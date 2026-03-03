import cloudscraper
from config import IDX_API_URL, IDX_PAGE_URL, KEYWORD

_scraper = cloudscraper.create_scraper()
_scraper.headers.update({
    "Referer": IDX_PAGE_URL,
})


def fetch_announcements() -> list[dict]:
    """Fetch announcements from the IDX API (Cloudflare-protected)"""
    params = {
        "keywords": KEYWORD,
        "pageNumber": 1,
        "pageSize": 20,
        "lang": "en",
    }
    resp = _scraper.get(IDX_API_URL, params=params, timeout=15)
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
