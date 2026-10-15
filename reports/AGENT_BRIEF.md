# Buyback audit: verify idx_buybacks against IDX filings

You are auditing a Supabase table `idx_buybacks` of Indonesian (IDX) share buyback programs against
the original company filings. Accuracy matters more than speed: every number you report must come
from a filing you actually read, with the filing cited. If you cannot establish a value, say so
(null + note) instead of guessing.

## Inputs (all local, read-only, do NOT fetch anything from the internet)
Base dir: `C:\Users\emirsyah\AppData\Local\Temp\claude\C--Users-emirsyah-Documents-CODING-supertype-buyback-notify\05c3f782-e44f-4d68-9a25-c3134a17d540\scratchpad\audit`
- `docs/<SYMBOL>/index.json`: the company's buyback-related filings since Jan 2025 (published date, title, files).
- `docs/<SYMBOL>/*.txt`: text of each PDF (liteparse, no OCR). If a .txt is nearly empty or garbled the PDF is
  scanned; then use the Read tool on the matching `.pdf` (it renders pages; use `pages` for long ones).
  `*_main.pdf` is the IDX e-reporting cover form, `*_att.pdf` are the company's letters/attachments, which
  usually hold the actual figures. Filings are bilingual Indonesian/English.
- `snapshot.json`: current DB rows (JSON list). Fields: symbol ("XXXX.JK"), mandate {start_date, end_date},
  transaction_details [{date, share_amount, average_price, percentage_of_shares}], company_fund
  [{utilized_fund, allocated_fund}], accumulated_shares_purchased, registry_updates (monthly treasury
  shares from a separate reliable source; may be null).

## Domain rules
- Two regimes. **Shareholder-approved** (POJK 29/2023): period up to 12 months after the GMS (RUPS),
  half-yearly cumulative reports (as of 30 Jun / 31 Dec). **Fluctuating-market** (POJK 13/2023,
  "kondisi pasar yang berfluktuasi secara signifikan"): no GMS, period up to 3 months from disclosure.
- A program = one plan (plus its corrections/updates). Progress, realization, final and termination
  reports attach to it. A termination/early completion shortens the period: end_date = actual end date.
- NOT buyback programs (never a row): transfers/sales/cancellation of treasury shares, bond/sukuk/AT1
  repurchases, buying another company's shares, repurchases forced by Article 62 Company Law (appraisal
  rights for shareholders who voted against a merger/spin-off/delisting), delisting/go-private tender offers.
- Indonesian numbers: "." thousands, "," decimals. "Rp1,5 triliun" = 1,500,000,000,000; "miliar" = 1e9; "juta" = 1e6.
- Scope: only programs whose period overlaps 2026 (end_date >= 2026-01-01). Ignore programs that ended in 2025.
- A plan "pending GMS approval" with no dates yet: report it with null dates and note it.

## Task for each SYMBOL in your batch
1. Read index.json and the relevant filings (plans, corrections, reports, terminations).
2. List every in-scope program with: start_date, end_date (actual, after any termination), regime,
   allocated_fund (IDR, max budget), max_shares (if stated), and the latest officially reported totals:
   shares bought, IDR spent, and the as-of date, each with its source filing.
3. For each existing DB row of that symbol, compare field by field with what the filings say:
   mandate dates, allocated_fund, utilized_fund, accumulated_shares_purchased, and the SUM of
   transaction_details share_amount (do not check rows one by one; but do report trades dated outside the
   period or obviously wrong years). Note: accumulated_shares_purchased may legitimately come from
   registry_updates (latest minus baseline) when the company published no total; then it is not an error
   unless a filing contradicts it.
4. Programs in the filings with no DB row = "missing". DB rows that match no real program = "delete".

## Output
Write ONE JSON file: `results/<your batch name>.json` (create the folder if needed) with this shape, and
end your final message with the path and a 3-line summary.

```json
{"batch": "b01", "symbols": [
  {"symbol": "ABCD",
   "programs": [
     {"start_date": "2026-03-09", "end_date": "2026-07-06", "regime": "gms|fluctuating|unknown",
      "allocated_fund": 905480000000, "max_shares": null,
      "reported_shares": 77856100, "reported_spent": null, "reported_as_of": "2026-07-06",
      "status": "ended|terminated|active|pending_gms",
      "sources": ["2026-07-06 Termination and Completion of the 2026 Share Buyback (att p.1)"],
      "db_row": {"start_date": "2026-03-09", "end_date": "2027-03-08"},
      "verdict": "verified|correct|delete|missing|uncertain",
      "corrections": {"mandate.end_date": "2026-07-06"},
      "notes": "short, factual"}
   ],
   "unmatched_db_rows": [{"start_date": "...", "end_date": "...", "verdict": "delete", "reason": "..."}],
   "not_a_buyback": "fill only if the symbol has no real in-scope program, with the reason"}
]}
```
Verdicts: `verified` = DB row matches filings; `correct` = DB row exists but fields need the listed
`corrections` (use dotted field names: mandate.start_date, mandate.end_date, company_fund.allocated_fund,
company_fund.utilized_fund, accumulated_shares_purchased, transaction_details[date=YYYY-MM-DD].date, ...);
`missing` = real program with no DB row; `delete` = DB row is not a real program or a duplicate;
`uncertain` = filings insufficient or contradictory (explain in notes).
Only put a value in `corrections` when a filing states it; registry-derived values are not corrections.
