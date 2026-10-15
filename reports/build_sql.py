"""Turn the audit results into reviewed SQL: corrections + deletions on existing rows, and inserts for
missing programs whose dates and budget are confirmed by filings. Uncertain items are listed, not written."""
import glob, json, os

A = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(A, "snapshot.json")))
by_key = {(r["symbol"][:-3], r["mandate"].get("start_date"), r["mandate"].get("end_date")): r for r in rows}

# Decisions made after reading the evidence (see the audit summary)
SKIP_CORRECTIONS = {
    ("CBDK", "2026-05-20"),  # the company's own filing contradicts itself (17,096,300 vs 17,096,700)
}
# ERAA 4 Aug 2026 (results report p.5): five lines, Rp57,090,735,000 / 127,130,900 shares
TX_PRICE_FIXES = {("ERAA", "2026-08-04"): 449.07}
# PRDA report of 2026-10-09 (att 221): trades after the DB's last day (2 Oct)
TX_APPEND = {("PRDA", "2026-08-20"): [
    {"date": "2026-10-05", "share_amount": 636100, "average_price": 2845.0, "percentage_of_shares": None},
    {"date": "2026-10-06", "share_amount": 916000, "average_price": 2946.0, "percentage_of_shares": None},
    {"date": "2026-10-07", "share_amount": 594300, "average_price": 3031.0, "percentage_of_shares": None},
    {"date": "2026-10-08", "share_amount": 425800, "average_price": 3035.0, "percentage_of_shares": None},
    {"date": "2026-10-09", "share_amount": 615000, "average_price": 3075.0, "percentage_of_shares": None},
]}
# Reviewer findings: the cited filing in the audit was the wrong one
SOURCE_OVERRIDES = {
    ("ADRO", "2025-06-03"): "2026-03-11 plan att 32: 556,195,200 shares bought 3 Jun 2025 - 28 Feb 2026 "
                            "(latest stated; buying 1 Mar - 16 Apr 2026 unreported, so a lower bound)",
    ("ASLC", "2026-05-20"): "2026-04-10 plan att 32: period 12 months from 20 May 2026",
    ("DEWA", "2025-11-18"): "2025-11-18 plan att 02: buyback period 19 Nov 2025 - 19 Feb 2026",
}
# Spend only when a filing states it: GEMA/ISSP values were derived from a remaining-budget column and are
# mid-program snapshots; AGRO states nominal + execution costs separately (budget includes costs)
INSERT_SPENT = {("GEMA", "2025-12-12"): None, ("ISSP", "2026-05-25"): None, ("AGRO", "2025-06-25"): 2715958910}


def lit(v):
    return "null" if v is None else str(int(v)) if isinstance(v, (int, float)) else f"'{v}'"


def mandate(s, e):
    return f"'{json.dumps({'start_date': s, 'end_date': e}, separators=(',', ':'))}'::jsonb"


def where(sym, s, e):
    return f"symbol = '{sym}.JK' and mandate = {mandate(s, e)}"


updates, deletes, inserts, skipped = [], [], [], []
for f in sorted(glob.glob(os.path.join(A, "results", "b*.json"))):
    for sd in json.load(open(f, encoding="utf-8"))["symbols"]:
        sym = sd["symbol"]
        for u in sd.get("unmatched_db_rows") or []:
            if u.get("verdict") == "delete":
                deletes.append((sym, u["start_date"], u["end_date"], u.get("reason", "")))
        for p in sd.get("programs") or []:
            v, db = p.get("verdict"), p.get("db_row")
            if v == "correct" and db:
                if (sym, db["start_date"]) in SKIP_CORRECTIONS:
                    skipped.append((sym, db, "self-contradicting filing"))
                    continue
                updates.append((sym, db, p["corrections"], p.get("sources", [])))
            elif v == "missing":
                # Rule: a fluctuating-market plan is in force from its disclosure. A shareholder-approved (GMS)
                # plan needs a filing dated on/after its start date (a report, termination or a later plan
                # referring to it); a pre-meeting disclosure alone doesn't prove it was approved.
                dated = sorted(s[:10] for s in p.get("sources") or [] if s[:4].isdigit())
                confirmed = p.get("regime") == "fluctuating" or bool(
                    p.get("start_date") and dated and dated[-1] >= p["start_date"])
                if not p.get("start_date") or not p.get("end_date") or not p.get("allocated_fund") \
                        or p.get("status") == "pending_gms" or not confirmed:
                    skipped.append((sym, {"start_date": p.get("start_date"), "end_date": p.get("end_date")},
                                    "GMS approval not confirmed by a post-meeting filing" if p.get("start_date")
                                    else "dates not known yet"))
                    continue
                inserts.append((sym, p))
            elif v == "uncertain":
                skipped.append((sym, db or {"start_date": p.get("start_date"), "end_date": p.get("end_date")},
                                (p.get("notes") or "")[:120]))

