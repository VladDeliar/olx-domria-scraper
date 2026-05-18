"""OLX.ua parser.

Strategy: OLX server-renders pages with an embedded JSON state blob
(`window.__PRERENDERED_STATE__`). We extract that JSON and parse listings
from it — no fragile HTML/CSS selectors. Confirmed via recon on
https://www.olx.ua/uk/nedvizhimost/kvartiry/kiev/ (see scraper/recon.py).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests
from pydantic import ValidationError

from scraper.http import build_session, fetch, polite_sleep
from scraper.models import Listing, ListingParam, Location, Operation, Price, Source
from scraper.pagination import page_url

_STATE_MARKER = "window.__PRERENDERED_STATE__="


def infer_operation_from_catalog(url: str) -> Operation:
    """OLX catalog URLs encode the operation explicitly.

    `/prodazha-kvartir/`  → sale
    `/arenda-kvartir/` or `/dolgosrochnaya-arenda-kvartir/` etc. → rent
    Parent category `/kvartiry/<city>/` mixes both → unknown.
    """
    lower = url.lower()
    if "prodazha-" in lower:
        return Operation.SALE
    if "arenda-" in lower or "/orenda-" in lower:
        return Operation.RENT
    return Operation.UNKNOWN


class OlxParseError(Exception):
    """Raised when OLX page structure does not match our assumptions."""


def fetch_search_page(url: str, session: requests.Session | None = None) -> str:
    session = session or build_session()
    response = fetch(session, url)
    return response.text


def extract_state(html: str) -> dict[str, Any]:
    """Return the decoded `__PRERENDERED_STATE__` JSON object."""
    start = html.find(_STATE_MARKER)
    if start < 0:
        raise OlxParseError("PRERENDERED_STATE marker not found")
    cursor = start + len(_STATE_MARKER)
    while cursor < len(html) and html[cursor].isspace():
        cursor += 1
    decoder = json.JSONDecoder()
    first_value, _ = decoder.raw_decode(html, cursor)
    if isinstance(first_value, str):
        first_value = json.loads(first_value)
    if not isinstance(first_value, dict):
        raise OlxParseError(f"unexpected state type: {type(first_value).__name__}")
    return first_value


def _ads_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        ads = state["listing"]["listing"]["ads"]
    except KeyError as exc:
        raise OlxParseError(f"missing key in state: {exc}") from exc
    if not isinstance(ads, list):
        raise OlxParseError(f"ads is not a list: {type(ads).__name__}")
    return ads


def _parse_price(raw: dict[str, Any]) -> Price:
    is_free = bool(raw.get("free"))
    regular = raw.get("regularPrice") or {}
    value = regular.get("value")
    return Price(
        value=Decimal(str(value)) if value is not None else None,
        currency=regular.get("currencyCode"),
        negotiable=bool(regular.get("negotiable", False)),
        is_free=is_free,
    )


def _parse_location(raw_loc: dict[str, Any], raw_map: dict[str, Any] | None) -> Location:
    raw_map = raw_map or {}
    return Location(
        region=raw_loc.get("regionName"),
        region_id=raw_loc.get("regionId"),
        city=raw_loc.get("cityName"),
        city_id=raw_loc.get("cityId"),
        district=raw_loc.get("districtName"),
        district_id=raw_loc.get("districtId"),
        latitude=raw_map.get("lat"),
        longitude=raw_map.get("lon"),
    )


_ROOMS_SLUG_TO_INT: dict[str, int] = {
    "odnokomnatnye": 1,
    "dvuhkomnatnye": 2,
    "trehkomnatnye": 3,
    "chetyrehkomnatnye": 4,
    "pyatikomnatnye": 5,
    "shestikomnatnye": 6,
}


def _normalize_param(key: str, raw_normalized: Any) -> Any:
    """Coerce source-specific normalised values to portable types.

    OLX gives `rooms` as a category slug like `'odnokomnatnye'`; we want an int
    so downstream filters (subscription matching) can do numeric comparisons.
    """
    if key == "number_of_rooms_string" and isinstance(raw_normalized, str):
        return _ROOMS_SLUG_TO_INT.get(raw_normalized, raw_normalized)
    return raw_normalized


def _parse_params(raw_params: list[dict[str, Any]]) -> list[ListingParam]:
    result: list[ListingParam] = []
    for p in raw_params:
        key = p.get("key")
        name = p.get("name")
        value = p.get("value")
        if not key or not name or value is None:
            continue
        result.append(
            ListingParam(
                key=str(key),
                name=str(name),
                value=str(value),
                normalized_value=_normalize_param(str(key), p.get("normalizedValue")),
            )
        )
    return result


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return datetime.fromisoformat(raw)


def parse_ad(raw: dict[str, Any], operation: Operation = Operation.UNKNOWN) -> Listing:
    """Build a `Listing` from one raw ad dict.

    `operation` is decided by the catalog URL (see `infer_operation_from_catalog`)
    — OLX ad payloads don't carry that field individually.

    Raises `pydantic.ValidationError` if mandatory fields are missing or wrong.
    """
    return Listing(
        source=Source.OLX,
        source_id=str(raw["id"]),
        operation_type=operation,
        url=raw["url"],
        title=raw["title"],
        description=raw.get("description"),
        price=_parse_price(raw.get("price") or {}),
        location=_parse_location(raw.get("location") or {}, raw.get("map")),
        params=_parse_params(raw.get("params") or []),
        photos=[p for p in (raw.get("photos") or []) if isinstance(p, str)],
        category_id=(raw.get("category") or {}).get("id"),
        is_business=bool(raw.get("isBusiness", False)),
        is_promoted=bool(raw.get("isPromoted", False)),
        created_at=_parse_dt(raw.get("createdTime")),
        refreshed_at=_parse_dt(raw.get("lastRefreshTime")),
        valid_to=_parse_dt(raw.get("validToTime")),
    )


def parse_search_page(html: str, operation: Operation = Operation.UNKNOWN) -> list[Listing]:
    """Extract all listings from a search-results page's HTML."""
    state = extract_state(html)
    ads = _ads_from_state(state)
    listings: list[Listing] = []
    for raw in ads:
        try:
            listings.append(parse_ad(raw, operation=operation))
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            ad_id = raw.get("id") if isinstance(raw, dict) else "?"
            print(f"[olx] skipped ad {ad_id}: {exc}")
    return listings


def iter_listings(base_url: str, max_pages: int = 1) -> Iterator[Listing]:
    """Yield listings across paginated search results.

    Stops early if a page returns zero listings (end of results / blocked).
    """
    session = build_session()
    operation = infer_operation_from_catalog(base_url)
    seen_ids: set[str] = set()
    for page in range(1, max_pages + 1):
        url = page_url(base_url, page)
        print(f"[olx] page {page}: {url}")
        html = fetch_search_page(url, session=session)
        listings = parse_search_page(html, operation=operation)
        if not listings:
            print(f"[olx] page {page} empty — stopping")
            break
        new_in_page = 0
        for listing in listings:
            if listing.source_id in seen_ids:
                continue
            seen_ids.add(listing.source_id)
            new_in_page += 1
            yield listing
        print(f"[olx] page {page}: +{new_in_page} new (total {len(seen_ids)})")
        if page < max_pages:
            polite_sleep()
