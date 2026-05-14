"""Enrich previously-scraped listings via Playwright (detail pages).

    python manage.py enrich --source olx --limit 5
    python manage.py enrich --source olx --reenrich   # re-fetch already-enriched

Only OLX is supported today — Dom.ria catalog is detailed enough that we
don't need a second pass. If/when Dom.ria gains a detail enricher, plug it
into the same dispatch table.
"""

from __future__ import annotations

import asyncio
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from listings.models import Listing, Source
from scraper.browser import browser_context
from scraper.http import polite_sleep
from scraper.sources.olx_detail import fetch_detail as fetch_olx_detail


async def _enrich_all(qs: list[Listing], cmd: BaseCommand) -> tuple[int, int]:
    """Run the Playwright fetch loop. Returns (ok_count, error_count)."""
    ok = errors = 0
    async with browser_context() as ctx:
        for i, listing in enumerate(qs, start=1):
            try:
                detail = await fetch_olx_detail(ctx, listing.url)
            except (TimeoutError, OSError, ValueError) as exc:
                errors += 1
                cmd.stderr.write(f"  [{i}/{len(qs)}] #{listing.source_id}: {exc}")
                continue
            listing.extras = dict(detail)
            listing.enriched_at = timezone.now()
            await listing.asave(update_fields=["extras", "enriched_at"])
            ok += 1
            desc_len = len(detail.get("description_full") or "")
            photos = len(detail.get("photos_full") or [])
            cmd.stdout.write(
                f"  [{i}/{len(qs)}] #{listing.source_id}: desc={desc_len} chars, photos={photos}"
            )
            if i < len(qs):
                polite_sleep()
    return ok, errors


class Command(BaseCommand):
    help = "Fetch detail pages and store extras (description_full, photos_full, posted_at_text)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--source",
            choices=[Source.OLX.value],
            default=Source.OLX.value,
            help="Currently only `olx` is supported.",
        )
        parser.add_argument("--limit", type=int, default=5)
        parser.add_argument(
            "--reenrich",
            action="store_true",
            help="Also include listings that already have `enriched_at` set.",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        qs = Listing.objects.filter(source=opts["source"])
        if not opts["reenrich"]:
            qs = qs.filter(enriched_at__isnull=True)
        qs = list(qs.order_by("-last_seen_at")[: opts["limit"]])
        if not qs:
            self.stdout.write(self.style.WARNING("nothing to enrich"))
            return
        self.stdout.write(self.style.NOTICE(f"enriching {len(qs)} listings via Playwright..."))
        ok, errors = asyncio.run(_enrich_all(qs, self))
        self.stdout.write(self.style.SUCCESS(f"done: ok={ok} errors={errors}"))
