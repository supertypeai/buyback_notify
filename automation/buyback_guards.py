"""Deterministic checks on an LLM extraction, used to trigger retries / escalation.

Each check returns human-readable problems that are fed back to the model verbatim,
so they say exactly which row or field looks wrong and why.
"""

import logging
import re
from datetime import date, timedelta

from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)

_SLACK = timedelta(days=3)


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except (TypeError, ValueError):
        return None


def _n(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- PDF text layer

def pdf_text(paths: list[str]) -> str:
    """Concatenated text layer of the PDFs, or '' if any PDF is scanned (no usable text layer),
    since figures may then sit in the part we can't read."""
    out = []
    for p in paths:
        try:
            pages = [page.extract_text() or "" for page in PdfReader(p).pages]
        except Exception:
            return ""
        if sum(len(x.strip()) for x in pages) < 200:
            return ""
        out.extend(pages)
    return "\n".join(out)


def pdf_text_partial(paths: list[str]) -> str:
    """Text layer of whichever PDFs have one (scanned ones contribute nothing)."""
    out = []
    for p in paths:
        try:
            out.extend(page.extract_text() or "" for page in PdfReader(p).pages)
        except Exception:
            continue
    return "\n".join(out)


_NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)")


def numbers_in(text: str) -> set[float]:
    """Every number in the text, read under both Indonesian and English conventions."""
    text = re.sub(r"(?i)(Rp|IDR)\s*\.", r"\1 ", text)
    vals = set()
    for tok in _NUM.findall(text):
        for th, dec in ((".", ","), (",", ".")):
            parts = tok.split(dec)
            if len(parts) > 2:
                continue
            groups = parts[0].split(th)
            if len(groups) > 1 and not all(len(g) == 3 for g in groups[1:]):
                continue
            try:
                vals.add(float("".join(groups) + ("." + parts[1] if len(parts) == 2 else "")))
            except ValueError:
                pass
    return vals


# ---------------------------------------------------------------- checks

