"""Pydantic Listing → Django ORM bridge.

`save_listing()` performs an upsert on `(source, source_id)`. Returns the
ORM instance plus a `created` flag so the management command can keep
new/updated tallies.
"""

from __future__ import annotations

from django.db import transaction

from listings.models import Listing, ListingParam

# Pydantic schema lives in the scraper package (added to sys.path in settings.py).
from scraper.models import Listing as PydanticListing


@transaction.atomic
def save_listing(pydantic_obj: PydanticListing) -> tuple[Listing, bool]:
    """Upsert one listing + its params atomically.

    Strategy for params: delete-all-and-recreate. Cheaper to code than diffing,
    fine for our scale; if we hit perf issues later we can switch to a merge.
    """
    defaults = {
        "operation_type": pydantic_obj.operation_type.value,
        "url": str(pydantic_obj.url),
        "title": pydantic_obj.title,
        "description": pydantic_obj.description or "",
        "price_value": pydantic_obj.price.value,
        "price_currency": pydantic_obj.price.currency or "",
        "price_negotiable": pydantic_obj.price.negotiable,
        "price_is_free": pydantic_obj.price.is_free,
        "region": pydantic_obj.location.region or "",
        "region_id": pydantic_obj.location.region_id,
        "city": pydantic_obj.location.city or "",
        "city_id": pydantic_obj.location.city_id,
        "district": pydantic_obj.location.district or "",
        "district_id": pydantic_obj.location.district_id,
        "latitude": pydantic_obj.location.latitude,
        "longitude": pydantic_obj.location.longitude,
        "photos": [str(p) for p in pydantic_obj.photos],
        "category_id": pydantic_obj.category_id,
        "is_business": pydantic_obj.is_business,
        "is_promoted": pydantic_obj.is_promoted,
        "created_at_source": pydantic_obj.created_at,
        "refreshed_at_source": pydantic_obj.refreshed_at,
        "valid_to_source": pydantic_obj.valid_to,
    }

    listing, created = Listing.objects.update_or_create(
        source=pydantic_obj.source.value,
        source_id=pydantic_obj.source_id,
        defaults=defaults,
    )

    listing.params.all().delete()
    ListingParam.objects.bulk_create(
        [
            ListingParam(
                listing=listing,
                key=p.key,
                name=p.name,
                value=p.value,
                normalized_value=p.normalized_value,
            )
            for p in pydantic_obj.params
        ]
    )
    return listing, created
