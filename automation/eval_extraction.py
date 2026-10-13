"""Compare extraction models on announcements with manually verified answers
(see reports/buyback_extraction_verification.md). Needs the PDFs in output/pdfs (run a backfill first).

usage (from the repo root): python automation/eval_extraction.py <rounds> model1 [model2 ...]
  rounds=0 -> raw model output, rounds=1 -> one guard-feedback retry
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

here = os.path.dirname(os.path.abspath(__file__))
repo = os.path.dirname(here)
rounds, models = int(sys.argv[1]), sys.argv[2:]
sys.path.insert(0, here)
os.chdir(repo)
from dotenv import load_dotenv; load_dotenv(os.path.join(repo, ".env"))
from buyback_extract import extract_announcement, local_pdf_path
from buyback_guards import pdf_text

cache = json.load(open("data/buyback_extractions.json"))


def find(sym, d, title_part=""):
    for e in cache.values():
        a = e["announcement"]
        if a["symbol"] == sym and a["publish_date"].startswith(d) and title_part.lower() in a["title"].lower():
            return a
    raise KeyError((sym, d, title_part))


def tx(ex): return ex.get("transactions") or []
def ssum(ex): return sum((t.get("share_amount") or 0) for t in tx(ex))
def row(ex, date): return next((t for t in tx(ex) if t.get("date") == date), {})
def near(a, b, tol=0.001): return a is not None and b is not None and abs(float(a) - float(b)) <= tol * abs(float(b))


CASES = [
    ("JRPT", "2026-04-14", "results", {
        "date 01-Apr-26 read as 2026-04-01": lambda e: row(e, "2026-04-01").get("share_amount") == 263500,
        "no 2026-01-01 row": lambda e: not row(e, "2026-01-01"),
        "rows sum 11,394,700": lambda e: ssum(e) == 11394700,
    }),
    ("JRPT", "2026-01-14", "results", {
        "2026-01-02 = 82,800 shares": lambda e: row(e, "2026-01-02").get("share_amount") == 82800,
        "rows sum 22,401,400": lambda e: ssum(e) == 22401400,
    }),
    ("WINS", "2026-01-14", "", {
        "2025-12-23 price 480": lambda e: row(e, "2025-12-23").get("average_price") == 480,
        "60 rows sum 50,181,500": lambda e: len(tx(e)) == 60 and ssum(e) == 50181500,
    }),
    ("INTP", "2026-04-07", "implementation report", {
        "no trade after 2026-04-07": lambda e: all((t.get("date") or "") <= "2026-04-07" for t in tx(e)),
        "rows sum 66,249,700": lambda e: ssum(e) == 66249700,
    }),
    ("JRPT", "2026-01-12", "", {
        "current-program rows only (sum 18,586,600)": lambda e: ssum(e) == 18586600,
        "earlier programs listed separately": lambda e: {p.get("total_shares") for p in e.get("previous_programs") or []} >= {23331700, 26890200},
    }),
    ("PRDA", "2026-09-04", "", {
        "11 rows sum 5,021,700": lambda e: len(tx(e)) == 11 and ssum(e) == 5021700,
        "utilized = 13,113,694,550 (budget - remaining)": lambda e: near(e.get("utilized_fund"), 13113694550),
    }),
    ("ASLC", "2026-05-13", "realization", {
        "7 rows exact": lambda e: [(t.get("date"), t.get("share_amount")) for t in tx(e)] == [
            ("2026-01-12", 25000000), ("2026-01-13", 5347200), ("2026-04-06", 4140400), ("2026-04-07", 8728600),
            ("2026-04-08", 269000), ("2026-05-07", 6330000), ("2026-05-08", 6670000)],
    }),
    ("ERAA", "2026-04-27", "", {
        "rows sum 224,554,300": lambda e: ssum(e) == 224554300,
        "utilized 88,480,335,800": lambda e: near(e.get("utilized_fund"), 88480335800, 0.00001),
    }),
    ("BEEF", "2026-08-19", "result", {
        "rows sum 52,588,600 (rows as printed)": lambda e: ssum(e) == 52588600,
    }),
    ("DEWA", "2026-02-13", "realization", {
        "accumulated 1,638,793,874": lambda e: e.get("accumulated_shares_purchased") == 1638793874,
        "utilized 949,999,969,885": lambda e: near(e.get("utilized_fund"), 949999969885, 0.00001),
    }),
]


def run(model, case):
    sym, d, tp, checks = case
    a = find(sym, d, tp)
    paths = [local_pdf_path(a, att, "output/pdfs") for att in a["attachments"]]
    t0 = time.time()
    try:
        res = extract_announcement(a, paths, model, feedback_rounds=rounds, text=pdf_text(paths))
        ex = res["extraction"]
        passed = {k: bool(f(ex)) for k, f in checks.items()}
        return model, sym, d, passed, len(res["guard_issues"]), res["rounds"], round(time.time() - t0), res.get("cost", 0)
    except Exception as e:
        return model, sym, d, {k: False for k in checks}, -1, 0, f"ERR {e}"[:80], 0


from concurrent.futures import as_completed

jobs = [(m, c) for m in models for c in CASES]
results = []
with ThreadPoolExecutor(12) as pool:
    for fut in as_completed([pool.submit(run, *j) for j in jobs]):
        r = fut.result()
        results.append(r)
        model, sym, d, passed, gi, rnds, secs, cost = r
        print(f"{model:32} {sym} {d}  {sum(passed.values())}/{len(passed)}  guard_issues={gi} rounds={rnds} "
              f"{secs}s ${cost:.4f}  " + "; ".join(f"{'✓' if v else '✗'} {k}" for k, v in passed.items()), flush=True)

out = {}
for model, sym, d, passed, gi, rnds, secs, cost in results:
    out.setdefault(model, [0, 0, 0.0, 0])
    out[model][0] += sum(passed.values()); out[model][1] += len(passed)
    out[model][2] += cost; out[model][3] += 1 if gi >= 0 else 0
print()
for m, (p, n, c, ok) in out.items():
    print(f"SCORE {m:32} {p}/{n}   total ${c:.3f}   ≈ ${c / max(ok, 1):.4f} per announcement")
