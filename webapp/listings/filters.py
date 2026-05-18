"""django-filter FilterSet for the listing list view."""

from __future__ import annotations

import django_filters
from django import forms
from django.db.models import QuerySet

from listings.models import Listing, Operation, Source


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
    city = django_filters.CharFilter(lookup_expr="icontains", label="Місто")
    district = django_filters.CharFilter(lookup_expr="icontains", label="Район")
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

    class Meta:
        model = Listing
        fields = [
            "source",
            "operation_type",
            "city",
            "district",
            "currency",
            "min_price",
            "max_price",
        ]

    def filter_rooms(self, qs: QuerySet[Listing], name: str, value: int) -> QuerySet[Listing]:
        return qs.filter(
            params__key="number_of_rooms_string",
            params__normalized_value=value,
        )

    def filter_search(self, qs: QuerySet[Listing], name: str, value: str) -> QuerySet[Listing]:
        return qs.filter(title__icontains=value)
