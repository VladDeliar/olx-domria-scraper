"""Database models for scraped real-estate listings.

Mirrors the Pydantic schemas in `scraper/models.py`, but as Django ORM.
Pydantic is the wire/validation format; Django is the storage format.
The pipeline in `scraper/pipelines.py` converts one to the other.
"""

from __future__ import annotations

from django.db import models


class Source(models.TextChoices):
    OLX = "olx", "OLX"
    DOMRIA = "domria", "Dom.ria"


class Listing(models.Model):
    source = models.CharField(max_length=16, choices=Source.choices)
    source_id = models.CharField(max_length=64, help_text="Native ID on the source site.")
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")

    price_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=8, blank=True, default="")
    price_negotiable = models.BooleanField(default=False)
    price_is_free = models.BooleanField(default=False)

    region = models.CharField(max_length=100, blank=True, default="")
    region_id = models.IntegerField(null=True, blank=True)
    city = models.CharField(max_length=100, blank=True, default="")
    city_id = models.IntegerField(null=True, blank=True)
    district = models.CharField(max_length=100, blank=True, default="")
    district_id = models.IntegerField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    photos = models.JSONField(default=list, blank=True)

    category_id = models.IntegerField(null=True, blank=True)
    is_business = models.BooleanField(default=False)
    is_promoted = models.BooleanField(default=False)

    created_at_source = models.DateTimeField(null=True, blank=True)
    refreshed_at_source = models.DateTimeField(null=True, blank=True)
    valid_to_source = models.DateTimeField(null=True, blank=True)

    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    # Detail-page enrichment (filled by `manage.py enrich`, source-specific shape)
    extras = models.JSONField(default=dict, blank=True)
    enriched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "source_id"], name="uniq_source_id"),
        ]
        indexes = [
            models.Index(fields=["source", "last_seen_at"]),
            models.Index(fields=["city", "district"]),
            models.Index(fields=["price_value"]),
        ]
        ordering = ["-last_seen_at"]

    def __str__(self) -> str:
        return f"[{self.source}:{self.source_id}] {self.title[:60]}"


class ListingParam(models.Model):
    """Typed attribute on a listing (floor, area, rooms, etc.)."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="params")
    key = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    value = models.CharField(max_length=500)
    normalized_value = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["listing", "key"])]
        unique_together = [("listing", "key")]

    def __str__(self) -> str:
        return f"{self.key}={self.value}"


class TelegramUser(models.Model):
    """A user who started a chat with our bot."""

    tg_user_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=64, blank=True, default="")
    first_name = models.CharField(max_length=64, blank=True, default="")
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self) -> str:
        tag = f"@{self.username}" if self.username else self.first_name
        return f"{tag} ({self.tg_user_id})"


class Subscription(models.Model):
    """User-defined filter set; new listings matching it are pushed to Telegram."""

    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="subscriptions"
    )
    source = models.CharField(max_length=16, choices=Source.choices, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    min_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    max_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="If price bounds are set, only listings in this currency match.",
    )
    min_rooms = models.IntegerField(null=True, blank=True)
    max_rooms = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_active", "user"])]

    def __str__(self) -> str:
        parts = []
        if self.district:
            parts.append(self.district)
        if self.min_price or self.max_price:
            lo = f"{self.min_price:.0f}" if self.min_price else ""
            hi = f"{self.max_price:.0f}" if self.max_price else ""
            parts.append(f"{lo}-{hi} {self.currency}".strip())
        if self.min_rooms or self.max_rooms:
            lo = self.min_rooms or ""
            hi = self.max_rooms or ""
            parts.append(f"{lo}-{hi}к")
        return " | ".join(parts) or "any"


class Notification(models.Model):
    """One sent notification — prevents pinging the same user about the same listing twice."""

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="notifications")
    listing = models.ForeignKey(
        "Listing", on_delete=models.CASCADE, related_name="notifications"
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "listing")]
        ordering = ["-sent_at"]


class ScrapeRun(models.Model):
    """One execution of the scraper for observability."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    source = models.CharField(max_length=16, choices=Source.choices)
    url = models.URLField(max_length=500)
    pages_requested = models.IntegerField(default=1)
    pages_fetched = models.IntegerField(default=0)
    scraped_count = models.IntegerField(default=0)
    new_count = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    error_message = models.TextField(blank=True, default="")

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["source", "started_at"])]

    def __str__(self) -> str:
        return f"{self.source} {self.started_at:%Y-%m-%d %H:%M} ({self.status})"
