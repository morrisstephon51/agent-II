"""
Scraper layer: Granted public API, NSF SBIR JSON API, httpx + BeautifulSoup4.
No paid services required.
"""
import re
import sys
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .config import GRANTED_QUERIES, MAX_GRANT_AGE_DAYS, SCRAPE_TARGETS
from .models import Grant

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GrantAgent/1.0; +https://github.com/morrisstephon51/agent-ii)"
    )
}

_DATE_PATTERNS = [
    "%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y",
]


def _parse_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _parse_amount(raw) -> Optional[int]:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


# ---------------------------------------------------------------------------
# Granted public API (free, no key required)
# ---------------------------------------------------------------------------

GRANTED_API_BASE = "https://api.granted.fyi/v1"


def _fetch_granted_query(query: str) -> list[Grant]:
    grants: list[Grant] = []
    try:
        r = httpx.get(
            f"{GRANTED_API_BASE}/grants/search",
            params={"q": query, "status": "open", "limit": 20},
            headers=_HEADERS,
            timeout=15,
        )
        if r.status_code != 200:
            return grants
        data = r.json()
        items = data if isinstance(data, list) else data.get("results", data.get("grants", []))
        for item in items:
            deadline = _parse_date(
                item.get("deadline") or item.get("close_date") or item.get("due_date", "")
            )
            grants.append(
                Grant(
                    title=item.get("title") or item.get("name", "Unknown"),
                    url=item.get("url") or item.get("link") or item.get("source_url", ""),
                    source=item.get("funder") or item.get("agency") or query,
                    description=(item.get("description") or item.get("summary", ""))[:800],
                    deadline=deadline,
                    award_min=_parse_amount(item.get("award_min") or item.get("min_amount", "")),
                    award_max=_parse_amount(
                        item.get("award_max") or item.get("max_amount") or item.get("amount", "")
                    ),
                )
            )
    except Exception as exc:
        print(f"[scraper] Granted query '{query}' failed: {exc}", file=sys.stderr)
    return grants


def fetch_granted() -> list[Grant]:
    grants: list[Grant] = []
    for q in GRANTED_QUERIES:
        grants.extend(_fetch_granted_query(q))
    return grants


# ---------------------------------------------------------------------------
# NSF SBIR public JSON API (free)
# ---------------------------------------------------------------------------

NSF_SBIR_API = "https://api.sbir.gov/public/api/solicitations"


def fetch_nsf_sbir() -> list[Grant]:
    grants: list[Grant] = []
    try:
        r = httpx.get(
            NSF_SBIR_API,
            params={"keyword": "artificial intelligence education", "open": "true", "rows": 20},
            headers=_HEADERS,
            timeout=15,
        )
        if r.status_code != 200:
            r = httpx.get("https://www.sbir.gov/api/solicitations/open", headers=_HEADERS, timeout=15)
        if r.status_code != 200:
            return grants
        data = r.json()
        items = data if isinstance(data, list) else data.get("results", [])
        for item in items:
            grants.append(
                Grant(
                    title=item.get("solicitation_title") or item.get("title", "NSF SBIR"),
                    url=item.get("solicitation_url") or item.get("url", "https://www.sbir.gov"),
                    source="NSF SBIR",
                    description=(item.get("program_description") or item.get("description", ""))[:800],
                    deadline=_parse_date(item.get("close_date") or item.get("deadline", "")),
                    award_min=_parse_amount(item.get("award_min", "")),
                    award_max=_parse_amount(item.get("award_max") or item.get("award_amount", "")),
                )
            )
    except Exception as exc:
        print(f"[scraper] NSF SBIR API failed: {exc}", file=sys.stderr)
    return grants


# ---------------------------------------------------------------------------
# httpx + BeautifulSoup4 scraper (free, no API key)
# ---------------------------------------------------------------------------

def _html_scrape(url: str) -> str:
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
        return r.text
    except Exception as exc:
        print(f"[scraper] httpx failed for {url}: {exc}", file=sys.stderr)
        return ""


def _extract_grants_from_html(html: str, source: str, source_url: str) -> list[Grant]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Remove nav/footer/script noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    # Deadline extraction
    deadline_match = re.search(
        r"(?:deadline|due|close[sd]?|apply by)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})",
        text, re.IGNORECASE,
    )
    deadline = _parse_date(deadline_match.group(1)) if deadline_match else None

    # Amount extraction
    award_max: Optional[int] = None
    amount_match = re.search(
        r"\$([\d,]+(?:\.\d+)?)\s*(million|M\b|thousand|K\b)?",
        text, re.IGNORECASE,
    )
    if amount_match:
        raw_val = amount_match.group(1).replace(",", "")
        suffix = (amount_match.group(2) or "").lower()
        multiplier = 1_000_000 if suffix in ("million", "m") else (1_000 if suffix in ("thousand", "k") else 1)
        try:
            award_max = int(float(raw_val) * multiplier)
        except ValueError:
            pass

    description = text[:600].strip()

    return [Grant(
        title=source,
        url=source_url,
        source=source,
        description=description,
        deadline=deadline,
        award_max=award_max,
    )]


def fetch_scraped_sources() -> list[Grant]:
    grants: list[Grant] = []
    for target in SCRAPE_TARGETS:
        if target.get("is_api"):
            continue
        source = target["source"]
        url = target["url"]
        html = _html_scrape(url)
        if not html:
            html = _html_scrape(target.get("fallback_url", url))
        extracted = _extract_grants_from_html(html, source, url)
        grants.extend(extracted)
        print(f"[scraper] {source}: {len(extracted)} candidate(s) found")
    return grants


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_all() -> list[Grant]:
    print("[scraper] Fetching from Granted database...")
    all_grants = fetch_granted()

    print("[scraper] Fetching NSF SBIR API...")
    all_grants.extend(fetch_nsf_sbir())

    print("[scraper] Scraping direct sources...")
    all_grants.extend(fetch_scraped_sources())

    seen: set[str] = set()
    unique: list[Grant] = []
    for g in all_grants:
        key = g.url.rstrip("/").lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(g)

    fresh = [g for g in unique if g.is_recent(MAX_GRANT_AGE_DAYS)]
    print(f"[scraper] {len(fresh)} fresh grants after dedup + age filter (from {len(all_grants)} raw)")
    return fresh
