"""Pydantic Listing -> Django ORM upsert."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scraper.sources.olx import parse_ad as parse_olx_ad

pytestmark = pytest.mark.django_db


def test_save_listing_creates_new(olx_ad_factory):
    from listings.models import Listing
    from listings.pipelines import save_listing

    pyd = parse_olx_ad(olx_ad_factory(id=1001))
    listing, created = save_listing(pyd)
    assert created is True
    assert Listing.objects.count() == 1
    assert listing.source_id == "1001"
    assert listing.price_value == Decimal("15000")
    assert listing.city == "Київ"


def test_save_listing_updates_existing(olx_ad_factory):
    """Second save of the same source_id is an update, not a duplicate."""
    from listings.models import Listing
    from listings.pipelines import save_listing

    pyd1 = parse_olx_ad(olx_ad_factory(id=2002, title="Старий заголовок"))
    save_listing(pyd1)
    pyd2 = parse_olx_ad(olx_ad_factory(id=2002, title="Новий заголовок"))
    listing, created = save_listing(pyd2)
    assert created is False
    assert Listing.objects.count() == 1
    assert listing.title == "Новий заголовок"


def test_save_listing_replaces_params_on_update(olx_ad_factory):
    """Param strategy is delete-and-recreate, not append."""
    from listings.pipelines import save_listing

    ad1 = olx_ad_factory(
        id=3003,
        params=[
            {"key": "floor", "name": "Поверх", "value": "5", "normalizedValue": "5"},
        ],
    )
    save_listing(parse_olx_ad(ad1))

    ad2 = olx_ad_factory(
        id=3003,
        params=[
            {"key": "floor", "name": "Поверх", "value": "7", "normalizedValue": "7"},
            {"key": "total_area", "name": "Площа", "value": "50 м²", "normalizedValue": "50"},
        ],
    )
    listing, _ = save_listing(parse_olx_ad(ad2))

    keys = set(listing.params.values_list("key", flat=True))
    assert keys == {"floor", "total_area"}
    floor = listing.params.get(key="floor")
    assert floor.value == "7"
