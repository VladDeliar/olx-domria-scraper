"""Celery tasks. Auto-discovered by config/celery.py via app.autodiscover_tasks()."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.db import DatabaseError
from django.utils import timezone

from bot.notifier import notify_new_listing
from listings.anomaly import check_listing, check_run
from listings.models import ScrapeRun
from listings.pipelines import save_listing
from scraper.sources import domria, olx

logger = logging.getLogger(__name__)

_SOURCES = {"olx": olx, "domria": domria}


def run_scrape(source_name: str, url: str, pages: int = 1) -> dict[str, Any]:
    """Synchronous core. Reused by the management command and the Celery task.

    Returns a dict of counters suitable for logging / Celery result.
    """
    if source_name not in _SOURCES:
        raise ValueError(f"unknown source: {source_name!r}")
    source = _SOURCES[source_name]

    run = ScrapeRun.objects.create(
        source=source_name, url=url, pages_requested=pages
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
                        logger.warning(
                            "notify failed for %s: %s", orm_obj.source_id, exc
                        )
                else:
                    updated += 1
                check_listing(orm_obj)
            except (DatabaseError, ValueError, TypeError) as exc:
                errors += 1
                logger.warning("save failed for %s: %s", listing.source_id, exc)
    except (DatabaseError, OSError) as exc:
        run.status = ScrapeRun.Status.FAILED
        run.error_message = repr(exc)
        run.finished_at = timezone.now()
        run.scraped_count = scraped
        run.new_count = new
        run.updated_count = updated
        run.error_count = errors
        run.save()
        raise

    run.status = ScrapeRun.Status.SUCCESS
    run.finished_at = timezone.now()
    run.scraped_count = scraped
    run.new_count = new
    run.updated_count = updated
    run.error_count = errors
    run.save()
    alerts = list(check_run(run))
    if alerts:
        logger.warning("run #%s raised %d alerts", run.id, len(alerts))

    return {
        "run_id": run.id,
        "source": source_name,
        "scraped": scraped,
        "new": new,
        "updated": updated,
        "errors": errors,
        "notified": notified,
    }


@shared_task(name="listings.scrape", bind=True, max_retries=3, default_retry_delay=60)
def scrape_task(self, source_name: str, url: str, pages: int = 1) -> dict[str, Any]:
    """Celery wrapper around run_scrape with retry on network errors."""
    try:
        result = run_scrape(source_name, url, pages)
    except OSError as exc:
        # Retry on transient network/IO errors.
        raise self.retry(exc=exc) from exc
    logger.info("scrape done: %s", result)
    return result
