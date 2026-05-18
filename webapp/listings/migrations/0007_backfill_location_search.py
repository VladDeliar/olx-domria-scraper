"""Backfill `location_search` for rows that were saved before the field
existed (or before pipelines started populating it).

Idempotent — re-running on already-backfilled rows is a no-op because the
recomputed string equals the stored one.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    # Inline normalize so we don't import from listings.locations — keeps the
    # migration self-contained and replayable even if the app code changes.
    import re

    pattern = re.compile(r"[\s\-'’`.,]+")

    def normalize(text):
        if not text:
            return ""
        return pattern.sub("", text).lower()

    Listing = apps.get_model("listings", "Listing")
    batch = []
    for listing in Listing.objects.iterator(chunk_size=500):
        parts = [
            normalize(listing.city),
            normalize(listing.district),
            normalize(listing.region),
        ]
        listing.location_search = " ".join(p for p in parts if p)
        batch.append(listing)
        if len(batch) >= 500:
            Listing.objects.bulk_update(batch, ["location_search"])
            batch = []
    if batch:
        Listing.objects.bulk_update(batch, ["location_search"])


def noop_reverse(apps, schema_editor):
    """Reverse leaves data in place — the column itself is dropped by 0006's
    reverse, so there's no work to undo here."""


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0006_listing_location_search"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=noop_reverse),
    ]
