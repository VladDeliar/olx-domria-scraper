"""CLI: scrape N pages from a source and (optionally) dump to JSONL.

    uv run python -m scraper olx    URL [--pages N] [--out FILE]
    uv run python -m scraper domria URL [--pages N] [--out FILE]

Examples:
    uv run python -m scraper olx https://www.olx.ua/uk/nedvizhimost/kvartiry/kiev/
    uv run python -m scraper domria https://dom.ria.com/uk/arenda-kvartir/kiev/ --pages 3 --out data/domria.jsonl
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from scraper.models import Listing
from scraper.pipelines import dump_jsonl
from scraper.sources import domria, olx

_SOURCES = {"olx": olx, "domria": domria}


def _tee_preview(listings: Iterable[Listing], n: int) -> Iterator[Listing]:
    """Pass listings through while printing the first `n` for the operator."""
    for i, ad in enumerate(listings):
        if i < n:
            price = f"{ad.price.value:.0f} {ad.price.currency}" if ad.price.value else "—"
            rooms = ad.param("number_of_rooms_string")
            area = ad.param("total_area")
            print(f"  #{ad.source_id} | {price} | {ad.location.district or '—'}")
            print(f"    {ad.title[:80]}")
            if rooms or area:
                rv = rooms.value if rooms else "?"
                av = area.value if area else "?"
                print(f"    rooms={rv}, area={av}")
            print(f"    {ad.url}")
        yield ad


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="scraper", description="Scrape real-estate listings.")
    parser.add_argument("source", choices=sorted(_SOURCES))
    parser.add_argument("url", help="Base search URL on the chosen source.")
    parser.add_argument("--pages", type=int, default=1, help="Max pages to fetch (default 1).")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write listings as JSONL to this path (creates parent dirs).",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="Print preview of first N listings to stdout (default 5).",
    )
    args = parser.parse_args(argv[1:])

    source = _SOURCES[args.source]
    print(f"Source: {args.source} | URL: {args.url} | pages: {args.pages}\n")

    stream = source.iter_listings(args.url, max_pages=args.pages)
    stream = _tee_preview(stream, args.preview)

    if args.out is not None:
        count = dump_jsonl(stream, args.out)
        print(f"\nWrote {count} listings -> {args.out}")
    else:
        # No output sink — still need to drain the iterator for previews.
        count = sum(1 for _ in stream)
        print(f"\nScraped {count} listings (no --out given; nothing saved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
