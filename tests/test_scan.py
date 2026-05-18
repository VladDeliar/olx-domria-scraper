"""ScanLocationView — manual scrape trigger from the listing page."""

from __future__ import annotations

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse


@pytest.fixture
def patch_delay(monkeypatch):
    """Replace `scrape_task.delay` with a recorder so tests don't touch Celery."""
    calls: list[tuple[str, str, int]] = []

    def fake_delay(source, url, pages):
        calls.append((source, url, pages))

        class _Result:
            id = f"fake-{len(calls)}"

        return _Result()

    monkeypatch.setattr("listings.views.scrape_task.delay", fake_delay)
    return calls


@pytest.fixture
def patch_resolve(monkeypatch):
    """Resolver is stubbed so tests don't need 30k gazetteer rows in DB."""

    def _patch(mapping):
        monkeypatch.setattr(
            "listings.views.resolve_location",
            lambda raw, cutoff=80: mapping.get(raw.strip().lower()),
        )

    return _patch


@pytest.mark.django_db
def test_scan_queues_tasks_for_known_city(patch_delay, patch_resolve):
    patch_resolve({"дніпро": "Дніпро"})
    client = Client()
    response = client.post(reverse("listings:scan"), {"location": "Дніпро"})

    assert response.status_code == 302
    # 4 tasks queued: OLX + Dom.ria for rent + sale.
    assert len(patch_delay) == 4
    sources = sorted({c[0] for c in patch_delay})
    assert sources == ["domria", "olx"]
    paths = sorted({c[1] for c in patch_delay})
    assert all("dnepr" in p for p in paths)


@pytest.mark.django_db
def test_scan_respects_operation_filter(patch_delay, patch_resolve):
    patch_resolve({"дніпро": "Дніпро"})
    response = Client().post(
        reverse("listings:scan"), {"location": "Дніпро", "operation_type": "rent"}
    )
    assert response.status_code == 302
    assert len(patch_delay) == 2  # rent only
    assert all("arenda" in c[1] for c in patch_delay)


@pytest.mark.django_db
def test_scan_unknown_city_warns(patch_delay, patch_resolve):
    # Resolver finds the place (it's in the gazetteer) but we have no
    # slug for it — typical for small villages.
    patch_resolve({"андріївка": "Андріївка"})
    response = Client().post(reverse("listings:scan"), {"location": "Андріївка"})

    assert response.status_code == 302
    assert patch_delay == []
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("не підтримується" in m for m in msgs)


@pytest.mark.django_db
def test_scan_dedupes_recent_runs(patch_delay, patch_resolve):
    from listings.models import ScrapeRun
    from listings.scan_targets import build_scrape_targets

    patch_resolve({"дніпро": "Дніпро"})
    # Pre-create a ScrapeRun for one of the 4 Dnipro URLs.
    first_url = build_scrape_targets("Дніпро")[0][1]
    ScrapeRun.objects.create(source="olx", url=first_url, status="success")

    response = Client().post(reverse("listings:scan"), {"location": "Дніпро"})
    assert response.status_code == 302
    # That recent URL skipped; the other three still fire.
    assert len(patch_delay) == 3
    assert first_url not in {c[1] for c in patch_delay}


@pytest.mark.django_db
def test_scan_unresolvable_location_errors(patch_delay, patch_resolve):
    patch_resolve({})  # nothing resolves
    response = Client().post(reverse("listings:scan"), {"location": "Атлантида"})

    assert response.status_code == 302
    assert patch_delay == []
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("Не розпізнав" in m for m in msgs)


@pytest.mark.django_db
def test_scan_blank_location_errors(patch_delay, patch_resolve):
    patch_resolve({})
    response = Client().post(reverse("listings:scan"), {"location": "   "})
    assert response.status_code == 302
    assert patch_delay == []
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("Не вказана" in m for m in msgs)
