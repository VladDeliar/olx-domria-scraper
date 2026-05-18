"""Dom.ria parser tests — synthetic HTML state, no network."""

from __future__ import annotations

import pytest

from scraper.sources.domria import (
    DomRiaParseError,
    extract_state,
    parse_ad,
    parse_search_page,
)


def test_extract_state_returns_dict(domria_html):
    state = extract_state(domria_html())
    assert "catalog" in state


def test_parse_search_page_one_listing(domria_html, domria_realty_factory):
    listings = parse_search_page(domria_html([domria_realty_factory(realty_id=99)]))
    assert len(listings) == 1
    assert listings[0].source_id == "99"
    assert listings[0].source.value == "domria"


def test_parse_ad_builds_url_and_localises_dt(domria_realty_factory):
    listing = parse_ad(domria_realty_factory())
    # Must include `/uk/` locale prefix — without it Dom.ria returns 404 even
    # though their JSON state ships URLs without locale.
    assert str(listing.url).startswith("https://dom.ria.com/uk/realty-")
    # publishing_date "2026-05-11 10:17:56" gets Europe/Kyiv tzinfo attached.
    assert listing.created_at is not None
    assert listing.created_at.tzinfo is not None


def test_parse_ad_maps_currency_symbol(domria_realty_factory):
    """`$` in currency_type should map to USD."""
    listing = parse_ad(domria_realty_factory(currency_type="$"))
    assert listing.price.currency == "USD"
    listing_uah = parse_ad(domria_realty_factory(currency_type="грн"))
    assert listing_uah.price.currency == "UAH"


def test_parse_ad_normalises_params_to_olx_compatible_keys(domria_realty_factory):
    """Both parsers must produce the same ListingParam keys for matching."""
    listing = parse_ad(domria_realty_factory(rooms_count=3, total_square_meters=80))
    rooms = listing.param("number_of_rooms_string")
    area = listing.param("total_area")
    assert rooms is not None and rooms.normalized_value == 3
    assert area is not None and area.normalized_value == 80


def test_extract_state_raises_when_marker_missing():
    with pytest.raises(DomRiaParseError):
        extract_state("<html><body>nothing here</body></html>")
