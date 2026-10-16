"""Sync IDX share-buyback disclosures into idx_buybacks.

Run from the repo root:
  python automation/buyback_sync.py --days 14            # daily run: upsert programs touched by new docs
  python automation/buyback_sync.py --since 2026-01-01   # backfill: upsert every program in the window
  python automation/buyback_sync.py --days 14 --dry-run  # show what would be written, touch nothing

Rows with any warning (failed consistency checks, overlapping programs, incomplete
mandate, unknown symbol) are skipped and printed for manual review.

Extractions are cached in data/buyback_extractions.json (committed by CI) so each
announcement is sent to the LLM only once, and older plans stay available when
new progress reports arrive.
"""

import argparse
import os
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

from buyback_extract import extract_all, fetch_buyback_announcements, save_cache  # noqa: E402
from buyback_store import (  # noqa: E402
    build_programs, fetch_existing, fetch_known_symbols, load_held, load_locked, plan_rows, upsert,
)

CACHE_PATH = os.getenv("BUYBACK_CACHE", "data/buyback_extractions.json")
# Rows verified by hand against the filings; the sync leaves them untouched
LOCKED_PATH = os.getenv("BUYBACK_LOCKED", "data/locked_programs.json")
# Programs not inserted until a filing confirms them (remove an entry once confirmed)
HELD_PATH = os.getenv("BUYBACK_HELD", "data/held_programs.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="YYYY-MM-DD; default is today minus --days")
    ap.add_argument("--until", default=date.today().isoformat())
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--pdf-dir", default="output/pdfs")
    ap.add_argument("--dry-run", action="store_true", help="print the planned writes without touching the DB")
    args = ap.parse_args()

    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        raise SystemExit("SUPABASE_URL / SUPABASE_KEY are required")

    since = args.since or (date.today() - timedelta(days=args.days)).isoformat()
    print(f"Fetching buyback announcements {since} .. {args.until}")
    announcements = fetch_buyback_announcements(since.replace("-", ""), args.until.replace("-", ""))
    print(f"  {len(announcements)} candidate announcements")

    cache = extract_all(announcements, args.pdf_dir, CACHE_PATH)
    # Extractions not yet written to the DB (new, re-extracted, or skipped/dry-run on an earlier run)
    pending = {k for k, v in cache.items() if v.get("synced") is False}

    programs = build_programs(cache)
    in_window = [p for p in programs if any(s["date"] >= since for s in p["sources"])]
    existing = fetch_existing()
    known = fetch_known_symbols(sorted({f"{p['symbol']}.JK" for p in in_window}))
    plans = plan_rows(in_window, existing, known, load_locked(LOCKED_PATH), load_held(HELD_PATH))

    # A backfill (--since) writes every program; daily runs only those with a pending document
    targets = plans if args.since else [
        pl for pl in plans if any(s["id"] in pending for s in pl["program"]["sources"])
    ]

    locked = [pl for pl in targets if pl.get("locked")]
    for pl in locked:
        print(f"  locked {pl['row']['symbol']} {pl['row']['mandate']}: hand-verified, not rewritten")
    targets = [pl for pl in targets if not pl.get("locked")]

    # Any warning keeps the row out of the DB
    for pl in targets:
        if pl["warnings"]:
            print(f"  skip {pl['row']['symbol']} {pl['row']['mandate']}: {'; '.join(pl['warnings'])}")
    targets = [pl for pl in targets if not pl["warnings"]]

    if args.dry_run:
        for pl in targets:
            print(f"  would {pl['action']}: {pl['row']['symbol']} {pl['row']['mandate']}")
        print(f"  dry run: {len(targets)} rows would be written")
        return

    errors = upsert(targets)
    print(f"  upserted {len(targets) - len(errors)} rows, {len(errors)} errors")
    for e in errors:
        print("   ", e)

    # Mark documents as synced: those behind rows written without error, and pending documents that
    # don't belong to any program (not a buyback). Skipped/flagged ones stay pending for review.
    failed = {e.split(" ")[0] for e in errors}
    done = {s["id"] for pl in targets if pl["row"]["symbol"] not in failed for s in pl["program"]["sources"]}
    done |= {s["id"] for pl in locked for s in pl["program"]["sources"]}
    in_programs = {s["id"] for p in programs for s in p["sources"]}
    done |= pending - in_programs
    for k in done & pending:
        cache[k]["synced"] = True
    save_cache(cache, CACHE_PATH)


if __name__ == "__main__":
    main()