def check(ex: dict, publish_date: str, text: str = "", partial_text: str = "") -> list[str]:
    """Problems found in one extraction. Empty list = passed."""
    missing = [k for k in ("is_share_buyback", "doc_type") if ex.get(k) is None]
    if ex.get("is_share_buyback") and not ex.get("symbol"):
        missing.append("symbol")
    if missing:
        return [f"required field(s) missing: {', '.join(missing)} - return the complete JSON object"]
    if not ex.get("is_share_buyback") or ex.get("doc_type") == "other":
        return []
    problems = []
    # Every plan states a budget or a share cap; neither means the document was not actually read.
    # (plan_update is exempt: a correction may only restate dates or the schedule.)
    if ex.get("doc_type") == "plan" and _n(ex.get("allocated_fund")) is None \
            and _n(ex.get("max_shares")) is None:
        problems.append("plan has neither allocated_fund nor max_shares - read the attached letter for the "
                        "maximum buyback budget and/or number of shares")
    published = _d(publish_date[:10])
    start, end = _d(ex.get("mandate_start_date")), _d(ex.get("mandate_end_date"))
    txs = ex.get("transactions") or []

    for f in ("mandate_start_date", "mandate_end_date", "report_as_of_date"):
        if ex.get(f) and not _d(ex[f]):
            problems.append(f"{f} '{ex[f]}' is not a valid YYYY-MM-DD date")
    if start and end and end < start:
        problems.append(f"mandate_end_date {end} is before mandate_start_date {start}")

    # Dates: valid, not in the future, in document order, inside the mandate
    prev = None
    for i, t in enumerate(txs, 1):
        if not t.get("date"):
            continue
        d = _d(t["date"])
        if d is None:
            problems.append(f"transactions row {i}: date '{t['date']}' is not a valid date")
            continue
        if published and d > published:
            problems.append(f"transactions row {i}: date {d} is after the announcement was published "
                            f"({published}) - likely a misread year or swapped day/month")
        if prev and d < prev:
            problems.append(f"transactions row {i}: date {d} is earlier than the previous row ({prev}); "
                            f"rows must follow the document's order - check for a swapped day/month "
                            f"(e.g. '01-Apr-26' is 2026-04-01)")
        if start and d < start - _SLACK:
            problems.append(f"transactions row {i}: date {d} is before mandate_start_date {start}")
        if end and d > end + _SLACK:
            problems.append(f"transactions row {i}: date {d} is after mandate_end_date {end}")
        prev = d
        if d.weekday() >= 5:
            problems.append(f"transactions row {i}: {d} is a weekend (IDX does not trade) - re-read the date")

    # Rows vs the totals the document prints
    dated = [t for t in txs if t.get("date")]
    sum_shares = sum(_n(t.get("share_amount")) or 0 for t in txs)
    sum_value = sum((_n(t.get("share_amount")) or 0) * (_n(t.get("average_price")) or 0) for t in txs)
    stated_shares, stated_value = _n(ex.get("stated_total_shares")), _n(ex.get("stated_total_value"))
    if dated and stated_shares and abs(sum_shares - stated_shares) > 0.5:
        problems.append(f"transaction share_amounts sum to {sum_shares:,.0f} but the document's stated total "
                        f"is {stated_shares:,.0f} (difference {sum_shares - stated_shares:+,.0f}) - "
                        f"re-read each row's share amount")
    if dated and stated_value and sum_value and abs(sum_value - stated_value) > 0.02 * stated_value:
        problems.append(f"sum of share_amount x average_price is {sum_value:,.0f} but the stated total value "
                        f"is {stated_value:,.0f} - re-read prices/share amounts")

    # Per-row printed amounts and remaining-budget columns (catch a misread share amount or price).
    # Fees and rounding make these differ by a few percent, so only clear outliers count; if most rows
    # deviate the same way it's a document convention, not a misread, and the check is skipped.
    row_problems, rows_checked = [], 0
    # The first row has no reliable "previous remaining" (tables often start mid-program), so the
    # remaining-budget check starts from the second row
    prev_rem = None
    for i, t in enumerate(txs, 1):
        sh, px = _n(t.get("share_amount")), _n(t.get("average_price"))
        val, rem = _n(t.get("value")), _n(t.get("remaining_budget"))
        if sh and px and val:
            rows_checked += 1
            if abs(sh * px - val) > 0.06 * val:
                row_problems.append(f"transactions row {i} ({t.get('date')}): {sh:,.0f} x {px:,.2f} = "
                                    f"{sh * px:,.0f} does not match the row's printed value {val:,.0f}")
        elif sh and px and rem is not None and prev_rem:
            spent = prev_rem - rem
            if spent > 0:
                rows_checked += 1
                if abs(spent - sh * px) > 0.06 * spent:
                    row_problems.append(f"transactions row {i} ({t.get('date')}): the remaining-budget column "
                                        f"drops by {spent:,.0f} but {sh:,.0f} x {px:,.2f} = {sh * px:,.0f}")
        if rem is not None:
            prev_rem = rem
    if row_problems and len(row_problems) <= max(2, 0.25 * rows_checked):
        problems.extend(row_problems)

    # Fund arithmetic: budget - remaining = used; used ~ sum(shares x price) when the rows cover the program
    alloc, util, rem = _n(ex.get("allocated_fund")), _n(ex.get("utilized_fund")), _n(ex.get("remaining_budget"))
    if alloc and util is not None and rem is not None and abs(alloc - rem - util) > max(1000, 0.00001 * alloc):
        problems.append(f"allocated_fund {alloc:,.0f} - remaining_budget {rem:,.0f} = {alloc - rem:,.0f}, "
                        f"but utilized_fund is {util:,.0f} - re-read these three figures")
    acc_ = _n(ex.get("accumulated_shares_purchased"))
    covers_program = dated and acc_ is not None and abs(acc_ - sum_shares) <= 0.5
    if util and sum_value and covers_program and abs(util - sum_value) > 0.05 * sum_value:
        problems.append(f"utilized_fund {util:,.0f} is far from the sum of share_amount x average_price "
                        f"({sum_value:,.0f}); only report utilized_fund if the document prints it or prints "
                        f"both the budget and the remaining budget")

    acc = _n(ex.get("accumulated_shares_purchased"))
    if acc and dated and stated_shares is None and abs(acc - sum_shares) > 0.5:
        problems.append(f"accumulated_shares_purchased {acc:,.0f} differs from the sum of transactions "
                        f"{sum_shares:,.0f}")

    # Scale errors ("Rp480.000.000 (480 juta)" read as 480 billion): the value isn't printed, but
    # value / 1,000 or / 1,000,000 is. Uses whatever text layer exists, even if some PDFs are scanned.
    ptext = partial_text or text
    if len(ptext) > 500:
        pvals = numbers_in(ptext)
        digits_only = re.sub(r"(?<=\d)[.,\s]+(?=\d)", "", ptext)  # pdf text can split long numbers
        for f in ("allocated_fund", "max_shares", "utilized_fund"):
            v = _n(ex.get(f))
            if not v or v < 1e6 or any(abs(v - x) <= max(1, v * 0.0005) for x in pvals) \
                    or str(int(v)) in digits_only:
                continue
            for factor in (1e3, 1e6):
                if any(abs(v / factor - x) <= max(1, v / factor * 0.0005) for x in pvals if x >= 1000):
                    problems.append(f"{f} = {v:,.0f} is not printed in the document, but {v / factor:,.0f} is - "
                                    f"likely a scale error (check juta/miliar/triliun and thousand separators)")
                    break

    # Printed figures must literally appear in the document (only checkable with a text layer)
    if len(text) > 500:
        vals = numbers_in(text)
        derived_alloc = (_n(ex.get("utilized_fund")) or 0) + (_n(ex.get("remaining_budget")) or 0)
        for f in ("stated_total_shares", "allocated_fund", "max_shares"):
            v = _n(ex.get(f))
            if f == "allocated_fund" and v and abs(v - derived_alloc) <= max(1, v * 0.0005):
                continue  # budget = used + remaining, both printed
            if v and v >= 1000 and not any(abs(v - x) <= max(1, v * 0.0005) for x in vals) \
                    and not re.search(r"(?i)(triliun|trillion|miliar|billion|juta|million)", text):
                problems.append(f"{f} = {v:,.0f} does not appear anywhere in the document text")
    return problems


