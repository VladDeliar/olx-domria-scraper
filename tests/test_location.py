"""Normalization + fuzzy resolver + filter end-to-end."""

from __future__ import annotations

import pytest
from listings.locations import (
    invalidate_known_locations_cache,
    normalize_location,
    resolve_location,
    suggest_locations,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Івано-Франківськ", "іванофранківськ"),
        ("Івано Франківськ", "іванофранківськ"),
        ("ІваноФранківськ", "іванофранківськ"),
        ("ІВАНО-ФРАНКІВСЬК", "іванофранківськ"),
        ("  івано-франківськ  ", "іванофранківськ"),
        ("Київ", "київ"),
        ("Печерський", "печерський"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_collapses_variants(raw, expected):
    assert normalize_location(raw) == expected


@pytest.fixture
def seed_listings(db):
    from listings.models import Listing

    def _make(city: str, district: str = ""):
        return Listing.objects.create(
            source="olx",
            source_id=f"loc-{city}-{district}",
            url=f"https://example.com/{city}-{district}",
            title=f"Тест {city}",
            city=city,
            district=district,
            location_search=f"{normalize_location(city)} {normalize_location(district)}".strip(),
        )

    _make("Київ", "Печерський")
    _make("Київ", "Дарницький")
    _make("Івано-Франківськ", "")
    _make("Львів", "Личаківський")
    invalidate_known_locations_cache()
    yield
    invalidate_known_locations_cache()


@pytest.mark.django_db
def test_resolve_exact_match(seed_listings):
    assert resolve_location("Печерський") == "Печерський"
    assert resolve_location("печерський") == "Печерський"
    assert resolve_location("ПЕЧЕРСЬКИЙ") == "Печерський"


@pytest.mark.django_db
def test_resolve_whitespace_variants(seed_listings):
    assert resolve_location("Івано Франківськ") == "Івано-Франківськ"
    assert resolve_location("ІваноФранківськ") == "Івано-Франківськ"


@pytest.mark.django_db
def test_resolve_fuzzy_handles_typo(seed_listings):
    # Real spelling error — single character missing — should still resolve.
    assert resolve_location("Печерскій") == "Печерський"


@pytest.mark.django_db
def test_resolve_returns_none_when_no_match(seed_listings):
    assert resolve_location("Марс") is None
    assert resolve_location("") is None


@pytest.mark.django_db
def test_suggest_returns_top_n_close_matches(seed_listings):
    # "Київ" + "Львів" share a vowel — neither should rank high for "ХерсонХ".
    suggestions = suggest_locations("Печерсхій", n=2)
    assert "Печерський" in suggestions


@pytest.mark.django_db
def test_filter_via_location_param(seed_listings):
    from django.test import Client

    response = Client().get("/?location=іванофранківськ")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Тест Івано-Франківськ" in body
    assert "Тест Київ" not in body
