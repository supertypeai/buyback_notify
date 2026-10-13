"""Merge per-announcement extractions into idx_buybacks rows, write CSVs and upsert to Supabase.

A row in idx_buybacks is one buyback program, keyed by (symbol, mandate) where
mandate = {"start_date", "end_date"}. Plans open a program; corrections, progress
reports and termination notices are attached to the program whose period covers them.
"""

import json
import os
from datetime import date, datetime, timedelta, timezone

import requests

TABLE = "idx_buybacks"
_MATCH_SLACK = timedelta(days=14)


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _interval(ex: dict, published: date) -> tuple[date, date]:
    """The period a report/termination speaks about, used to find its program."""
    dated = sorted(x for x in (_d(t.get("date")) for t in ex.get("transactions") or []) if x)
    as_of = _d(ex.get("report_as_of_date"))
    start = _d(ex.get("mandate_start_date")) or (dated[0] if dated else None) or as_of or published
    end = _d(ex.get("mandate_end_date")) or as_of or (dated[-1] if dated else None) or start
    return start, max(start, end)


def _overlap_days(p: dict, start: date, end: date) -> int:
    p_end = p["end"] or date.max
    return (min(end, p_end) - max(start, p["start"])).days


def _find_program(programs: list[dict], ex: dict, published: date, is_plan: bool):
    start = _d(ex.get("mandate_start_date"))
    if is_plan:
        # A correction/update of a plan keeps (roughly) the same start date;
        # undated plans (pending GMS approval) collapse into the latest undated program
        for p in reversed(programs):
            if start is None and p["start"] is None:
                return p
            if start and p["start"] and abs((p["start"] - start).days) <= 7:
                return p
        return None

    # Reports go to the program whose period overlaps theirs the most
    s, e = _interval(ex, published)
    best, best_overlap = None, -_MATCH_SLACK.days
    for p in programs:
        if p["start"] is None:
            continue
        ov = _overlap_days(p, s, e)
        if ov >= best_overlap:
            best, best_overlap = p, ov
    # A report stating its own mandate belongs to a different program when both
    # its start and end clearly differ from the (documented) program period
    end = _d(ex.get("mandate_end_date"))
    if best and start and not best["start_inferred"] and abs((best["start"] - start).days) > 7:
        if end is None or best["end"] is None or abs((best["end"] - end).days) > 7:
            return None
    return best


def _new_program(symbol: str) -> dict:
    return {
        "symbol": symbol, "start": None, "start_inferred": False, "end": None,
        "allocated": None, "max_shares": None,
        "tx": {}, "undated": None, "acc": None, "utilized": None, "sources": [],
    }


