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
def test_scan_unknown_with_no_gazetteer_row_warns(patch_delay, patch_resolve):
    """Resolver returns canonical, but no GazetteerLocation row exists →
    no parent oblast to fall back to → 'unsupported' warning."""
    patch_resolve({"мерефа": "Мерефа"})
    response = Client().post(reverse("listings:scan"), {"location": "Мерефа"})

    assert response.status_code == 302
    assert patch_delay == []
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("не вдається просканувати" in m for m in msgs)


@pytest.mark.django_db
def test_scan_falls_back_to_oblast_for_village(patch_delay, patch_resolve):
    """Village resolves, has gazetteer row with parent oblast → scan oblast URLs."""
    from listings.models import GazetteerLocation

    GazetteerLocation.objects.create(
        name="Підгайчики",
        normalized="підгайчики",
        kind="village",
        parent_path="Тернопільська > Чортківський",
    )
    patch_resolve({"підгайчики": "Підгайчики"})

    response = Client().post(reverse("listings:scan"), {"location": "Підгайчики"})
    assert response.status_code == 302
    # 4 oblast-level targets queued (Тернопільська: olx=ter, domria=obl-ternopolskaya).
    assert len(patch_delay) == 4
    urls = {c[1] for c in patch_delay}
    assert any("/ter/" in u for u in urls)
    assert any("obl-ternopolskaya" in u for u in urls)
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("мала громада" in m and "Тернопільська" in m for m in msgs)


@pytest.mark.django_db
def test_scan_unsupported_when_parent_oblast_missing(patch_delay, patch_resolve):
    """Defensive — gazetteer row exists but its first parent isn't in LOCATION_SLUGS."""
    from listings.models import GazetteerLocation

    GazetteerLocation.objects.create(
        name="EdgePlace",
        normalized="edgeplace",
        kind="village",
        parent_path="UnknownOblast > UnknownRaion",
    )
    patch_resolve({"edgeplace": "EdgePlace"})

    response = Client().post(reverse("listings:scan"), {"location": "EdgePlace"})
    assert patch_delay == []
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("не вдається просканувати" in m for m in msgs)


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
