"""django-filter FilterSet for the listing list view."""

from __future__ import annotations

from datetime import timedelta

import django_filters
from django import forms
from django.db.models import QuerySet
from django.utils import timezone

from listings.locations import normalize_location, resolve_location
from listings.models import Listing, Operation, Source

# Relative-time windows for the two date filters.
_PERIODS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}
_PERIOD_CHOICES = [
    ("1h", "за годину"),
    ("1d", "за добу"),
    ("3d", "за 3 дні"),
    ("7d", "за тиждень"),
    ("30d", "за місяць"),
]


class ListingFilter(django_filters.FilterSet):
    source = django_filters.ChoiceFilter(
        choices=Source.choices,
        empty_label="всі джерела",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    operation_type = django_filters.ChoiceFilter(
        # Hide the UNKNOWN choice from the dropdown — it's an internal default
        # for the rare mixed-catalog scrape, not something users pick.
        choices=[(v, label) for v, label in Operation.choices if v != Operation.UNKNOWN],
        empty_label="продаж і оренда",
        label="Тип угоди",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    location = django_filters.CharFilter(
        method="filter_location",
        label="Локація",
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "list": "location-suggestions",  # ties to <datalist> in list.html
                "placeholder": "Київ, Печерський, Львів…",
                "autocomplete": "off",
            }
        ),
    )
    # Hard-coded set: OLX + Dom.ria never deliver anything else (USD/EUR/UAH
    # are mapped from raw symbols in scraper/sources/domria.py:_CURRENCY_MAP;
    # OLX returns ISO codes directly and we've only seen these three).
    currency = django_filters.ChoiceFilter(
        field_name="price_currency",
        choices=[("UAH", "UAH"), ("USD", "USD"), ("EUR", "EUR")],
        empty_label="будь-яка",
        label="Валюта",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    min_price = django_filters.NumberFilter(
        field_name="price_value", lookup_expr="gte", label="Ціна від"
    )
    max_price = django_filters.NumberFilter(
        field_name="price_value", lookup_expr="lte", label="Ціна до"
    )
    rooms = django_filters.NumberFilter(method="filter_rooms", label="Кімнат")
    search = django_filters.CharFilter(method="filter_search", label="Пошук")
    published_within = django_filters.ChoiceFilter(
        method="filter_published_within",
        choices=_PERIOD_CHOICES,
        empty_label="будь-коли",
        label="Опубліковано на джерелі",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    added_within = django_filters.ChoiceFilter(
        method="filter_added_within",
        choices=_PERIOD_CHOICES,
        empty_label="будь-коли",
        label="Додано в нашу базу",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )

    class Meta:
        model = Listing
        fields = [
            "source",
            "operation_type",
            "currency",
            "min_price",
            "max_price",
        ]

    def filter_location(self, qs: QuerySet[Listing], name: str, value: str) -> QuerySet[Listing]:
        """Resolve typos/whitespace, then icontains on the prebuilt search column."""
        canonical = resolve_location(value)
        target = normalize_location(canonical or value)
        if not target:
            return qs
        return qs.filter(location_search__icontains=target)

    def filter_rooms(self, qs: QuerySet[Listing], name: str, value: int) -> QuerySet[Listing]:
        return qs.filter(
            params__key="number_of_rooms_string",
            params__normalized_value=value,
        )

    def filter_search(self, qs: QuerySet[Listing], name: str, value: str) -> QuerySet[Listing]:
        return qs.filter(title__icontains=value)

    def filter_published_within(
        self, qs: QuerySet[Listing], name: str, value: str
    ) -> QuerySet[Listing]:
        """Ads published on the source within the window. NULL dates drop out
        naturally — an unknown publish date isn't 'recent'."""
        delta = _PERIODS.get(value)
        if not delta:
            return qs
        return qs.filter(created_at_source__gte=timezone.now() - delta)

    def filter_added_within(
        self, qs: QuerySet[Listing], name: str, value: str
    ) -> QuerySet[Listing]:
        """Listings first scraped into our DB within the window."""
        delta = _PERIODS.get(value)
        if not delta:
            return qs
        return qs.filter(first_seen_at__gte=timezone.now() - delta)
