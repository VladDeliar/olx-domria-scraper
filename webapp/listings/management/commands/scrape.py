"""Run the scraper and persist results to the DB.

    python manage.py scrape olx    URL [--pages N]
    python manage.py scrape domria URL [--pages N]

Thin wrapper around `listings.tasks.run_scrape` — the same code path Celery
uses, so behaviour stays identical whether triggered manually or by Beat.
"""

from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from listings.tasks import _SOURCES, run_scrape


class Command(BaseCommand):
    help = "Scrape listings from a source URL into the DB."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("source", choices=sorted(_SOURCES))
        parser.add_argument("url")
        parser.add_argument("--pages", type=int, default=1)

    def handle(self, *args: Any, **opts: Any) -> None:
        try:
            result = run_scrape(opts["source"], opts["url"], opts["pages"])
        except (DatabaseError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"[run {result['run_id']}] {result['source']} done: "
                f"scraped={result['scraped']} new={result['new']} "
                f"updated={result['updated']} errors={result['errors']} "
                f"notified={result['notified']}"
            )
        )
