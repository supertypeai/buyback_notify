"""Fetch IDX share-buyback announcements and extract structured data from their PDFs.

IDX sits behind Cloudflare, so requests go through curl_cffi with a Chrome
TLS fingerprint (plus PROXY_URL when set). Each announcement's PDFs are sent
to an OpenRouter model that reads PDFs natively (handles scanned documents).
"""

import base64
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from curl_cffi import requests as cffi_requests

from buyback_guards import SOFT_ISSUE_PREFIX, check, fix_scale, pdf_text, pdf_text_partial, repair

IDX_API_URL = "https://www.idx.co.id/primary/NewsAnnouncement/GetAllAnnouncement"
SEARCH_KEYWORDS = ["buyback", "buy back", "repurchase", "treasury", "pembelian kembali"]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.8-flash")
# Stronger model used only when the primary model's output fails the guards
FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "~deepseek/deepseek-flash-latest")
MAX_PDF_BYTES = 15 * 1024 * 1024
REQUEST_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "120"))
# Bump when the prompt/guards change so cached extractions are redone
EXTRACTION_VERSION = 4

# Titles that are never about a company buying back its own shares
_EXCLUDE_TITLE = re.compile(
    r"report of shares transfer from shares buy ?back"
    r"|bond|sukuk|debt securities|tier 1|\bAT1\b|repurchase agreement|\(repo\)"
    # Repurchases the law forces on the company (dissenting shareholders, delisting) are not programs
    r"|article 62|pasal 62|delisting|go private|cancel the listing"
    r"|dissent|do not approve|tidak setuju|merger|spin.?off",
    re.IGNORECASE,
)


def excluded_title(title: str) -> bool:
    return bool(_EXCLUDE_TITLE.search(" ".join(title.split())))

_proxy = os.getenv("PROXY_URL", "")
_session = cffi_requests.Session(
    impersonate="chrome",
    proxies={"http": _proxy, "https": _proxy} if _proxy else None,
    # The proxy re-signs HTTPS with its own certificate, so verification fails through it
    verify=not _proxy,
)


def _get(url: str, params: dict | None = None, retries: int = 6):
    for attempt in range(retries):
        try:
            resp = _session.get(url, params=params, timeout=60)
            if resp.status_code == 200:
                return resp
            print(f"  HTTP {resp.status_code} for {url}")
        except Exception as e:  # curl timeouts, resets
            print(f"  {type(e).__name__} for {url}: {e}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}")


def fetch_buyback_announcements(date_from: str, date_to: str) -> list[dict]:
    """All buyback-related announcements published between two YYYYMMDD dates."""
    found = {}
    for kw in SEARCH_KEYWORDS:
        page = 1
        while True:
            data = _get(IDX_API_URL, {
                "keywords": kw, "pageNumber": page, "pageSize": 100, "lang": "en",
                "dateFrom": date_from, "dateTo": date_to,
            }).json()
            for item in data.get("Items") or []:
                found.setdefault(item["Id"], item)
            if page >= (data.get("PageCount") or 1):
                break
            page += 1
            time.sleep(2)
        time.sleep(2)

    announcements = []
    for item in found.values():
        title = " ".join((item.get("Title") or "").split())
        if _EXCLUDE_TITLE.search(title):
            continue
        announcements.append({
            "id": item["Id"],
            "symbol": (item.get("Code") or "").strip(),
            "publish_date": item.get("PublishDate") or "",
            "title": title,
            "attachments": [
                {"url": a["FullSavePath"], "filename": a.get("OriginalFilename") or a["PDFFilename"]}
                for a in item.get("Attachments") or []
                if a.get("FullSavePath")
            ],
        })
    announcements.sort(key=lambda a: a["publish_date"])
    return announcements


def local_pdf_path(announcement: dict, attachment: dict, pdf_dir: str) -> str:
    name = re.sub(r"[^\w.\-]+", "_", attachment["filename"])
    return os.path.join(pdf_dir, announcement["symbol"] or "UNKNOWN", name)


