"""HTML views: list + filters, detail, dashboard."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from celery.result import AsyncResult
from django.contrib import messages
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from listings.filters import ListingFilter
from listings.locations import (
    get_known_locations,
    get_oblast_settlements,
    get_oblasts,
    resolve_location,
)
from listings.models import Listing, ScrapeAlert, ScrapeRun, Source, Subscription
from listings.scan_targets import find_scan_strategy, supported_cities
from listings.tasks import scrape_task

_SORTS: dict[str, tuple[Any, ...]] = {
    "newest": ("-last_seen_at",),
    # nulls_last so price-less listings never crowd the top of a price sort.
    "price_asc": (F("price_value").asc(nulls_last=True), "-last_seen_at"),
    "price_desc": (F("price_value").desc(nulls_last=True), "-last_seen_at"),
}


class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 24

    def get_queryset(self):
        qs = Listing.objects.all().prefetch_related("params")
        self.filter = ListingFilter(self.request.GET, queryset=qs)
        sort = self.request.GET.get("sort", "newest")
        order = _SORTS.get(sort, _SORTS["newest"])
        return self.filter.qs.distinct().order_by(*order)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filter
        ctx["total"] = self.filter.qs.distinct().count()
        ctx["sort"] = self.request.GET.get("sort", "newest")
        # Feeds the <datalist id="location-suggestions"> in list.html. Cached
        # inside get_known_locations() — cheap per-request.
        ctx["location_suggestions"] = get_known_locations()
        # Feeds the "Область" cascade <select>. ~27 names, cached 24 h.
        ctx["oblasts"] = get_oblasts()
        return ctx


def oblast_settlements_json(request: HttpRequest) -> JsonResponse:
    """Cascade endpoint: cities + towns inside `?oblast=…` as JSON.

    Powers the Область → Місто dropdown on the list page. Plain JsonResponse
    — no DRF, no serialisation; the payload is just a list of strings.
    """
    oblast = request.GET.get("oblast", "")
    return JsonResponse({"settlements": get_oblast_settlements(oblast)})


class ScanLocationView(View):
    """POST endpoint behind the 'Просканувати зараз' button on the list page.

    Resolves the user's typed location, looks up our hand-curated city-slug
    map, and fires `scrape_task.delay` per source URL. Dedupes against
    ScrapeRuns started within the last 5 minutes — doubles as soft rate-limit
    and protects us from accidentally hammering OLX/Dom.ria on impatient
    button-mashing.
    """

    _RECENT_WINDOW = timedelta(minutes=5)

    def post(self, request: HttpRequest) -> HttpResponse:
        raw = (request.POST.get("location") or "").strip()
        operation = (request.POST.get("operation_type") or "").strip() or None
        list_url = reverse("listings:list")

        if not raw:
            messages.error(request, "Не вказана локація для сканування.")
            return redirect(list_url)

        canonical = resolve_location(raw)
        if not canonical:
            messages.error(request, f"Не розпізнав локацію «{raw}».")
            return redirect(f"{list_url}?location={raw}")

        kind, scan_key, targets = find_scan_strategy(canonical, operation=operation)
        if kind == "unsupported":
            sample = ", ".join(supported_cities()[:8])
            messages.warning(
                request,
                f"«{canonical}» поки не вдається просканувати — нема ні прямої "
                f"сторінки на джерелах, ні відомої батьківської області. "
                f"Доступні великі міста, серед них: {sample}, …",
            )
            return redirect(f"{list_url}?location={canonical}")

        cutoff = timezone.now() - self._RECENT_WINDOW
        recent_urls = set(
            ScrapeRun.objects.filter(started_at__gte=cutoff).values_list("url", flat=True)
        )
        task_ids: list[str] = []
        for source, url in targets:
            if url in recent_urls:
                continue
            task_ids.append(scrape_task.delay(source, url, 1).id)
        queued = len(task_ids)
        # Stash IDs so the list page can poll /scan/status/ for the "+N" notice.
        request.session["scan_tasks"] = task_ids

        if not queued:
            messages.info(
                request,
                f"«{scan_key}» вже сканувалось у останні 5 хвилин — нові таски "
                "не потрібні. Оновіть сторінку щоб побачити свіжі результати.",
            )
        elif kind == "oblast":
            messages.info(
                request,
                f"«{canonical}» — мала громада, окремої сторінки на джерелах нема. "
                f"Сканую всю {scan_key} обл. ({queued} з {len(targets)} джерел, "
                f"це ~30 секунд). «{canonical}» з'явиться у списку, якщо для нього "
                "хоч одне оголошення опубліковане.",
            )
        else:
            messages.info(
                request,
                f"Сканування «{canonical}» почато ({queued} з {len(targets)} джерел).",
            )
        suffix = "&scan=running" if queued else ""
        return redirect(f"{list_url}?location={canonical}{suffix}")


def scan_status(request: HttpRequest) -> JsonResponse:
    """Poll endpoint for the list page's scan-progress banner.

    Reads the Celery task IDs stashed in the session by ScanLocationView and
    reports aggregate progress. Once every task is ready, sums the
    {new, updated, errors} counts each `scrape_task` returns and consumes the
    session key so the "+N" notice fires exactly once.
    """
    ids = request.session.get("scan_tasks") or []
    if not ids:
        return JsonResponse({"active": False})

    results = [AsyncResult(tid) for tid in ids]
    done = [r for r in results if r.ready()]
    if len(done) < len(results):
        return JsonResponse(
            {"active": True, "finished": False, "done": len(done), "total": len(results)}
        )

    new = updated = errors = 0
    for r in results:
        if r.successful() and isinstance(r.result, dict):
            new += r.result.get("new", 0)
            updated += r.result.get("updated", 0)
            errors += r.result.get("errors", 0)
    request.session.pop("scan_tasks", None)
    return JsonResponse(
        {"active": True, "finished": True, "new": new, "updated": updated, "errors": errors}
    )


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
