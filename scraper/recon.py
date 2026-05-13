"""Recon a target site: fetch a search page, save HTML, look for hidden JSON API.

Run:
    uv run python -m scraper.recon https://www.olx.ua/uk/nedvizhimost/kvartiry/kiev/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from scraper.http import build_session, fetch

_OUT_DIR = Path("scraper/recon_artefacts")

_JSON_BLOB_PATTERNS = [
    (r"window\.__PRERENDERED_STATE__\s*=\s*", "PRERENDERED_STATE"),
    (r"window\.__INITIAL_STATE__\s*=\s*", "INITIAL_STATE"),
    (r"window\.__NEXT_DATA__\s*=\s*", "NEXT_DATA"),
    (r'<script[^>]+id="__NEXT_DATA__"[^>]*>', "NEXT_DATA_SCRIPT"),
    (r"window\.__APOLLO_STATE__\s*=\s*", "APOLLO_STATE"),
]

_API_HINT_PATTERNS = [
    r"/api/v\d+/[\w/-]+",
    r'"apiUrl"\s*:\s*"([^"]+)"',
    r'"graphql"\s*:\s*"([^"]+)"',
]


def _report(label: str, hits: list[str]) -> None:
    if not hits:
        print(f"  [ ] {label}: not found")
        return
    print(f"  [x] {label}: {len(hits)} hit(s)")
    for hit in hits[:5]:
        print(f"      - {hit[:120]}")


def recon(url: str) -> None:
    print(f"Reconning: {url}\n")
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    session = build_session()
    response = fetch(session, url)
    html = response.text

    out_file = _OUT_DIR / "last_response.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Saved {len(html):,} bytes -> {out_file}\n")

    print("Embedded JSON state markers:")
    for pattern, label in _JSON_BLOB_PATTERNS:
        hits = re.findall(pattern, html)
        _report(label, hits)

    print("\nAPI endpoint hints:")
    for pattern in _API_HINT_PATTERNS:
        hits = re.findall(pattern, html)
        _report(pattern, list(set(hits)))

    print("\nResponse headers of interest:")
    for header in ("content-type", "server", "x-powered-by", "set-cookie"):
        if value := response.headers.get(header):
            print(f"  {header}: {value[:120]}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m scraper.recon <url>", file=sys.stderr)
        return 2
    recon(argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