def download_pdfs(announcement: dict, pdf_dir: str) -> list[str]:
    """Download an announcement's attachments into pdf_dir/<SYMBOL>/, skipping existing files."""
    paths = []
    for att in announcement["attachments"]:
        path = local_pdf_path(announcement, att, pdf_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(_get(att["url"]).content)
            time.sleep(1)
        paths.append(path)
    return paths


_PROMPT = """\
You extract structured data from Indonesia Stock Exchange (IDX) disclosures about share buybacks
("pembelian kembali saham"). Documents are often bilingual Indonesian/English; the first PDF is
usually the IDX e-reporting cover form and the rest are the company's letter and attachments
(attachments may be scanned or rotated - read them carefully). If the cover form and the attached
letter disagree, trust the attached letter/table.

Announcement title: {title}
Issuer code: {symbol}
Published: {publish_date}

Return ONLY a JSON object with these keys:
{{
  "is_share_buyback": true if the document is about the company buying back ITS OWN listed shares
      (a plan, a correction/amendment of a plan, a progress or realization report, or a completion /
      termination notice). false if it is only about transferring, selling, distributing or
      withdrawing treasury shares, buying back bonds/sukuk/other securities, buying shares of a
      different company, or does not concern a buyback at all. Also false for repurchases the company
      is obliged to make: from shareholders who voted against a merger, spin-off or other action
      (Article/Pasal 62 of Law 40/2007, "pemegang saham yang tidak setuju") or because of a delisting
      or go-private - these are not buyback programs.
  "doc_type": one of "plan", "plan_update", "progress_report", "final_report", "termination", "other".
      Use "final_report" when it reports results for the whole buyback period, "termination" for a
      notice that the buyback ended/was stopped early (it may also include results).
  "symbol": 4-letter IDX ticker of the company buying back its shares,
  "mandate_start_date": first day the buyback may be executed (YYYY-MM-DD) or null,
  "mandate_end_date": last day of the buyback period (YYYY-MM-DD) or null. If the document says the
      buyback was terminated/ended early, use the actual end date.
  "allocated_fund": maximum IDR budget for the buyback program (number) or null,
  "max_shares": maximum number of shares to be bought back, or null,
  "report_as_of_date": date through which reported purchases are counted (YYYY-MM-DD) or null,
  "transactions": purchases of the CURRENT program disclosed in this document, in the same order as
      the document. One item per trading day:
      {{"date": "YYYY-MM-DD", "share_amount": shares bought that day,
        "average_price": average IDR price per share that day,
        "percentage_of_shares": that day's shares as a percent of ISSUED/LISTED shares if the column
            means that (null if the column is a percent of the planned buyback or not given),
        "value": the IDR amount printed for that day's row, or null,
        "remaining_budget": the "sisa biaya/dana" (remaining budget) printed after that row, or null}}
      If a day has several rows (one per price level), sum the shares into one item and use the
      share-weighted average price; value/remaining_budget are then the day's totals/last value.
      If only a total is given, a single item with "date": null and the totals.
      Empty list for plans with no purchases yet.
  "stated_total_shares": the TOTAL shares bought for the current program exactly as printed in the
      document (e.g. the "Jumlah/Total" row), or null if no total is printed,
  "stated_total_value": the total IDR amount printed for the current program, or null,
  "remaining_budget": the latest remaining budget printed for the current program, or null,
  "accumulated_shares_purchased": total shares bought under THIS program as of report_as_of_date, or null,
  "utilized_fund": total IDR spent under THIS program as of report_as_of_date. If not printed but the
      budget and remaining budget are, use budget - remaining. Otherwise null,
  "previous_programs": if the document ALSO summarises earlier, separate buyback periods (e.g. a
      half-year recap covering several successive programs), list them here as
      {{"start_date", "end_date", "total_shares", "total_value"}} and DO NOT put their daily rows in
      "transactions". Otherwise [],
  "notes": one short sentence on anything ambiguous or inconsistent in the document, else ""
}}

Date rules: tables often write dates as dd-Mon-yy ("01-Apr-26" = 2026-04-01, "15-Jan-26" = 2026-01-15)
or dd/mm/yyyy ("06/04/2026" = 2026-04-06). Trades can never be dated after the publish date. If the
document has an obvious year typo (e.g. "02-Jan-25" between Dec 2025 and Jan 2026 rows) use the
correct year and say so in notes.
Number rules: Indonesian formatting uses "." for thousands and "," for decimals ("1.069" = 1069,
"3.884,18" = 3884.18). Return plain JSON numbers in full units: "Rp1,5 triliun" = 1500000000000,
"Rp200 miliar" = 200000000000, "Rp 50 juta" = 50000000. Percentages as percent values (0.26 means 0.26%).
Use null for anything not stated; never guess.
"""

_RETRY = """\
Your previous answer failed these automatic consistency checks:
{problems}

Re-read the relevant parts of the documents (especially the transaction table) and return the full
corrected JSON object. If after re-reading the document itself is inconsistent (e.g. its printed total
does not equal the sum of its rows), keep the values exactly as printed and explain in "notes".
"""


def _openrouter_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY ")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return key.strip()


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0) if m else text)
    # Some models wrap the object in a list
    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object, got {type(data).__name__}")
    return data


