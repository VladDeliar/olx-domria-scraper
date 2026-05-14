"""OLX parser tests — synthetic HTML state, no network."""

from __future__ import annotations

import pytest

from scraper.sources.olx import (
    OlxParseError,
    extract_state,
    parse_ad,
    parse_search_page,
)


def test_extract_state_returns_dict(olx_html):
    state = extract_state(olx_html())
    assert isinstance(state, dict)
    assert "listing" in state


def test_parse_search_page_returns_one_listing(olx_html, olx_ad_factory):
    listings = parse_search_page(olx_html([olx_ad_factory(id=42)]))
    assert len(listings) == 1
    assert listings[0].source_id == "42"
    assert listings[0].title == "Здам 1-кімнатну квартиру"
    assert listings[0].source.value == "olx"


def test_parse_ad_extracts_price_and_location(olx_ad_factory):
    listing = parse_ad(olx_ad_factory())
    assert listing.price.value == 15000
    assert listing.price.currency == "UAH"
    assert listing.location.district == "Печерський"
    assert listing.location.city == "Київ"


def test_parse_ad_normalises_rooms_slug_to_int(olx_ad_factory):
    """The OLX catalog stores rooms as 'odnokomnatnye'; parser must coerce to int."""
    listing = parse_ad(olx_ad_factory())
    rooms = listing.param("number_of_rooms_string")
    assert rooms is not None
    assert rooms.normalized_value == 1


def test_parse_search_page_skips_broken_ad(olx_html, olx_ad_factory):
    good = olx_ad_factory(id=1)
    broken = olx_ad_factory(id=2)
    del broken["url"]  # missing required field -> ValidationError, but loop continues
    listings = parse_search_page(olx_html([good, broken]))
    assert len(listings) == 1
    assert listings[0].source_id == "1"


def test_extract_state_raises_when_marker_missing():
    with pytest.raises(OlxParseError):
        extract_state("<html><body>no state here</body></html>")
