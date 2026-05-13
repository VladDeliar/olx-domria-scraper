"""HTML views: list + filters, detail, dashboard."""

from __future__ import annotations

from typing import Any

from django.db.models import Avg, Count, Q
from django.views.generic import DetailView, ListView, TemplateView

from listings.filters import ListingFilter
from listings.models import Listing, ScrapeRun, Subscription


class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 24

    def get_queryset(self):
        qs = (
            Listing.objects.all()
            .prefetch_related("params")
            .order_by("-last_seen_at")
        )
        self.filter = ListingFilter(self.request.GET, queryset=qs)
        return self.filter.qs.distinct()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filter
        ctx["total"] = self.filter.qs.distinct().count()
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
        return ctx
