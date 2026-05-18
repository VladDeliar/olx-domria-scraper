from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from listings.models import (
    Listing,
    ListingParam,
    Notification,
    ScrapeAlert,
    ScrapeRun,
    Subscription,
    TelegramUser,
)


class ListingParamInline(admin.TabularInline):
    model = ListingParam
    extra = 0
    fields = ("key", "name", "value", "normalized_value")
    readonly_fields = fields


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "operation_type",
        "source_id",
        "title_short",
        "price_display",
        "city",
        "district",
        "is_promoted",
        "enriched_at",
        "last_seen_at",
    )
    list_filter = (
        "source",
        "operation_type",
        "city",
        "district",
        "price_currency",
        "is_promoted",
        "is_business",
        ("enriched_at", admin.EmptyFieldListFilter),
    )
    search_fields = ("source_id", "title", "description", "district", "city")
    readonly_fields = ("first_seen_at", "last_seen_at", "enriched_at", "open_link")
    inlines = [ListingParamInline]
    list_per_page = 50
    date_hierarchy = "last_seen_at"

    @admin.display(description="Title")
    def title_short(self, obj: Listing) -> str:
        return obj.title[:60]

    @admin.display(description="Price")
    def price_display(self, obj: Listing) -> str:
        if obj.price_is_free:
            return "free"
        if obj.price_value is None:
            return "—"
        return f"{obj.price_value:,.0f} {obj.price_currency}"

    @admin.display(description="Open on source")
    def open_link(self, obj: Listing) -> str:
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.url, obj.url)


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ("tg_user_id", "username", "first_name", "is_active", "registered_at")
    list_filter = ("is_active",)
    search_fields = ("tg_user_id", "username", "first_name")
    readonly_fields = ("registered_at", "last_active_at")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "source",
        "district",
        "city",
        "min_price",
        "max_price",
        "currency",
        "min_rooms",
        "max_rooms",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "source", "currency")
    search_fields = ("user__username", "user__tg_user_id", "district", "city")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "listing", "sent_at")
    list_filter = ("sent_at",)
    search_fields = ("user__username", "listing__source_id")
    readonly_fields = ("sent_at",)
    date_hierarchy = "sent_at"


@admin.register(ScrapeAlert)
class ScrapeAlertAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "severity",
        "category",
        "message_short",
        "run",
        "listing",
        "resolved",
    )
    list_filter = ("severity", "category", "resolved")
    search_fields = ("message", "context")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    actions = ["mark_resolved"]

    @admin.display(description="Message")
    def message_short(self, obj: ScrapeAlert) -> str:
        return obj.message[:80]

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, qs) -> None:
        qs.update(resolved=True)


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "started_at",
        "status",
        "pages_fetched",
        "scraped_count",
        "new_count",
        "updated_count",
        "error_count",
    )
    list_filter = ("source", "status")
    search_fields = ("url", "error_message")
    readonly_fields = ("started_at", "finished_at")
    date_hierarchy = "started_at"
