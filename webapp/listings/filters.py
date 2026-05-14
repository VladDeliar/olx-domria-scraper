"""django-filter FilterSet for the listing list view."""

from __future__ import annotations

import django_filters
from django.db.models import QuerySet

from listings.models import Listing, Source


class ListingFilter(django_filters.FilterSet):
    source = django_filters.ChoiceFilter(choices=Source.choices, empty_label="всі джерела")
    city = django_filters.CharFilter(lookup_expr="icontains", label="Місто")
    district = django_filters.CharFilter(lookup_expr="icontains", label="Район")
    currency = django_filters.CharFilter(
        field_name="price_currency", lookup_expr="iexact", label="Валюта"
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
        fields = ["source", "city", "district", "currency", "min_price", "max_price"]

    def filter_rooms(self, qs: QuerySet[Listing], name: str, value: int) -> QuerySet[Listing]:
        return qs.filter(
            params__key="number_of_rooms_string",
            params__normalized_value=value,
        )

    def filter_search(self, qs: QuerySet[Listing], name: str, value: str) -> QuerySet[Listing]:
        return qs.filter(title__icontains=value)
