"""Normalization + fuzzy resolver + filter end-to-end."""

from __future__ import annotations

import pytest
from listings.locations import (
    get_oblast_settlements,
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


@pytest.fixture
def seed_gazetteer(db):
    """Cities that have NO listings but are valid Ukrainian places."""
    from listings.locations import normalize_location
    from listings.models import GazetteerLocation

    for name in ("Дніпро", "Тернопіль", "Чернігів"):
        GazetteerLocation.objects.create(
            name=name,
            normalized=normalize_location(name),
            kind=GazetteerLocation.Kind.CITY,
            parent_path="",
        )
    invalidate_known_locations_cache()
    yield
    invalidate_known_locations_cache()


@pytest.mark.django_db
def test_resolve_falls_back_to_gazetteer(seed_gazetteer):
    # No listings at all, but Дніпро exists in the gazetteer → resolves.
    assert resolve_location("Дніпро") == "Дніпро"
    assert resolve_location("дніпро") == "Дніпро"


@pytest.mark.django_db
def test_resolve_fuzzy_against_gazetteer(seed_gazetteer):
    # Single missing letter in gazetteer-only name.
    assert resolve_location("Тернопль") == "Тернопіль"


@pytest.mark.django_db
def test_filter_via_location_param(seed_listings):
    from django.test import Client

    response = Client().get("/?location=іванофранківськ")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Тест Івано-Франківськ" in body
    assert "Тест Київ" not in body


@pytest.fixture
def seed_gazetteer_oblast(db):
    """One oblast with 2 cities, 1 town, 1 village inside it."""
    from listings.models import GazetteerLocation

    GazetteerLocation.objects.create(
        name="Тернопільська", normalized="тернопільська", kind="oblast", parent_path=""
    )
    GazetteerLocation.objects.create(
        name="Тернопіль",
        normalized="тернопіль",
        kind="city",
        parent_path="Тернопільська > Тернопільський",
    )
    GazetteerLocation.objects.create(
        name="Чортків",
        normalized="чортків",
        kind="city",
        parent_path="Тернопільська > Чортківський",
    )
    GazetteerLocation.objects.create(
        name="Заводське",
        normalized="заводське",
        kind="town",
        parent_path="Тернопільська > Чортківський",
    )
    GazetteerLocation.objects.create(
        name="Підгайчики",
        normalized="підгайчики",
        kind="village",
        parent_path="Тернопільська > Чортківський",
    )
    invalidate_known_locations_cache()
    yield
    invalidate_known_locations_cache()


@pytest.mark.django_db
def test_get_oblast_settlements_returns_cities_only(seed_gazetteer_oblast):
    names = get_oblast_settlements("Тернопільська")
    assert "Тернопіль" in names
    assert "Чортків" in names
    # Towns (СМТ) and villages excluded — hundreds per oblast, unusable in a
    # <select>; the free-text input reaches them instead.
    assert "Заводське" not in names
    assert "Підгайчики" not in names


@pytest.mark.django_db
def test_oblast_settlements_json_returns_cities(seed_gazetteer_oblast):
    from django.test import Client

    response = Client().get("/locations/settlements/?oblast=Тернопільська")
    assert response.status_code == 200
    data = response.json()
    assert "Тернопіль" in data["settlements"]
    assert "Підгайчики" not in data["settlements"]


@pytest.mark.django_db
def test_oblast_settlements_json_unknown_oblast(seed_gazetteer_oblast):
    from django.test import Client

    response = Client().get("/locations/settlements/?oblast=Атлантида")
    assert response.status_code == 200
    assert response.json() == {"settlements": []}
