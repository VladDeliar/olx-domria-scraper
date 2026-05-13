"""Playwright (Chromium) helper for JS-rendered pages.

`fetch_rendered_html(url)` opens a headless browser, navigates, waits for
network to settle, returns the rendered HTML. Reuses a single browser
process across calls via the `browser_context` async context manager —
launching a fresh Chromium per URL is 1–2 sec of overhead each time.

Cost model: a browser fetch is ~5–20x slower than `requests.get`. Use it
only when the page genuinely needs JS to expose data, not as a default.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from playwright.async_api import Browser, BrowserContext, async_playwright

_DEFAULT_TIMEOUT_MS: Final[int] = 20_000

# Fixed desktop Chrome UA. fake_useragent's random pool includes mobile UAs,
# which makes OLX server a mobile page with a different DOM (no
# `data-testid="ad_description"`). Pinning desktop guarantees consistent
# rendering for detail-page parsing.
_DESKTOP_UA: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@asynccontextmanager
async def browser_context(*, headless: bool = True) -> AsyncIterator[BrowserContext]:
    """Yield a fresh Playwright BrowserContext, cleaning up on exit."""
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=_DESKTOP_UA,
            locale="uk-UA",
            viewport={"width": 1280, "height": 800},
        )
        try:
            yield context
        finally:
            await context.close()
            await browser.close()


async def fetch_rendered_html(
    context: BrowserContext,
    url: str,
    *,
    wait_until: str = "networkidle",
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> str:
    """Open `url` in a new page and return its rendered HTML."""
    page = await context.new_page()
    try:
        await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        return await page.content()
    finally:
        await page.close()
