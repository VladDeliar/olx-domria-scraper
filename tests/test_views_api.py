"""HTML views + REST API smoke tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_listings():
    from listings.models import Listing

    a = Listing.objects.create(
        source="olx",
        source_id="L1",
        url="https://www.olx.ua/d/uk/obyavlenie/L1.html",
        title="Печерська квартира",
        price_value=Decimal("25000"),
        price_currency="UAH",
        city="Київ",
        district="Печерський",
    )
    b = Listing.objects.create(
        source="domria",
        source_id="L2",
        url="https://dom.ria.com/realty-L2.html",
        title="Квартира на Шевченківському",
        price_value=Decimal("800"),
        price_currency="USD",
        city="Київ",
        district="Шевченківський",
    )
    return a, b


def test_list_view_renders(two_listings):
    response = Client().get(reverse("listings:list"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Печерська квартира" in body
    assert "Квартира на Шевченківському" in body


def test_list_view_filters_by_currency(two_listings):
    response = Client().get(reverse("listings:list") + "?currency=USD")
    body = response.content.decode("utf-8")
    assert "Квартира на Шевченківському" in body
    assert "Печерська квартира" not in body


def test_detail_view_renders(two_listings):
    a, _ = two_listings
    response = Client().get(reverse("listings:detail", args=[a.pk]))
    assert response.status_code == 200
    assert "Печерська" in response.content.decode("utf-8")


def test_dashboard_renders(two_listings):
    response = Client().get(reverse("listings:dashboard"))
    assert response.status_code == 200
    # Counts are rendered into the cards.
    body = response.content.decode("utf-8")
    assert "Дашборд" in body
    assert "scrape-chart" in body


def test_api_list_returns_json(two_listings):
    response = Client().get("/api/listings/")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    titles = {r["title"] for r in data["results"]}
    assert "Печерська квартира" in titles


def test_api_filter_by_max_price(two_listings):
    response = Client().get("/api/listings/?max_price=1000&currency=USD")
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["price_currency"] == "USD"