_MODALITIES: dict[str, list[str]] = {}
_PDFIUM_LOCK = threading.Lock()  # pdfium is not thread-safe


def _input_modalities(model: str) -> list[str]:
    """What the model accepts per OpenRouter's catalogue (cached)."""
    if not _MODALITIES:
        try:
            for m in requests.get("https://openrouter.ai/api/v1/models", timeout=60).json()["data"]:
                _MODALITIES[m["id"]] = m.get("architecture", {}).get("input_modalities") or []
        except Exception:
            pass
    return _MODALITIES.get(model, ["file"])


def _pdf_parts(pdf_paths: list[str], model: str = OPENROUTER_MODEL) -> list[dict]:
    """PDFs as native file parts, or as page images for vision models without PDF support."""
    as_images = "file" not in _input_modalities(model) and "image" in _input_modalities(model)
    parts = []
    for path in pdf_paths:
        if os.path.getsize(path) > MAX_PDF_BYTES:
            continue
        if as_images:
            parts.extend(_page_images(path))
            continue
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        parts.append({
            "type": "file",
            "file": {"filename": os.path.basename(path), "file_data": f"data:application/pdf;base64,{b64}"},
        })
    # Without document parts the model only sees the title and returns a plausible but empty extraction
    if not parts:
        raise RuntimeError(f"no readable document content for {model} in {pdf_paths}")
    return parts


