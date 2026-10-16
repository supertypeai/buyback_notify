"""Track buyback progress from the treasury-share line of IDX monthly registration reports.

Every listed company files a "Monthly Report of Securities Holders Registration" around the
5th-10th of each month. Its "Saham Treasuri" row holds treasury shares at the previous and the
current month-end, so the month-on-month change is the shares bought back (or transferred /
cancelled when it drops). This covers programs that never publish a buyback report on IDX.

For each idx_buybacks program still active (period end + 1 month >= today) this builds
`registry_updates`: a baseline month-end before the program starts, then each month-end in the
period. accumulated_shares_purchased is filled from it only when the company has not reported
an official total.

Run from the repo root:
  python automation/treasury_sync.py --dry-run          # show what would be written
  python automation/treasury_sync.py --all --dry-run    # every program, incl. ended ones (validation)
  python automation/treasury_sync.py                    # write registry_updates
"""

import argparse
import calendar
import json
import os
import re
import time
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

from curl_cffi import requests as cffi_requests  # noqa: E402

from buyback_store import TABLE, _d, _sb, fetch_existing  # noqa: E402

ANNOUNCEMENT_URL = "https://www.idx.co.id/primary/ListedCompany/GetAnnouncement"
REPORT_TITLE = "Monthly Report of Securities Holders Registration"
CACHE_PATH = os.getenv("TREASURY_CACHE", "data/treasury_reports.json")
# Bump when the parser changes so cached reports are parsed again
PARSER_VERSION = 2
# Keep tracking a program this long after its period ends, to pick up the final month-end report
TRAILING = timedelta(days=31)

# Cloudflare accepts some TLS fingerprints and not others, and that changes over time
_FINGERPRINTS = ["chrome124", "safari", "chrome", "chrome131"]
_proxy = os.getenv("PROXY_URL", "")
_PROXIES = {"http": _proxy, "https": _proxy} if _proxy else None
_session = None

_MONTHS = {m: i for i, m in enumerate(
    ["januari", "februari", "maret", "april", "mei", "juni", "juli",
     "agustus", "september", "oktober", "november", "desember"], 1)}


# ---------------------------------------------------------------- IDX access

class IdxUnreachable(RuntimeError):
    """No session could reach IDX at all; retrying company by company would only waste time."""


def _new_session():
    last = None
    for imp in _FINGERPRINTS:
        # The proxy re-signs HTTPS with its own certificate, so verification fails through it
        s = cffi_requests.Session(impersonate=imp, proxies=_PROXIES, verify=not _proxy)
        try:
            s.get("https://www.idx.co.id/en/", timeout=30)
            probe = s.get(ANNOUNCEMENT_URL, params={"kodeEmiten": "BBCA", "emitenType": "*", "indexFrom": 0,
                                                    "pageSize": 1, "lang": "en"}, timeout=30)
            if probe.status_code == 200:
                return s
            last = f"HTTP {probe.status_code}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
    raise IdxUnreachable(f"IDX unreachable with every TLS fingerprint (last: {last})")


def _get(url: str, params: dict | None = None, retries: int = 4):
    global _session
    for attempt in range(retries):
        try:
            _session = _session or _new_session()
            resp = _session.get(url, params=params, timeout=60)
            if resp.status_code == 200:
                return resp
            print(f"  HTTP {resp.status_code} for {url}")
            if resp.status_code == 403:
                _session = None  # Cloudflare challenge: try a fresh session / fingerprint
            elif resp.status_code == 429:
                time.sleep(30 * (attempt + 1))  # rate limited: back off well beyond the usual retry
        except IdxUnreachable:
            raise
        except Exception as e:
            print(f"  {type(e).__name__} for {url}: {e}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}")


def fetch_reports(code: str, date_from: date, date_to: date) -> list[dict]:
    """Registration reports a company filed between two dates (corrections included)."""
    out, page = [], 0
    while True:
        data = _get(ANNOUNCEMENT_URL, {
            "kodeEmiten": code, "emitenType": "*", "indexFrom": page, "pageSize": 100, "lang": "en",
            "dateFrom": date_from.strftime("%Y%m%d"), "dateTo": date_to.strftime("%Y%m%d"),
            "keyword": "Securities Holders Registration",
        }).json()
        replies = data.get("Replies") or []
        for r in replies:
            p = r["pengumuman"]
            if not p["JudulPengumuman"].strip().startswith(REPORT_TITLE):
                continue
            # The main e-reporting form holds the table; attachments are scans of the same data
            atts = sorted(r.get("attachments") or [], key=lambda a: a.get("IsAttachment", True))
            if atts:
                out.append({"published": p["TglPengumuman"], "title": p["JudulPengumuman"].strip(),
                            "url": atts[0]["FullSavePath"]})
        # indexFrom is a page number, not an offset
        if len(replies) < 100:
            return out
        page += 1
        time.sleep(1)


