"""Entry point: fetch one OLX search page and print parsed listings.

    uv run python -m scraper https://www.olx.ua/uk/nedvizhimost/kvartiry/kiev/
"""

from __future__ import annotations

import sys

from scraper.sources.olx import fetch_search_page, parse_search_page


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m scraper <olx-search-url>", file=sys.stderr)
        return 2
    url = argv[1]
    print(f"Fetching: {url}")
    html = fetch_search_page(url)
    print(f"  -> {len(html):,} bytes")

    listings = parse_search_page(html)
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
