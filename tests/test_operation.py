"""operation_type inference + filter."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scraper.models import Operation
from scraper.sources.domria import parse_ad as parse_domria_ad
from scraper.sources.olx import infer_operation_from_catalog
from scraper.sources.olx import parse_ad as parse_olx_ad


@pytest.mark.parametrize(
    "url,expected",
    [
        # OLX rent variants
        (
            "https://www.olx.ua/uk/nedvizhimost/kvartiry/dolgosrochnaya-arenda-kvartir/kiev/",
            Operation.RENT,
        ),
        ("https://www.olx.ua/uk/nedvizhimost/kvartiry/arenda-kvartir/lvov/", Operation.RENT),
        # OLX sale
        (
            "https://www.olx.ua/uk/nedvizhimost/kvartiry/prodazha-kvartir/kiev/",
            Operation.SALE,
        ),
        # Parent category — mixed
        ("https://www.olx.ua/uk/nedvizhimost/kvartiry/kiev/", Operation.UNKNOWN),
    ],
)
def test_olx_infer_operation_from_catalog(url, expected):
    assert infer_operation_from_catalog(url) == expected


def test_olx_parse_ad_attaches_operation(olx_ad_factory):
    listing = parse_olx_ad(olx_ad_factory(), operation=Operation.RENT)
    assert listing.operation_type == Operation.RENT


def test_olx_parse_ad_defaults_to_unknown(olx_ad_factory):
    listing = parse_olx_ad(olx_ad_factory())
    assert listing.operation_type == Operation.UNKNOWN


def test_domria_parse_ad_uses_advert_type_id(domria_realty_factory):
    # Default factory has advert_type_id=3 only if we set it; let's verify both paths.
    rent_listing = parse_domria_ad(domria_realty_factory(advert_type_id=3))
    assert rent_listing.operation_type == Operation.RENT
    sale_listing = parse_domria_ad(domria_realty_factory(advert_type_id=1))
    assert sale_listing.operation_type == Operation.SALE


def test_domria_parse_ad_unknown_when_advert_type_missing(domria_realty_factory):
    listing = parse_domria_ad(domria_realty_factory(advert_type_id=None))
    assert listing.operation_type == Operation.UNKNOWN


@pytest.mark.django_db
def test_list_view_filter_by_operation():
    from django.test import Client
    from django.urls import reverse
    from listings.models import Listing

    Listing.objects.create(
        source="olx",
        source_id="S1",
        url="https://x/1",
        title="Продаж квартири",
        operation_type="sale",
        price_value=Decimal("1500000"),
        price_currency="UAH",
        city="Київ",
    )
    Listing.objects.create(
        source="olx",
        source_id="S2",
        url="https://x/2",
        title="Оренда квартири",
        operation_type="rent",
        price_value=Decimal("15000"),
        price_currency="UAH",
        city="Київ",
    )

    response = Client().get(reverse("listings:list") + "?operation_type=rent")
    body = response.content.decode("utf-8")
    assert "Оренда квартири" in body
    assert "Продаж квартири" not in body
