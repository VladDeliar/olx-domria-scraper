"""Dom.ria parser.

Strategy: Dom.ria server-renders pages with an embedded `window.__INITIAL_STATE__`
JSON blob containing `catalog.realtyForCatalog` — a list of listings with all
fields flat in one dict. No fragile HTML/CSS selectors. Confirmed via recon
on https://dom.ria.com/uk/arenda-kvartir/kiev/.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests
from pydantic import ValidationError

from scraper.http import build_session, fetch
from scraper.models import Listing, ListingParam, Location, Price, Source

_STATE_MARKER = "window.__INITIAL_STATE__="
_SITE_ORIGIN = "https://dom.ria.com"
_CDN_ORIGIN = "https://cdn.riastatic.com/photos"

_CURRENCY_MAP = {
    "$": "USD",
    "грн": "UAH",
    "грн.": "UAH",
    "€": "EUR",
}

# Map Dom.ria flat fields → ListingParam entries with OLX-compatible keys.
# (key in our normalised model, dom.ria field name, display name, formatter)
_PARAM_MAPPINGS: list[tuple[str, str, str, str]] = [
    ("floor", "floor", "Поверх", "{}"),
    ("total_floors", "floors_count", "Поверховість", "{}"),
    ("total_area", "total_square_meters", "Загальна площа", "{} м²"),
    ("living_area", "living_square_meters", "Житлова площа", "{} м²"),
    ("kitchen_area", "kitchen_square_meters", "Площа кухні", "{} м²"),
    ("number_of_rooms_string", "rooms_count", "Кількість кімнат", "{}"),
    ("wall_type", "wall_type", "Тип стін", "{}"),
]


class DomRiaParseError(Exception):
    """Raised when Dom.ria page structure does not match our assumptions."""


def fetch_search_page(url: str, session: requests.Session | None = None) -> str:
    session = session or build_session()
    response = fetch(session, url)
    return response.text


def extract_state(html: str) -> dict[str, Any]:
    """Return the decoded `__INITIAL_STATE__` JSON object."""
    start = html.find(_STATE_MARKER)
    if start < 0:
        raise DomRiaParseError("INITIAL_STATE marker not found")
    cursor = start + len(_STATE_MARKER)
    while cursor < len(html) and html[cursor].isspace():
        cursor += 1
    decoder = json.JSONDecoder()
    first_value, _ = decoder.raw_decode(html, cursor)
    if isinstance(first_value, str):
        first_value = json.loads(first_value)
    if not isinstance(first_value, dict):
        raise DomRiaParseError(f"unexpected state type: {type(first_value).__name__}")
    return first_value


def _ads_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        ads = state["catalog"]["realtyForCatalog"]
    except KeyError as exc:
        raise DomRiaParseError(f"missing key in state: {exc}") from exc
    if not isinstance(ads, list):
        raise DomRiaParseError(f"realtyForCatalog is not a list: {type(ads).__name__}")
    return ads


def _parse_price(raw: dict[str, Any]) -> Price:
    value = raw.get("price")
    currency_symbol = (raw.get("currency_type") or "").strip()
    return Price(
        value=Decimal(str(value)) if value not in (None, 0) else None,
        currency=_CURRENCY_MAP.get(currency_symbol),
        negotiable=False,
        is_free=False,
    )


def _parse_location(raw: dict[str, Any]) -> Location:
    return Location(
        region=raw.get("state_name_uk"),
        region_id=raw.get("state_id"),
        city=raw.get("city_name_uk") or raw.get("cityName"),
        city_id=raw.get("city_id"),
        district=raw.get("district_name_uk"),
        district_id=raw.get("district_id"),
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
    )


def _parse_params(raw: dict[str, Any]) -> list[ListingParam]:
    params: list[ListingParam] = []
    for key, src_field, display_name, fmt in _PARAM_MAPPINGS:
        value = raw.get(src_field)
        if value in (None, "", 0):
            continue
        params.append(
            ListingParam(
                key=key,
                name=display_name,
                value=fmt.format(value),
                normalized_value=value,
            )
        )
    return params


def _parse_photos(raw: dict[str, Any]) -> list[str]:
    """Build CDN URLs from `photos[].file` paths.

    Dom.ria stores e.g. `dom/photo/123/123/1234/1234.jpg`; the public CDN serves
    `<origin>/dom/photo/.../1234b.jpg` (the `b` suffix denotes the size variant
    used on the listing page).
    """
    photos: list[str] = []
    main_photo = raw.get("mainPhoto")
    if isinstance(main_photo, str) and main_photo:
        photos.append(main_photo)
    for photo in raw.get("photos") or []:
        if not isinstance(photo, dict):
            continue
        file_path = photo.get("file")
        if not isinstance(file_path, str) or "." not in file_path:
            continue
        stem, dot, ext = file_path.rpartition(".")
        url = f"{_CDN_ORIGIN}/{stem}b{dot}{ext}"
        if url not in photos:
            photos.append(url)
    return photos


def _parse_dt(raw: str | None) -> datetime | None:
    """Dom.ria uses `YYYY-MM-DD HH:MM:SS` (naive, Kyiv local time)."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _build_url(beautiful_url: str) -> str:
    if beautiful_url.startswith("http"):
        return beautiful_url
    if not beautiful_url.startswith("/"):
        beautiful_url = "/" + beautiful_url
    return f"{_SITE_ORIGIN}{beautiful_url}"


def _build_title(raw: dict[str, Any]) -> str:
    """Dom.ria has no clean title field; prefer SEO ALT, fall back to a synthesised one."""
    seo = raw.get("imgSeoALT")
    if isinstance(seo, str) and seo.strip():
        return seo.strip()
    rooms = raw.get("rooms_count")
    area = raw.get("total_square_meters")
    city = raw.get("city_name_uk")
    realty = raw.get("realty_type_name_uk", "Квартира")
    return f"{realty}, {rooms}к, {area} м², {city}"


def parse_ad(raw: dict[str, Any]) -> Listing:
    """Build a `Listing` from one Dom.ria raw dict."""
    return Listing(
        source=Source.DOMRIA,
        source_id=str(raw["realty_id"]),
        url=_build_url(raw["beautifulUrl"]),
        title=_build_title(raw),
        description=raw.get("description_uk"),
        price=_parse_price(raw),
        location=_parse_location(raw),
        params=_parse_params(raw),
        photos=_parse_photos(raw),
        category_id=raw.get("realty_type_id"),
        is_business=bool(raw.get("agency_id")),
        is_promoted=False,
        created_at=_parse_dt(raw.get("publishing_date")),
        refreshed_at=_parse_dt(raw.get("actualized_at")),
        valid_to=None,
    )


def parse_search_page(html: str) -> list[Listing]:
    state = extract_state(html)
    ads = _ads_from_state(state)
    listings: list[Listing] = []
    for raw in ads:
        try:
            listings.append(parse_ad(raw))
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            ad_id = raw.get("realty_id") if isinstance(raw, dict) else "?"
            print(f"[domria] skipped ad {ad_id}: {exc}")
    return listings
