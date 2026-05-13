"""DRF viewsets — read-only HTTP API on top of the same FilterSet as HTML views."""

from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from listings.filters import ListingFilter
from listings.models import Listing
from listings.serializers import ListingSerializer


class ListingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Listing.objects.prefetch_related("params").order_by("-last_seen_at")
    serializer_class = ListingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ListingFilter
    search_fields = ["title", "description", "city", "district"]
    ordering_fields = ["price_value", "last_seen_at", "first_seen_at", "created_at_source"]