# ---------------------------------------------------------------- parsing

_SHARES = re.compile(r"^\d{1,3}(?:\.\d{3})*$")
_TOKEN = re.compile(r"[\d.,]+%?")


def _shares(tok: str) -> int | None:
    return int(tok.replace(".", "")) if _SHARES.match(tok) else None


def _pct(tok: str) -> float | None:
    try:
        return float(tok.rstrip("%").replace(",", "."))
    except ValueError:
        return None


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def parse_treasury(text: str) -> dict:
    """Treasury shares and % at the previous and the current month-end, from the report text.

    Long numbers can wrap: the leading digits sit on the line above the label and the rest on
    the label line ("1.564.531.43 3,342% ..." / "Saham Treasuri 0 0"). Those pieces are joined
    column by column. GOTO lists two share classes side by side (previous A, B, then current
    A, B), so the current figures start halfway along the row."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    for i, line in enumerate(lines):
        # "Saham Treasuri" since early 2026, "Saham Treasury" in older reports
        m = re.search(r"Saham\s+Treasur[iy]\b", line)
        if not m:
            continue
        toks = _TOKEN.findall(line[m.end():])
        if any(t.endswith("%") for t in toks):
            share_toks = [t for t in toks if not t.endswith("%")]
            pct_toks = [t for t in toks if t.endswith("%")]
        else:
            above = _TOKEN.findall(lines[i - 1]) if i else []
            heads = [t for t in above if not t.endswith("%")]
            if not toks or len(heads) != len(toks):
                return {"error": f"cannot join wrapped treasury numbers: {line.strip()!r}"}
            share_toks = [h + t for h, t in zip(heads, toks)]
            pct_toks = [t for t in above if t.endswith("%")]
        shares = [_shares(t) for t in share_toks]
        pcts = [_pct(t) for t in pct_toks]
        if len(shares) < 2 or None in shares or len(pcts) < 2 or None in pcts:
            return {"error": f"unexpected treasury row: {line.strip()!r}"}
        # Previous-month columns come first, current-month ones start halfway along the row
        return {"prev_shares": shares[0], "shares": shares[len(shares) // 2],
                "prev_pct": pcts[0], "pct": pcts[len(pcts) // 2]}
    return {"error": "no 'Saham Treasuri' row"}


def parse_period(text: str) -> date | None:
    """The month-end the report covers: "... berakhir pada akhir bulan September - 2026", or in
    older reports "... berakhir pada 28 November 2025" (the last trading day of the month)."""
    m = re.search(r"akhir\s+bulan\s+([A-Za-z]+)\s*-\s*(\d{4})", text) \
        or re.search(r"berakhir\s+pada\s+\d{1,2}\s+([A-Za-z]+)\s+(\d{4})", text)
    if m and m.group(1).lower() in _MONTHS:
        return _month_end(int(m.group(2)), _MONTHS[m.group(1).lower()])
    return None


def parse_report(report: dict) -> dict:
    from liteparse import LiteParse

    pdf = _get(report["url"]).content
    text = LiteParse(ocr_enabled=False, quiet=True).parse(pdf).text
    out = {**report, **parse_treasury(text), "version": PARSER_VERSION}
    month_end = parse_period(text)
    if month_end is None:
        # Reports cover the month before the one they are filed in
        pub = date.fromisoformat(report["published"][:10])
        month_end = pub.replace(day=1) - timedelta(days=1)
        out["period_from_publish_date"] = True
    out["month_end"] = month_end.isoformat()
    return out


# ---------------------------------------------------------------- cache

def load_cache(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)


def company_months(code: str, date_from: date, date_to: date, cache: dict) -> dict[str, dict]:
    """Month-end -> parsed report for a company. A correction filed later replaces the original."""
    months = {}
    for rep in fetch_reports(code, date_from, date_to):
        parsed = cache.get(rep["url"])
        if not parsed or parsed.get("version") != PARSER_VERSION:
            try:
                parsed = parse_report(rep)
            except Exception as e:
                print(f"  ! {code} {rep['published'][:10]}: {e}")
                continue
            cache[rep["url"]] = parsed
            time.sleep(1)
        if "error" in parsed:
            print(f"  ! {code} {parsed['month_end']} ({parsed['published'][:10]}): {parsed['error']}")
            continue
        cur = months.get(parsed["month_end"])
        if cur is None or parsed["published"] > cur["published"]:
            months[parsed["month_end"]] = parsed
    return months


# ---------------------------------------------------------------- programs

def _month_ends(start: date, end: date) -> list[date]:
    """Month-ends from the one before `start` (baseline) through the one covering `end`."""
    out = [start.replace(day=1) - timedelta(days=1)]
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(_month_end(y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build_registry(start: date, end: date, months: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """registry_updates for one program, plus problems worth reviewing."""
    entries, issues = [], []
    for i, me in enumerate(_month_ends(start, end)):
        if me > date.today():
            break
        key = me.isoformat()
        rep = months.get(key)
        if rep is not None:
            shares, pct, src = rep["shares"], rep["pct"], rep["url"]
        else:
            # Missing month: the next report's "previous month" column states the same figure
            nxt = months.get(_month_end(*((me.year + 1, 1) if me.month == 12 else (me.year, me.month + 1))).isoformat())
            if nxt is None:
                if i == 0:
                    issues.append(f"no report for baseline month-end {key}")
                elif me < date.today() - timedelta(days=15):
                    issues.append(f"no report for {key}")
                continue
            shares, pct, src = nxt["prev_shares"], nxt["prev_pct"], nxt["url"]
        entry = {"month_end": key, "treasury_shares": shares, "treasury_pct": pct}
        if i == 0:
            entry["baseline"] = True
        elif entries:
            entry["change"] = shares - entries[-1]["treasury_shares"]
        entry["source_pdf"] = src
        # Each report's previous-month column should equal the prior report's current column
        if rep is not None and entries and entries[-1]["month_end"] == (me.replace(day=1) - timedelta(days=1)).isoformat() \
                and rep["prev_shares"] != entries[-1]["treasury_shares"]:
            issues.append(f"{key}: previous-month column {rep['prev_shares']:,} != {entries[-1]['month_end']} "
                          f"report {entries[-1]['treasury_shares']:,}")
        entries.append(entry)
    if entries and not entries[0].get("baseline"):
        entries = []  # without a baseline the changes can't be measured
    return entries, issues


def registry_total(entries: list[dict]) -> tuple[int | None, bool]:
    """Shares bought per the registry, and whether treasury dropped during the program.
    A drop (transfer / cancellation) would hide buying in latest - baseline, so then only the
    monthly increases are counted."""
    if len(entries) < 2:
        return None, False
    changes = [e["change"] for e in entries[1:] if "change" in e]
    dropped = any(c < 0 for c in changes)
    if dropped:
        return sum(c for c in changes if c > 0), True
    return entries[-1]["treasury_shares"] - entries[0]["treasury_shares"], False


def _overlaps(mandate: dict, lo: date, hi: date) -> bool:
    s, e = _d((mandate or {}).get("start_date")), _d((mandate or {}).get("end_date"))
    return bool(s and e and s <= hi and e >= lo)


def plan_updates(rows: list[dict], include_ended: bool, cache: dict,
                 fetch_failures: list | None = None) -> list[dict]:
    """Registry plans for the target programs. Companies IDX wouldn't serve are added to
    `fetch_failures` (and skipped) so the caller can fail the run after writing the rest."""
    fetch_failures = [] if fetch_failures is None else fetch_failures
    today = date.today()
    targets = []
    for row in rows:
        m = row.get("mandate") or {}
        start, end = _d(m.get("start_date")), _d(m.get("end_date"))
        if not start or not end or start > today:
            continue
        if not include_ended and end + TRAILING < today:
            continue
        targets.append((row, start, end))

    by_code: dict[str, list] = {}
    for t in targets:
        by_code.setdefault(t[0]["symbol"].removesuffix(".JK"), []).append(t)

    plans = []
    for n, (code, progs) in enumerate(sorted(by_code.items()), 1):
        # Reports filed in the start month cover the baseline month-end
        date_from = min(s for _, s, _ in progs).replace(day=1)
        date_to = min(today, max(e for _, _, e in progs) + TRAILING + timedelta(days=15))
        print(f"  [{n}/{len(by_code)}] {code}: reports {date_from} .. {date_to}")
        try:
            months = company_months(code, date_from, date_to, cache)
        except IdxUnreachable:
            raise
        except Exception as e:
            print(f"  ! {code}: {e}")
            fetch_failures.append(f"{code}: {e}")
            continue
        time.sleep(2)  # IDX rate-limits bursts of announcement queries
        siblings = [r for r in rows if r["symbol"] == f"{code}.JK"]
        for row, start, end in progs:
            entries, issues = build_registry(start, end, months)
            total, dropped = registry_total(entries)
            if dropped:
                issues.append("treasury dropped during the program (transfer/cancellation); "
                              "counted monthly increases only")
            # Month-end snapshots can't split buying between programs active in the same months
            # (back-to-back programs), so the total would include the other program's shares
            window = (start.replace(day=1), _month_ends(start, end)[-1])
            shared = [r["mandate"] for r in siblings if r is not row and _overlaps(r["mandate"], *window)]
            if shared:
                issues.append("shares months with " + ", ".join(
                    f"{m.get('start_date')}..{m.get('end_date')}" for m in shared)
                    + " - registry total not used as accumulated_shares_purchased")
            plans.append({"row": row, "registry_updates": entries, "registry_total": total,
                          "issues": issues, "shared_months": bool(shared)})
    return plans


def _is_official(row: dict) -> bool:
    """accumulated_shares_purchased came from the company's own reports, not from a previous
    registry run (which writes exactly latest - baseline, or the sum of increases)."""
    acc = row.get("accumulated_shares_purchased") or 0
    if not acc:
        return False
    previous, _ = registry_total(row.get("registry_updates") or [])
    return previous is None or acc != previous


def patch(row: dict, body: dict) -> str | None:
    url, h = _sb()
    resp = requests.patch(
        f"{url}/rest/v1/{TABLE}",
        params={"symbol": f"eq.{row['symbol']}", "mandate": f"eq.{json.dumps(row['mandate'])}"},
        headers={**h, "Prefer": "return=representation"}, json=body, timeout=60,
    )
    if resp.status_code >= 300:
        return f"{resp.status_code} {resp.text[:200]}"
    # Row-level security turns a disallowed update into "200, nothing changed" (e.g. an anon key)
    if not resp.json():
        return "no row updated - row not found, or SUPABASE_KEY lacks update rights (needs the service_role key)"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="include programs that ended long ago (validation)")
    ap.add_argument("--symbol", help="only this ticker, e.g. ASII")
    ap.add_argument("--dry-run", action="store_true", help="print the planned writes without touching the DB")
    args = ap.parse_args()

    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        raise SystemExit("SUPABASE_URL / SUPABASE_KEY are required")

    rows = fetch_existing()
    if args.symbol:
        rows = [r for r in rows if r["symbol"].removesuffix(".JK") == args.symbol.upper()]
    cache = load_cache(CACHE_PATH)
    fetch_failures: list[str] = []
    try:
        plans = plan_updates(rows, args.all, cache, fetch_failures)
    except IdxUnreachable as e:
        raise SystemExit(f"FAILED: {e}")
    finally:
        save_cache(cache, CACHE_PATH)

    errors = []
    for pl in plans:
        row, entries, total = pl["row"], pl["registry_updates"], pl["registry_total"]
        m = row["mandate"]
        official = _is_official(row)
        print(f"\n{row['symbol']} {m['start_date']}..{m['end_date']}  "
              f"months={len(entries)}  registry_total={'-' if total is None else f'{total:,}'}  "
              f"db_accumulated={row.get('accumulated_shares_purchased') or 0:,}{' (official)' if official else ''}")
        for e in entries:
            chg = "baseline" if e.get("baseline") else f"{e.get('change', 0):+,}"
            print(f"    {e['month_end']}  {e['treasury_shares']:>16,}  {e['treasury_pct']:>7}%  {chg}")
        for issue in pl["issues"]:
            print(f"    ! {issue}")

        if not entries:
            continue
        body = {"registry_updates": entries}
        if not official and total is not None and not pl["shared_months"]:
            body["accumulated_shares_purchased"] = total
        if args.dry_run:
            print(f"    would set: {', '.join(body)}")
            continue
        err = patch(row, body)
        if err:
            errors.append(f"{row['symbol']} {m}: {err}")

    if args.dry_run:
        print(f"\ndry run: {sum(1 for p in plans if p['registry_updates'])} of {len(plans)} programs would be updated")
    else:
        print(f"\nupdated {sum(1 for p in plans if p['registry_updates']) - len(errors)} programs, {len(errors)} errors")
        for e in errors:
            print("   ", e)

    # Exit non-zero after writing what we could, so the GitHub job turns red and emails
    problems = []
    if fetch_failures:
        problems.append(f"IDX would not serve {len(fetch_failures)} compan(ies), so they were not updated: "
                        f"{fetch_failures[0]}")
    if errors:
        problems.append(f"{len(errors)} row(s) not written to Supabase: {errors[0]}")
    if problems:
        raise SystemExit("FAILED: " + " | ".join(problems))


if __name__ == "__main__":
    main()
