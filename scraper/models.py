"""Pydantic schemas for scraped real-estate listings.

Source-agnostic — every parser must return `Listing` instances. Anything that
fails validation is a parse error: logged and (later) written to ScrapeAlert,
never silently coerced.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Source(StrEnum):
    OLX = "olx"
    DOMRIA = "domria"


class Price(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Decimal | None = Field(default=None, description="Amount in `currency`; None if free.")
    currency: str | None = Field(default=None, description="ISO-4217 code, e.g. UAH, USD.")
    negotiable: bool = False
    is_free: bool = False


class Location(BaseModel):
    model_config = ConfigDict(frozen=True)

    region: str | None = None
    region_id: int | None = None
    city: str | None = None
    city_id: int | None = None
    district: str | None = None
    district_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class ListingParam(BaseModel):
    """A typed attribute on a listing (floor, area, rooms, etc.)."""

    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    value: str
    normalized_value: Any = None


class Listing(BaseModel):
    """One real-estate listing, normalised across sources."""

    model_config = ConfigDict(frozen=True)

    source: Source
    source_id: str = Field(description="Native ID inside `source` (used for upsert).")
    url: HttpUrl
    title: str
    description: str | None = None

    price: Price
    location: Location
    params: list[ListingParam] = Field(default_factory=list)
    photos: list[HttpUrl] = Field(default_factory=list)

    category_id: int | None = None
    is_business: bool = False
    is_promoted: bool = False

    created_at: datetime | None = None
    refreshed_at: datetime | None = None
    valid_to: datetime | None = None

    def param(self, key: str) -> ListingParam | None:
        for p in self.params:
            if p.key == key:
                return p
        return None
