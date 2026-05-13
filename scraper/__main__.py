"""Entry point: fetch one search page (OLX or Dom.ria) and print parsed listings.

    uv run python -m scraper olx    https://www.olx.ua/uk/nedvizhimost/kvartiry/kiev/
    uv run python -m scraper domria https://dom.ria.com/uk/arenda-kvartir/kiev/
"""

from __future__ import annotations

import sys
from typing import Protocol

from scraper.models import Listing
from scraper.sources import domria, olx


class _Source(Protocol):
    def fetch_search_page(self, url: str) -> str: ...
    def parse_search_page(self, html: str) -> list[Listing]: ...


_SOURCES: dict[str, _Source] = {"olx": olx, "domria": domria}


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in _SOURCES:
        print("usage: python -m scraper <olx|domria> <url>", file=sys.stderr)
        return 2
    source = _SOURCES[argv[1]]
    url = argv[2]
    print(f"Fetching ({argv[1]}): {url}")
    html = source.fetch_search_page(url)
    print(f"  -> {len(html):,} bytes")

    listings = source.parse_search_page(html)
    print(f"Parsed: {len(listings)} listings\n")

    for ad in listings[:5]:
        price = (
            f"{ad.price.value:.0f} {ad.price.currency}" if ad.price.value else "—"
        )
        rooms = ad.param("number_of_rooms_string")
        area = ad.param("total_area")
        print(f"  #{ad.source_id} | {price} | {ad.location.district or '—'}")
        print(f"    {ad.title[:80]}")
        if rooms or area:
            print(f"    rooms={rooms.value if rooms else '?'}, area={area.value if area else '?'}")
        print(f"    {ad.url}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