def _page_images(path: str, max_pages: int = 12, scale: float = 1.6) -> list[dict]:
    """Render PDF pages to JPEG (~115 dpi; enough for scanned tables, small token count)."""
    import io
    import pypdfium2 as pdfium
    import PIL  # noqa: F401  to_pil() needs Pillow, which pypdfium2 does not install; fail loudly, not per page

    parts = []
    with _PDFIUM_LOCK:
        try:
            pdf = pdfium.PdfDocument(path)
            images = [pdf[i].render(scale=scale).to_pil().convert("L") for i in range(min(len(pdf), max_pages))]
            pdf.close()
        except Exception as e:  # a corrupt or encrypted PDF; the announcement's other PDFs may still be readable
            print(f"  cannot render {path}: {type(e).__name__}: {e}")
            return parts
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        parts.append({"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}})
    return parts


def _chat(model: str, messages: list[dict]) -> tuple[dict, str, float]:
    body = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}],
        "usage": {"include": True},
    }
    headers = {"Authorization": f"Bearer {_openrouter_key()}"}
    last_err = None
    for attempt in range(2):
        try:
            resp = requests.post(OPENROUTER_URL, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code in ProviderError.STATUSES:
                # Out of credit / bad or disabled key: retrying can't help, and every document will fail
                raise ProviderError(resp.status_code, f"{model}: HTTP {resp.status_code} {resp.text[:200]}")
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            return _parse_json(raw), raw, float((data.get("usage") or {}).get("cost") or 0)
        except ProviderError:
            raise
        except Exception as e:
            last_err = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{model}: {last_err}")


class ProviderError(RuntimeError):
    """OpenRouter refused the account or key (no credit, invalid or disabled key). Systemic, not per-document."""
    STATUSES = (401, 402, 403)

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def extract_announcement(announcement: dict, pdf_paths: list[str], model: str = OPENROUTER_MODEL,
                         feedback_rounds: int = 1, text: str | None = None) -> dict:
    """One model: extract, run guards, and feed failures back for up to `feedback_rounds` retries."""
    messages = [{"role": "user", "content": [{"type": "text", "text": _PROMPT.format(**announcement)},
                                             *_pdf_parts(pdf_paths, model)]}]
    text = pdf_text(pdf_paths) if text is None else text
    partial = pdf_text_partial(pdf_paths)
    best, cost = None, 0.0
    for round_ in range(feedback_rounds + 1):
        ex, raw, c = _chat(model, messages)
        cost += c
        ex = fix_scale(ex, partial)
        problems = check(ex, announcement["publish_date"], text, partial)
        if best is None or len(problems) <= len(best["guard_issues"]):
            best = {"extraction": ex, "guard_issues": problems, "model": model, "rounds": round_ + 1}
        best["cost"] = cost
        if not problems:
            break
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": _RETRY.format(problems="\n".join(f"- {p}" for p in problems))}]
    return best


def extract_with_guards(announcement: dict, pdf_paths: list[str]) -> dict:
    """Primary model with guard feedback; escalate to FALLBACK_MODEL if checks still fail."""
    text = pdf_text(pdf_paths)
    try:
        result = extract_announcement(announcement, pdf_paths, OPENROUTER_MODEL, text=text)
    except Exception as e:
        # e.g. the primary model dropping the connection on a large PDF
        if not FALLBACK_MODEL:
            raise
        print(f"  {OPENROUTER_MODEL} failed for {announcement['id']}: {e}; using {FALLBACK_MODEL}")
        result = extract_announcement(announcement, pdf_paths, FALLBACK_MODEL, text=text)
        result["escalated_from"] = OPENROUTER_MODEL
        result["extraction"] = repair(result["extraction"])
        return _soften(result)
    if result["guard_issues"] and FALLBACK_MODEL and FALLBACK_MODEL != OPENROUTER_MODEL:
        try:
            alt = extract_announcement(announcement, pdf_paths, FALLBACK_MODEL, text=text)
        except Exception as e:  # keep the primary result if the fallback is unavailable
            print(f"  fallback {FALLBACK_MODEL} failed for {announcement['id']}: {e}")
            if isinstance(e, ProviderError):
                result["provider_error"] = str(e)
            alt = None
        if alt:
            total = result.get("cost", 0) + alt.get("cost", 0)
            if len(alt["guard_issues"]) < len(result["guard_issues"]):
                alt["escalated_from"] = OPENROUTER_MODEL
                result = alt
            result["cost"] = total
    result["extraction"] = repair(result["extraction"])
    return _soften(result)


def _soften(result: dict) -> dict:
    """Soft checks drive the retry and fallback above but don't block the program: some plans state
    only a percentage cap, or just shorten an existing program."""
    soft = [p for p in result["guard_issues"] if p.startswith(SOFT_ISSUE_PREFIX)]
    if soft:
        result["guard_issues"] = [p for p in result["guard_issues"] if p not in soft]
        result["soft_issues"] = soft
    return result


def load_cache(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)


def extract_all(announcements: list[dict], pdf_dir: str, cache_path: str,
                workers: int = int(os.getenv("BUYBACK_WORKERS", "8")), failures: list | None = None) -> dict:
    """Download + extract every announcement not already in the cache. Returns the full cache.
    OpenRouter account/key errors are appended to `failures` so the caller can fail the run after
    syncing what it could; per-document errors (corrupt PDF, unreadable pages) are only logged."""
    failures = [] if failures is None else failures
    cache = load_cache(cache_path)
    todo = [a for a in announcements
            if a["id"] not in cache or cache[a["id"]].get("version") != EXTRACTION_VERSION]
    print(f"  {len(announcements) - len(todo)} cached, {len(todo)} to extract")

    for a in todo:
        a["pdf_paths"] = download_pdfs(a, pdf_dir)

    def work(a):
        return a, extract_with_guards(a, a["pdf_paths"])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, a) for a in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                a, result = fut.result()
            except ProviderError as e:
                print(f"  ! {e}")
                failures.append(str(e))
                continue
            except Exception as e:
                print(f"  ! {e}")
                continue
            if result.get("provider_error"):
                failures.append(result["provider_error"])
            ex = result["extraction"]
            cache[a["id"]] = {
                "announcement": {k: v for k, v in a.items() if k != "pdf_paths"},
                **result,
                "version": EXTRACTION_VERSION,
                "synced": False,  # set True by buyback_sync once its program row is written
            }
            flag = f" ! {len(result['guard_issues'])} guard issue(s)" if result["guard_issues"] else ""
            print(f"  [{n}/{len(todo)}] {a['symbol']} {a['publish_date'][:10]} {ex.get('doc_type')} "
                  f"buyback={ex.get('is_share_buyback')} model={result['model']}{flag}")
            save_cache(cache, cache_path)  # after every document, so an interrupted run loses nothing

    save_cache(cache, cache_path)
    return cache
