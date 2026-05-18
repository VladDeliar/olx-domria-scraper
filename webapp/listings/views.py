"""HTML views: list + filters, detail, dashboard."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from listings.filters import ListingFilter
from listings.locations import get_known_locations
from listings.models import Listing, ScrapeAlert, ScrapeRun, Source, Subscription


class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 24

    def get_queryset(self):
        qs = Listing.objects.all().prefetch_related("params").order_by("-last_seen_at")
        self.filter = ListingFilter(self.request.GET, queryset=qs)
        return self.filter.qs.distinct()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filter
        ctx["total"] = self.filter.qs.distinct().count()
        # Feeds the <datalist id="location-suggestions"> in list.html. Cached
        # inside get_known_locations() — cheap per-request.
        ctx["location_suggestions"] = get_known_locations()
        return ctx


class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("params")


class DashboardView(TemplateView):
    template_name = "listings/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["total"] = Listing.objects.count()
        ctx["by_source"] = list(
            Listing.objects.values("source").annotate(n=Count("id")).order_by("-n")
        )
        ctx["by_operation"] = list(
            Listing.objects.values("operation_type").annotate(n=Count("id")).order_by("-n")
        )
        ctx["by_district"] = list(
            Listing.objects.exclude(district="")
            .values("district")
            .annotate(
                n=Count("id"),
                avg_uah=Avg("price_value", filter=Q(price_currency="UAH")),
                avg_usd=Avg("price_value", filter=Q(price_currency="USD")),
            )
            .order_by("-n")[:15]
        )
        ctx["recent_runs"] = ScrapeRun.objects.order_by("-started_at")[:8]
        ctx["active_subscriptions"] = Subscription.objects.filter(is_active=True).count()

        # 30-day chart data: scraped_count per source per day.
        since = timezone.now() - timedelta(days=30)
        rows = (
            ScrapeRun.objects.filter(started_at__gte=since)
            .annotate(day=TruncDate("started_at"))
            .values("day", "source")
            .annotate(scraped=Sum("scraped_count"))
            .order_by("day")
        )
        days = sorted({r["day"].isoformat() for r in rows})
        per_source: dict[str, dict[str, int]] = {s.value: {} for s in Source}
        for r in rows:
            per_source[r["source"]][r["day"].isoformat()] = r["scraped"] or 0
        ctx["chart_data"] = json.dumps(
            {
                "labels": days,
                "datasets": [
                    {
                        "label": dict(Source.choices)[src],
                        "data": [per_source[src].get(d, 0) for d in days],
                    }
                    for src in per_source
                ],
            },
            ensure_ascii=False,
        )

        ctx["recent_alerts"] = ScrapeAlert.objects.filter(resolved=False).select_related(
            "run", "listing"
        )[:15]
        ctx["alert_counts"] = {
            "open": ScrapeAlert.objects.filter(resolved=False).count(),
            "today": ScrapeAlert.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=1)
            ).count(),
        }
        return ctx
