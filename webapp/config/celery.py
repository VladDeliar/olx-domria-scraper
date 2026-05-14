"""Celery application for periodic scraping.

Broker: Redis (Memurai on Windows — see .env.example for URL).
Pool: `solo` is the only reliable choice on Windows in dev (prefork
needs fork()). Start workers with `--pool=solo` accordingly.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("realestate_radar")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
