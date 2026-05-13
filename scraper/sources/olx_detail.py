"""OLX detail-page enrichment via Playwright (Chromium).

The OLX **catalog** page uses SSR with `__PRERENDERED_STATE__`, so we scrape
it with plain `requests` (see sources/olx.py). The **detail** page is
client-rendered — the HTML returned to a bare HTTP client is an empty React
shell. Hence Playwright.

Extracted extras:
    description_full   — full description text (catalog one may be truncated)
    photos_full        — all gallery image URLs (catalog had only 6)
    posted_at_text     — human-readable posting time as shown to users
"""

from __future__ import annotations

from typing import Final, TypedDict

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, TimeoutError as PlaywrightTimeout


class OlxDetail(TypedDict):
    description_full: str | None
    photos_full: list[str]
    posted_at_text: str | None


_PHOTO_TESTIDS: Final[tuple[str, ...]] = ("swiper-image", "swiper-image-lazy", "ad-photo")


def _parse_detail_html(html: str) -> OlxDetail:
    soup = BeautifulSoup(html, "lxml")

    description_full: str | None = None
    if desc_el := soup.find(attrs={"data-testid": "ad_description"}):
        description_full = desc_el.get_text(separator="\n", strip=True) or None

    posted_at_text: str | None = None
    if posted_el := soup.find(attrs={"data-testid": "ad-posted-at"}):
        posted_at_text = posted_el.get_text(strip=True) or None

    photos: list[str] = []
    seen: set[str] = set()
    for testid in _PHOTO_TESTIDS:
        for el in soup.find_all(attrs={"data-testid": testid}):
            src = el.get("src") or el.get("data-src")
            if isinstance(src, str) and src.startswith("http") and src not in seen:
                seen.add(src)
                photos.append(src)

    return OlxDetail(
        description_full=description_full,
        photos_full=photos,
        posted_at_text=posted_at_text,
    )


async def fetch_detail(context: BrowserContext, url: str) -> OlxDetail:
    """Fetch and parse one OLX listing detail page.

    We don't reuse `fetch_rendered_html` because we need to explicitly wait
    for the description block — `networkidle` returns before all React
    hydration completes for content below the fold.
    """
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        try:
            await page.wait_for_function(
                """() => {
                    const el = document.querySelector('[data-testid="ad_description"]');
                    return el && el.innerText.trim().length > 20;
                }""",
                timeout=10_000,
            )
        except PlaywrightTimeout:
            # Description didn't hydrate in time — return whatever rendered.
            pass
        html = await page.content()
    finally:
        await page.close()
    return _parse_detail_html(html)