def fix_scale(ex: dict, partial_text: str) -> dict:
    """Undo 1,000x / 1,000,000x reading errors when the document prints exactly value / factor
    (e.g. "Rp480.000.000 (480 juta)" read as 480 billion). Deterministic; recorded in `derived`."""
    if len(partial_text) <= 500:
        return ex
    vals = numbers_in(partial_text)
    digits_only = re.sub(r"(?<=\d)[.,\s]+(?=\d)", "", partial_text)
    for f in ("allocated_fund", "max_shares", "utilized_fund"):
        v = _n(ex.get(f))
        if not v or v < 1e6 or any(abs(v - x) <= max(1, v * 0.0005) for x in vals) or str(int(v)) in digits_only:
            continue
        for factor in (1e3, 1e6):
            hit = [x for x in vals if x >= 1000 and abs(v / factor - x) <= max(1, v / factor * 0.0005)]
            if hit:
                ex[f] = hit[0]
                ex.setdefault("derived", []).append(f"{f} scaled down {factor:,.0f}x to the printed {hit[0]:,.0f}")
                break
    return ex


def repair(ex: dict) -> dict:
    """Fill values that follow arithmetically from what the document states."""
    if ex.get("utilized_fund") in (None, "", 0):
        alloc, rem = _n(ex.get("allocated_fund")), _n(ex.get("remaining_budget"))
        if alloc and rem is not None and 0 <= rem <= alloc:
            ex["utilized_fund"] = alloc - rem
            ex.setdefault("derived", []).append("utilized_fund = allocated_fund - remaining_budget")
        elif _n(ex.get("stated_total_value")):
            ex["utilized_fund"] = _n(ex["stated_total_value"])
            ex.setdefault("derived", []).append("utilized_fund = stated_total_value")
    if ex.get("accumulated_shares_purchased") in (None, "") and _n(ex.get("stated_total_shares")):
        ex["accumulated_shares_purchased"] = int(_n(ex["stated_total_shares"]))
    return ex
