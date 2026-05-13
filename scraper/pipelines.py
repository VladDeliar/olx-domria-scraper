"""Sinks for scraped Listings.

For now: JSON Lines on disk (one Listing per line). DB pipeline lands on Day 3
once the Django app exists.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from scraper.models import Listing


def dump_jsonl(listings: Iterable[Listing], out_path: Path) -> int:
    """Write listings to a JSON Lines file. Returns number of records written.

    JSONL (vs. one big JSON array) means we can stream-write and you can grep,
    pipe to jq, or load line-by-line without parsing the whole file.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for listing in listings:
            f.write(listing.model_dump_json())
            f.write("\n")
            count += 1
    return count