def build_programs(cache: dict) -> list[dict]:
    docs = []
    for entry in cache.values():
        ex, ann = entry["extraction"], entry["announcement"]
        if not ex.get("is_share_buyback") or ex.get("doc_type") == "other":
            continue
        symbol = (ex.get("symbol") or ann["symbol"] or "").strip().upper()
        if not symbol:
            continue
        docs.append((ann["publish_date"], symbol, ann, ex, entry.get("guard_issues") or []))
    docs.sort(key=lambda d: d[0])

    by_symbol: dict[str, list[dict]] = {}
    for published_s, symbol, ann, ex, guard_issues in docs:
        published = _d(published_s[:10])
        programs = by_symbol.setdefault(symbol, [])
        is_plan = ex.get("doc_type") in ("plan", "plan_update")
        prog = _find_program(programs, ex, published, is_plan)
        if prog is None:
            prog = _new_program(symbol)
            programs.append(prog)

        start, end = _d(ex.get("mandate_start_date")), _d(ex.get("mandate_end_date"))
        if is_plan:
            prog["start"] = start or prog["start"]
            prog["end"] = end or prog["end"]
            prog["start_inferred"] = prog["start_inferred"] and not start
        else:
            if start and (prog["start"] is None or prog["start_inferred"]):
                prog["start"], prog["start_inferred"] = start, False
            elif prog["start"] is None:
                # Program began before our window: provisional start from the report itself
                prog["start"], prog["start_inferred"] = _interval(ex, published)[0], True
            # Termination / final reports may shorten the period
            if end and (prog["end"] is None or ex.get("doc_type") == "termination"):
                prog["end"] = end
        prog["allocated"] = _num(ex.get("allocated_fund")) or prog["allocated"]
        prog["max_shares"] = _num(ex.get("max_shares")) or prog["max_shares"]

        for t in ex.get("transactions") or []:
            row = {
                "date": t.get("date") or None,
                "share_amount": int(_num(t.get("share_amount")) or 0),
                "average_price": _num(t.get("average_price")),
                "percentage_of_shares": _num(t.get("percentage_of_shares")),
            }
            if row["date"]:
                prog["tx"][row["date"]] = row  # later reports overwrite the same day
            elif row["share_amount"]:
                prog["undated"] = row
        if _num(ex.get("accumulated_shares_purchased")) is not None:
            prog["acc"] = int(_num(ex["accumulated_shares_purchased"]))
        elif any(t.get("date") for t in ex.get("transactions") or []):
            prog["acc"] = None  # newer daily rows but no stated total: use the sum of rows instead
        rem = _num(ex.get("remaining_budget"))
        derived = prog["allocated"] - rem if rem is not None and prog["allocated"] else None
        if derived is not None and 0 <= derived <= prog["allocated"]:
            # Budget (from this doc or the program's plan) - printed remaining budget, computed here
            # rather than trusting the model's arithmetic
            prog["utilized"] = derived
        elif _num(ex.get("utilized_fund")) is not None:
            # e.g. the report's remaining budget assumes a different budget than the plan (JRPT)
            prog["utilized"] = _num(ex["utilized_fund"])

        prog["sources"].append({
            "id": ann["id"],
            "date": published_s[:10],
            "doc_type": ex.get("doc_type"),
            "title": ann["title"],
            "pdfs": [a["url"] for a in ann["attachments"]],
            "guard_issues": guard_issues,
        })

    return [p for ps in by_symbol.values() for p in ps]


def to_row(p: dict) -> dict:
    """Shape a merged program like an idx_buybacks row."""
    tx = [p["tx"][k] for k in sorted(p["tx"])]
    if not tx and p["undated"]:
        tx = [p["undated"]]
    acc = p["acc"] if p["acc"] is not None else sum(t["share_amount"] for t in tx)
    return {
        "symbol": f"{p['symbol']}.JK",
        "mandate": {
            "start_date": p["start"].isoformat() if p["start"] else None,
            "end_date": p["end"].isoformat() if p["end"] else None,
        },
        "transaction_details": tx,
        "company_fund": [{
            "utilized_fund": p["utilized"] if p["utilized"] is not None else 0.0,
            "allocated_fund": p["allocated"] if p["allocated"] is not None else 0.0,
        }],
        "accumulated_shares_purchased": acc,
    }


# ---------------------------------------------------------------- Supabase

