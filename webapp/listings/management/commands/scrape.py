"""Run the scraper and persist results to the DB.

    python manage.py scrape olx    URL [--pages N]
    python manage.py scrape domria URL [--pages N]
"""

from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from django.utils import timezone

from bot.notifier import notify_new_listing
from listings.models import ScrapeRun
from listings.pipelines import save_listing
from scraper.sources import domria, olx

_SOURCES = {"olx": olx, "domria": domria}


class Command(BaseCommand):
    help = "Scrape listings from a source URL into the DB."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("source", choices=sorted(_SOURCES))
        parser.add_argument("url")
        parser.add_argument("--pages", type=int, default=1)

    def handle(self, *args: Any, **opts: Any) -> None:
        source_name: str = opts["source"]
        url: str = opts["url"]
        pages: int = opts["pages"]
        source = _SOURCES[source_name]

        run = ScrapeRun.objects.create(
            source=source_name,
            url=url,
            pages_requested=pages,
        )
        self.stdout.write(
            self.style.NOTICE(f"[run {run.id}] {source_name} {url} pages={pages}")
        )

        scraped = new = updated = errors = notified = 0
        try:
            for listing in source.iter_listings(url, max_pages=pages):
                try:
                    orm_obj, created = save_listing(listing)
                    scraped += 1
                    if created:
                        new += 1
                        try:
                            notified += notify_new_listing(orm_obj)
                        except (DatabaseError, OSError) as exc:
                            self.stderr.write(
                                f"[run {run.id}] notify failed for {orm_obj.source_id}: {exc}"
                            )
                    else:
                        updated += 1
                except (DatabaseError, ValueError, TypeError) as exc:
                    errors += 1
                    self.stderr.write(
                        f"[run {run.id}] save failed for {listing.source_id}: {exc}"
                    )
        except (DatabaseError, OSError) as exc:
            run.status = ScrapeRun.Status.FAILED
            run.error_message = repr(exc)
            run.finished_at = timezone.now()
            run.scraped_count = scraped
            run.new_count = new
            run.updated_count = updated
            run.error_count = errors
            run.save()
            raise CommandError(f"scrape failed: {exc}") from exc

        run.status = ScrapeRun.Status.SUCCESS
        run.finished_at = timezone.now()
        run.scraped_count = scraped
        run.new_count = new
        run.updated_count = updated
        run.error_count = errors
        run.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"[run {run.id}] done: scraped={scraped} new={new} "
                f"updated={updated} errors={errors} notified={notified}"
            )
        )