out = ["-- idx_buybacks corrections from the 2026-10-15 audit against IDX filings",
       "-- Run inside one transaction; review each block first.", "begin;", ""]
out.append("-- 1. Field corrections (each value is stated in the cited filing)")
for sym, db, corr, src in updates:
    sets, fund_sets, tx_fixes = [], {}, []
    s, e = db["start_date"], db["end_date"]
    new_s, new_e = corr.get("mandate.start_date", s), corr.get("mandate.end_date", e)
    if (new_s, new_e) != (s, e):
        sets.append(f"mandate = {mandate(new_s, new_e)}")
        # Months were built for the old period; the treasury sync rebuilds them if the program is still active
        sets.append("registry_updates = null")
    for k, val in corr.items():
        if k.startswith("company_fund."):
            fund_sets[k.split(".", 1)[1]] = val
        elif k == "accumulated_shares_purchased":
            sets.append(f"accumulated_shares_purchased = {lit(val)}")
        elif k.startswith("transaction_details["):
            tx_fixes.append((k, val))
    if fund_sets:
        row = by_key[(sym, s, e)]
        fund = dict((row.get("company_fund") or [{}])[0] or {})
        fund.update(fund_sets)
        sets.append(f"company_fund = '{json.dumps([fund], separators=(',', ':'))}'::jsonb")
    if tx_fixes or (sym, s) in TX_APPEND:
        row = by_key[(sym, s, e)]
        tx = [dict(t) for t in row["transaction_details"]] + TX_APPEND.get((sym, s), [])
        for k, val in tx_fixes:
            day, field = k[len("transaction_details[date="):].split("].")
            for t in tx:
                if t.get("date") == day:
                    t[field] = val
        for t in tx:  # a day's average price must follow its corrected share count
            fix = TX_PRICE_FIXES.get((sym, t.get("date")))
            if fix is not None:
                t["average_price"] = fix
        tx.sort(key=lambda t: t.get("date") or "")
        sets.append(f"transaction_details = '{json.dumps(tx, separators=(',', ':'))}'::jsonb")
    out.append(f"-- {sym} {s}..{e}: {', '.join(f'{k}={v}' for k, v in corr.items())}")
    out.append(f"--   source: {SOURCE_OVERRIDES.get((sym, s)) or (src[-1] if src else '?')}"[:240])
    out.append(f"update idx_buybacks set {', '.join(sets)}, updated_on = now()\n  where {where(sym, s, e)};")
out += ["", "-- 2. Rows that are not buyback programs, or duplicates"]
for sym, s, e, reason in deletes:
    out.append(f"-- {sym}: {reason[:160]}")
    out.append(f"delete from idx_buybacks where {where(sym, s, e)};")
out += ["", "-- 3. Missing programs with filing-confirmed dates and budget"]
for sym, p in inserts:
    acc = p.get("reported_shares") or 0
    spent = INSERT_SPENT.get((sym, p["start_date"]), p.get("reported_spent"))
    fund = [{"utilized_fund": float(spent or 0), "allocated_fund": float(p["allocated_fund"])}]
    out.append(f"-- {sym} {p['start_date']}..{p['end_date']} ({p.get('regime')}): {(p.get('sources') or ['?'])[-1]}"[:220])
    out.append("insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, "
               "accumulated_shares_purchased, updated_on)\n  values ("
               f"'{sym}.JK', {mandate(p['start_date'], p['end_date'])}, '[]'::jsonb, "
               f"'{json.dumps(fund, separators=(',', ':'))}'::jsonb, {lit(acc)}, now()) on conflict do nothing;")
out += ["", "commit;", "", "-- Not written (needs a filing that confirms it):"]
for sym, db, why in skipped:
    out.append(f"--   {sym} {db.get('start_date')}..{db.get('end_date')}: {why}")
open(os.path.join(A, "fixes.sql"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"{len(updates)} updates, {len(deletes)} deletes, {len(inserts)} inserts, {len(skipped)} left out")
