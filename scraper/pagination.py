"""URL helpers for paginated search results.

Both OLX and Dom.ria use the same convention: append `?page=N` to the base
search URL (preserving any existing query parameters). Centralised here so
each source doesn't reinvent it.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def page_url(base_url: str, page: int) -> str:
    """Return `base_url` with `page` parameter set (1-based).

    Page 1 keeps the original URL unchanged (most sites canonicalise that).
    """
    if page <= 1:
        return base_url
    parsed = urlparse(base_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(params)))
