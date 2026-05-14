"""Pytest fixtures shared across test modules."""

from __future__ import annotations

import json

import pytest


def _olx_state_doc(ads: list[dict]) -> str:
    """Build minimal HTML with an embedded __PRERENDERED_STATE__ blob.

    Real OLX wraps the state as a JSON-encoded string literal (so the marker
    looks like `window.__PRERENDERED_STATE__= "..."`). We mirror that exact
    shape so the parser exercises its real decoder path.
    """
    state = {"listing": {"listing": {"ads": ads, "totalElements": len(ads)}}}
    state_str = json.dumps(state, ensure_ascii=False)
    return (
        "<html><head><script>"
        f"window.__PRERENDERED_STATE__= {json.dumps(state_str)};"
        "window.__SOMETHING_ELSE__ = {};"
        "</script></head><body></body></html>"
    )


def _domria_state_doc(realties: list[dict]) -> str:
    state = {
        "catalog": {
            "realtyForCatalog": realties,
            "realtyCountCatalog": len(realties),
        }
    }
    return (
        "<html><head><script>"
        f"window.__INITIAL_STATE__={json.dumps(state, ensure_ascii=False)};"
        "</script></head><body></body></html>"
    )


@pytest.fixture
def olx_ad_factory():
    """Return a callable that builds a realistic OLX ad dict.

    Mirrors the shape captured during recon (see scraper/inspect_state.py).
    """

    def make(**overrides):
        ad = {
            "id": 100,
            "title": "Здам 1-кімнатну квартиру",
            "description": "Опис оголошення",
            "url": "https://www.olx.ua/d/uk/obyavlenie/test-100.html",
            "createdTime": "2026-05-13T18:41:42+03:00",
            "lastRefreshTime": "2026-05-13T18:46:21+03:00",
            "validToTime": "2026-06-12T18:43:17+03:00",
            "isBusiness": False,
            "isPromoted": False,
            "category": {"id": 1760, "type": "real_estate"},
            "price": {
                "free": False,
                "regularPrice": {
                    "value": 15000,
                    "currencyCode": "UAH",
                    "negotiable": False,
                },
            },
            "location": {
                "regionName": "Київська область",
                "regionId": 25,
                "cityName": "Київ",
                "cityId": 268,
                "districtName": "Печерський",
                "districtId": 11,
            },
            "map": {"lat": 50.45, "lon": 30.52},
            "params": [
                {
                    "key": "number_of_rooms_string",
                    "name": "Кімнат",
                    "value": "1 кімната",
                    "normalizedValue": "odnokomnatnye",
                },
                {
                    "key": "total_area",
                    "name": "Загальна площа",
                    "value": "45 м²",
                    "normalizedValue": "45",
                },
                {"key": "floor", "name": "Поверх", "value": "3", "normalizedValue": "3"},
            ],
            "photos": ["https://cdn.example.com/p1.jpg"],
        }
        ad.update(overrides)
        return ad

    return make


@pytest.fixture
def domria_realty_factory():
    def make(**overrides):
        realty = {
            "realty_id": 12345,
            "beautifulUrl": "/realty-test-12345.html",
            "imgSeoALT": "Здається в оренду 2-кімнатна квартира 60 м²",
            "description_uk": "Тестовий опис",
            "price": 800,
            "currency_type": "$",
            "state_name_uk": "Київська",
            "state_id": 10,
            "city_name_uk": "Київ",
            "city_id": 10,
            "district_name_uk": "Шевченківський",
            "district_id": 15101,
            "latitude": 50.45,
            "longitude": 30.52,
            "total_square_meters": 60.5,
            "living_square_meters": 35.0,
            "kitchen_square_meters": 10.0,
            "rooms_count": 2,
            "floor": 5,
            "floors_count": 9,
            "wall_type": "кирпич",
            "realty_type_id": 2,
            "agency_id": 0,
            "publishing_date": "2026-05-11 10:17:56",
            "actualized_at": "2026-05-13 18:08:11",
            "mainPhoto": "https://cdn.riastatic.com/photos/dom/photo/1/1/1/1/1b.jpg",
            "photos": [{"file": "dom/photo/1/1/1/1/1.jpg"}],
        }
        realty.update(overrides)
        return realty

    return make


@pytest.fixture
def olx_html(olx_ad_factory):
    return lambda ads=None: _olx_state_doc(ads or [olx_ad_factory()])


@pytest.fixture
def domria_html(domria_realty_factory):
    return lambda realties=None: _domria_state_doc(realties or [domria_realty_factory()])
