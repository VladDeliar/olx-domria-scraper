"""Extract and inspect an embedded JS state JSON blob from a saved HTML page.

Run:
    uv run python -m scraper.inspect_state                    # OLX (default)
    uv run python -m scraper.inspect_state __INITIAL_STATE__   # Dom.ria
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HTML_FILE = Path("scraper/recon_artefacts/last_response.html")
_OUT_JSON = Path("scraper/recon_artefacts/state.json")


def _find_json_blob(html: str, marker_name: str = "__PRERENDERED_STATE__") -> str:
    """Locate `window.<marker_name>=` and return the JSON text after it.

    Some sites stringify the JSON (`"...escaped..."`); some inline it directly.
    We use raw_decode to consume exactly the first JSON value.
    """
    marker = f"window.{marker_name}="
    start = html.find(marker)
    if start < 0:
        raise ValueError(f"marker {marker!r} not found")
    cursor = start + len(marker)
    while cursor < len(html) and html[cursor].isspace():
        cursor += 1
    decoder = json.JSONDecoder()
    first_value, _ = decoder.raw_decode(html, cursor)
    if isinstance(first_value, str):
        return first_value
    return json.dumps(first_value)


def _summarise(node: object, path: str = "", depth: int = 0, max_depth: int = 3) -> None:
    if depth > max_depth:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            type_name = type(value).__name__
            extra = ""
            if isinstance(value, list):
                extra = f"[{len(value)}]"
            elif isinstance(value, dict):
                extra = f"{{{len(value)}}}"
            print(f"  {'  ' * depth}{path}.{key}: {type_name}{extra}")
            if isinstance(value, (dict, list)) and depth < max_depth:
                _summarise(value, f"{path}.{key}", depth + 1, max_depth)
    elif isinstance(node, list) and node:
        _summarise(node[0], f"{path}[0]", depth + 1, max_depth)


def main(argv: list[str]) -> int:
    marker = argv[1] if len(argv) > 1 else "__PRERENDERED_STATE__"
    html = _HTML_FILE.read_text(encoding="utf-8")
    raw = _find_json_blob(html, marker)
    data = json.loads(raw)
    _OUT_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved parsed state ({len(raw):,} chars) -> {_OUT_JSON}\n")
    print(f"Top-level structure (marker={marker}):")
    _summarise(data, max_depth=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
