"""DRF serializers for the public API."""

from __future__ import annotations

from rest_framework import serializers

from listings.models import Listing, ListingParam


class ListingParamSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingParam
        fields = ["key", "name", "value", "normalized_value"]


class ListingSerializer(serializers.ModelSerializer):
    params = ListingParamSerializer(many=True, read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id",
            "source",
            "source_display",
            "source_id",
            "url",
            "title",
            "description",
            "price_value",
            "price_currency",
            "price_negotiable",
            "price_is_free",
            "city",
            "district",
            "region",
            "latitude",
            "longitude",
            "photos",
            "params",
            "is_business",
            "is_promoted",
            "created_at_source",
            "refreshed_at_source",
            "first_seen_at",
            "last_seen_at",
            "enriched_at",
        ]
