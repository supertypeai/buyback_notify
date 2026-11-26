"""Shared IDX fetcher: the same ladder the other IDX scrapers run.

Cloudflare fingerprints the caller: plain requests gets a challenge page (HTML, HTTP 403 or
200), and which browser fingerprint passes rotates every few days. So try plain first, then
each TLS fingerprint, proxy route before direct, in rounds.

Same shape as `idx_fetch.py` in sectors_idx_profile_updater / sectors_indices_company_list /
sectors_idx_suspension, and the inline ladder in sectors_idx_daily_data. Difference here:
a fresh session per attempt (closed in `finally`), so a session that Cloudflare has poisoned
cannot be reused for the rest of the run, and `params` are passed straight to the request.

kind: json -> body starts with "{"     raw -> any non-empty, non-challenge body (pdf, xlsx)
"""

import os
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FINGERPRINTS = ["firefox133", "tor145", "safari17_0", "safari17_2_ios"]
ROUNDS = 3
BACKOFF_SECONDS = 60
TIMEOUT = (10, 60)
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.idx.co.id/en/news/announcement",
}
# The impersonated client sets its own User-Agent; keep ours from overriding it
_FINGERPRINT_HEADERS = {k: v for k, v in HEADERS.items() if k.lower() != "user-agent"}

PROXY_URL = os.getenv("PROXY_URL", "")
_PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None


class IdxBlocked(RuntimeError):
    """Every route returned a challenge page or failed; nothing usable came back."""


def _challenge(content: bytes) -> bool:
    """Cloudflare's interstitial arrives as HTML with either 403 or 200."""
    head = content[:300].lstrip().lower()
    return head.startswith(b"<") and (b"<html" in head or b"just a moment" in head)


def _looks_right(content: bytes, kind: str) -> bool:
    if kind == "json":
        return content.lstrip().startswith(b"{")
    if kind == "raw":
        return bool(content) and not _challenge(content)
    raise ValueError(f"unknown kind {kind!r}, expected json|raw")


def _plain(url, params, kind, timeout):
    """Plain requests with retries on 429/5xx: cheap first rung, sometimes enough."""
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])))
    session.verify = False  # the proxy re-signs HTTPS with its own certificate
    session.trust_env = False
    try:
        response = session.get(url, params=params, headers=HEADERS, proxies=_PROXIES, timeout=timeout)
        response.raise_for_status()
        if not _looks_right(response.content, kind):
            raise ValueError(f"non-{kind} body (HTTP {response.status_code}) - challenge page")
        return response.content
    finally:
        session.close()


def idx_get(url: str, kind: str = "json", params: dict | None = None, rounds: int = ROUNDS) -> bytes:
    """GET an IDX url, plain requests first, then each browser TLS fingerprint."""
    tried = []
    try:
        return _plain(url, params, kind, TIMEOUT)
    except Exception as error:
        tried.append(f"plain: {type(error).__name__}: {str(error)[:80]}")

    from curl_cffi import requests as cffi_requests

    routes = [_PROXIES, None] if _PROXIES else [None]
    for round_no in range(1, rounds + 1):
        for fingerprint in FINGERPRINTS:
            for route in routes:
                where = "proxy" if route else "direct"
                session = cffi_requests.Session(impersonate=fingerprint, proxies=route, verify=not route)
                try:
                    response = session.get(url, params=params, headers=_FINGERPRINT_HEADERS, timeout=TIMEOUT)
                    if response.status_code == 200 and _looks_right(response.content, kind):
                        return response.content
                    tried.append(f"{fingerprint}/{where}: HTTP {response.status_code}")
                except Exception as error:  # curl timeouts, resets, TLS errors
                    tried.append(f"{fingerprint}/{where}: {type(error).__name__}: {str(error)[:40]}")
                finally:
                    session.close()
        if round_no < rounds:
            time.sleep(BACKOFF_SECONDS * round_no)

    raise IdxBlocked(f"IDX blocked every route for {url} ({'; '.join(tried[-6:])})")