def _sb():
    url, key = os.environ["SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_KEY"]
    return url, {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def fetch_existing() -> list[dict]:
    url, h = _sb()
    resp = requests.get(f"{url}/rest/v1/{TABLE}?select=*", headers=h, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_known_symbols(symbols: list[str]) -> set[str]:
    url, h = _sb()
    resp = requests.get(
        f"{url}/rest/v1/idx_company_profile",
        params={"select": "symbol", "symbol": f"in.({','.join(symbols)})"},
        headers=h, timeout=60,
    )
    resp.raise_for_status()
    return {r["symbol"] for r in resp.json()}


def _mandate_dates(m):
    m = m or {}
    return _d(m.get("start_date")), _d(m.get("end_date"))


def _match_existing(row: dict, start_inferred: bool, existing: list[dict]):
    """Find the existing DB row this program corresponds to, if any."""
    same_symbol = [e for e in existing if e["symbol"] == row["symbol"]]
    for e in same_symbol:
        if e["mandate"] == row["mandate"]:
            return e
    s, en = _mandate_dates(row["mandate"])
    if s is None:
        return None
    candidates = []
    for e in same_symbol:
        xs, xe = _mandate_dates(e["mandate"])
        if not xs or not xe:
            continue
        overlaps = s <= xe + _MATCH_SLACK and (en is None or xs <= en + _MATCH_SLACK)
        close_start = abs((xs - s).days) <= 7
        if overlaps and (close_start or start_inferred or en is None):
            candidates.append((abs((xs - s).days), e))
    return min(candidates, key=lambda c: c[0])[1] if candidates else None


def _keep_existing_values(row: dict, existing: dict):
    """Never overwrite information already in the DB with an empty value from our documents."""
    old_fund = (existing.get("company_fund") or [{}])[0] or {}
    fund = row["company_fund"][0]
    for k in ("utilized_fund", "allocated_fund"):
        if not fund.get(k) and _num(old_fund.get(k)):
            fund[k] = _num(old_fund[k])
    if not row["accumulated_shares_purchased"] and existing.get("accumulated_shares_purchased"):
        row["accumulated_shares_purchased"] = existing["accumulated_shares_purchased"]
    # Union of daily rows by date; ours win on the same date. Undated aggregates are replaced.
    ours = {t["date"]: t for t in row["transaction_details"] if t.get("date")}
    for t in existing.get("transaction_details") or []:
        if isinstance(t, dict) and t.get("date") and t["date"] not in ours and "share_amount" in t:
            ours[t["date"]] = t
    if ours:
        row["transaction_details"] = [ours[k] for k in sorted(ours)]


def plan_rows(programs: list[dict], existing: list[dict] | None, known_symbols: set | None) -> list[dict]:
    """Decide, per program, the final row and whether it inserts or updates an existing row."""
    plans = []
    for p in sorted(programs, key=lambda p: (p["symbol"], p["start"] or date.min)):
        row = to_row(p)
        old = None
        if existing is not None:
            match = _match_existing(row, p["start_inferred"], existing)
            if match is not None:
                old = match["mandate"]
                xs, xe = _mandate_dates(old)
                s, e = _mandate_dates(row["mandate"])
                # Our dates win when they come from the documents; fill gaps from the DB
                if p["start_inferred"] or s is None:
                    s = xs
                e = e or xe
                row["mandate"] = {"start_date": s.isoformat() if s else None,
                                  "end_date": e.isoformat() if e else None}
                _keep_existing_values(row, match)

        warnings = []
        bad_docs = [s for s in p["sources"] if s.get("guard_issues")]
        if bad_docs:
            warnings.append("source failed consistency checks: " + " | ".join(
                f"{s['date']} {s['guard_issues'][0]}" for s in bad_docs))
        if p["start_inferred"] and old is None:
            warnings.append("start date unknown (plan predates window) - not upserted")
        if not row["mandate"]["start_date"] or not row["mandate"]["end_date"]:
            warnings.append("mandate period incomplete - not upserted")
        if known_symbols is not None and row["symbol"] not in known_symbols:
            warnings.append("symbol not in idx_company_profile - not upserted")

        if old is None:
            action = "insert"
        elif old == row["mandate"]:
            action = "update"
        else:
            action = f"update (mandate was {old.get('start_date')}..{old.get('end_date')})"
        plans.append({"row": row, "old_mandate": old, "action": action,
                      "warnings": warnings, "program": p})

    # Flag programs of the same symbol whose periods overlap (e.g. cumulative multi-program reports)
    for a in plans:
        for b in plans:
            if a is b or a["row"]["symbol"] != b["row"]["symbol"]:
                continue
            (as_, ae), (bs, be) = _mandate_dates(a["row"]["mandate"]), _mandate_dates(b["row"]["mandate"])
            if as_ and bs and as_ < (be or date.max) and bs < (ae or date.max):
                a["warnings"].append(f"overlaps {bs}..{be} - review")
    return plans


def upsert(plans: list[dict]) -> list[str]:
    """Write planned rows one by one so a bad row doesn't block the rest."""
    url, h = _sb()
    now = datetime.now(timezone.utc).isoformat()
    errors = []
    for plan in plans:
        row = {**plan["row"], "updated_on": now}
        old = plan["old_mandate"]
        if old is not None and old != row["mandate"]:
            # Mandate (part of the PK) changed: update the existing row in place
            resp = requests.patch(
                f"{url}/rest/v1/{TABLE}",
                params={"symbol": f"eq.{row['symbol']}", "mandate": f"eq.{json.dumps(old)}"},
                headers={**h, "Prefer": "return=minimal"}, json=row, timeout=60,
            )
        else:
            resp = requests.post(
                f"{url}/rest/v1/{TABLE}?on_conflict=symbol,mandate",
                headers={**h, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=row, timeout=60,
            )
        if resp.status_code >= 300:
            errors.append(f"{row['symbol']} {row['mandate']}: {resp.status_code} {resp.text[:200]}")
    return errors
