from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from listings.models import Listing, ListingParam, ScrapeRun


class ListingParamInline(admin.TabularInline):
    model = ListingParam
    extra = 0
    fields = ("key", "name", "value", "normalized_value")
    readonly_fields = fields


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "source",
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
