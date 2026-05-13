# RealEstate Radar

End-to-end real-estate aggregator: scrapes listings from OLX / Dom.ria, stores them in PostgreSQL, serves a Django web UI + REST API, and pushes Telegram notifications for user-defined subscriptions (district / price / area filters).

> Pet project to demonstrate Junior–Middle Python skills: web scraping, Django, async Telegram bots, Docker, CI, data quality.

---

## Status

Work in progress. See the [14-day build plan](#roadmap) below.

## Architecture

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Scraper     │──▶│  PostgreSQL  │◀──│  Django UI   │
│  (Celery)    │   │              │   │  + REST API  │
└──────────────┘   └──────┬───────┘   └──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  Telegram    │
                   │  bot (aiogram)│
                   └──────────────┘
```

Detailed component breakdown lives in [CLAUDE.md](CLAUDE.md).

## Tech stack

| Layer       | Tools                                          |
|-------------|------------------------------------------------|
| Language    | Python 3.11+, managed with `uv`                |
| Scraping    | `requests` + `beautifulsoup4`, `playwright`    |
| Validation  | `pydantic` v2, `tenacity`                      |
| Web         | Django 5.x, Django REST Framework              |
| Bot         | `aiogram` 3.x                                  |
| Storage     | PostgreSQL 16, Redis                           |
| Scheduling  | Celery + Celery Beat                           |
| Infra       | Docker, docker-compose                         |
| Tooling     | `ruff`, `mypy`, `pytest`, GitHub Actions       |

## Quick start

```bash
# 1. Clone and enter
git clone https://github.com/<user>/realestate-radar.git
cd realestate-radar

# 2. Configure env
cp .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, POSTGRES_PASSWORD, etc.

# 3. Run everything
docker compose up --build
```

The Django UI will be available at http://localhost:8000, admin at /admin.

## Local development without Docker

```bash
uv sync
uv run python webapp/manage.py migrate
uv run python webapp/manage.py runserver
```

## Project layout

See [CLAUDE.md](CLAUDE.md) for the canonical layout and conventions.

## Roadmap

- [ ] **Day 0** — Project skeleton: `CLAUDE.md`, `README.md`, `pyproject.toml`, git
- [ ] **Days 1–2** — OLX scraper (Requests + BS4), Pydantic models
- [ ] **Day 3** — PostgreSQL + Django ORM, dedupe via `update_or_create`
- [ ] **Days 4–5** — Playwright for JS-rendered detail pages
- [ ] **Day 6** — Telegram bot (aiogram): subscriptions, notifications
- [ ] **Days 7–8** — Django UI: list, filters, dashboard, REST API
- [ ] **Day 9** — Docker + docker-compose for all services
- [ ] **Day 10** — Celery + Celery Beat for scheduled scraping
- [ ] **Day 11** — Data validation, anomaly detection, scrape-run metrics
- [ ] **Day 12** — Tests + GitHub Actions CI
- [ ] **Day 13** — Documentation polish, architecture diagram
- [ ] **Day 14** — Deploy (Railway / Fly.io), make repo public

## Working with AI

This project is built using Claude Code as the primary development tool. The full log of what worked, what didn't, and lessons learned lives in [AI_WORKFLOW.md](AI_WORKFLOW.md).

## License

MIT
