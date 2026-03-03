import requests
import urllib3
from config import IDX_API_URL, IDX_PAGE_URL, KEYWORD, PROXY_URL

# Suppress SSL warnings that come with verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": IDX_PAGE_URL,
}

_PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None


def fetch_announcements() -> list[dict]:
    """Fetch announcements from the IDX API via proxy with browser-like headers."""
    params = {
        "keywords": KEYWORD,
        "pageNumber": 1,
        "pageSize": 20,
        "lang": "en",
    }

    resp = requests.get(
        IDX_API_URL,
        params=params,
        headers=_HEADERS,
        proxies=_PROXIES,
        timeout=15,
        verify=False,  # disables SSL cert check
    )
    resp.raise_for_status()
    data = resp.json()

    items = data.get("Items") or data.get("Results") or []

    announcements = []
    for item in items:
        title = item.get("Title") or ""
        date = item.get("PublishDate") or item.get("Date") or ""
        code = item.get("Code") or ""

        # Build a link to the PDF attachment if available
        attachments = item.get("Attachments") or []
        link = ""
        if attachments:
            path = attachments[0].get("FullSavePath") or ""
            if path:
                link = path if path.startswith("http") else "https://www.idx.co.id" + path

        ann_id = item.get("Id") or title

        announcements.append(
            {
                "id": str(ann_id),
                "title": title,
                "date": date,
                "company": code,
                "link": link,
            }
        )

    print(f"  Fetched {len(announcements)} announcements via API.")
    return announcements


def filter_keyword(announcements: list[dict], keyword: str) -> list[dict]:
    """Return announcements whose title contains keyword (case-insensitive)"""
    kw = keyword.lower()
    return [a for a in announcements if kw in a["title"].lower()]
