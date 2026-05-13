# RealEstate Radar — Project Context for Claude Code

## What this project is
End-to-end pet project: scrape real-estate listings (OLX / Dom.ria), normalise them into Postgres, expose a Django web UI + REST API, and a Telegram bot that sends notifications based on user-defined subscriptions. Built to demonstrate Junior-Middle Python skills: scraping, Django, async bots, Docker, basic CI, data quality.

## Stack (fixed — do not propose alternatives without asking)
- Python 3.11+, managed with `uv`
- `requests` + `beautifulsoup4` for static pages
- `playwright` (NOT Selenium) for JS-rendered pages
- `pydantic` v2 for data validation
- `tenacity` for retries
- Django 5.x + Django REST Framework
- PostgreSQL 16 (via Docker)
- `aiogram` 3.x for the Telegram bot
- Celery + Redis for periodic scraping (Celery Beat)
- Docker + docker-compose for local dev
- `pytest` + `pytest-django` + `responses` for tests
- `ruff` for lint + format (no black, no flake8)
- GitHub Actions for CI

## Repository layout
```
parser/
├── CLAUDE.md
├── README.md
├── AI_WORKFLOW.md
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── scraper/          # standalone scraping package
│   ├── sources/      # one file per site (olx.py, domria.py)
│   ├── models.py     # pydantic schemas
│   └── pipelines.py  # save_to_db, dedupe
├── webapp/           # Django project
│   ├── manage.py
│   ├── config/       # settings, urls, wsgi
│   ├── listings/     # Django app: Listing model, views, admin, API
│   └── monitoring/   # ScrapeRun, ScrapeAlert
├── bot/              # aiogram app
│   ├── handlers/
│   └── main.py
├── tests/
└── .github/workflows/ci.yml
```

## Conventions

### Code style
- Format with `ruff format`, lint with `ruff check --fix`. Line length 100.
- Type hints on every function signature. Run `mypy --strict` on `scraper/` and `bot/`.
- Docstrings: Google style. Only on public functions and classes — skip trivial ones.
- Imports: stdlib → third-party → local, separated by blank lines (ruff handles it).

### Naming
- Functions: `snake_case`, verbs (`fetch_page`, `parse_listing`).
- Classes: `PascalCase`, nouns.
- Constants: `UPPER_SNAKE`.
- Private: leading underscore. No dunder except actual dunders.

### Django specifics
- Fat models, thin views. Business logic in model methods or `services.py`, never in views.
- Use `select_related` / `prefetch_related` whenever a view touches FK/M2M.
- All migrations reviewed by me before commit — never auto-apply on `--merge`.
- Admin: every model gets `list_display`, `list_filter`, `search_fields`.

### Scraper specifics
- Always check for a hidden JSON API in DevTools first — never default to HTML parsing.
- Selectors: prefer `data-*` attributes and stable tag/structure. Forbidden: generated CSS class names like `css-a3xv7p`.
- Every scraper output goes through a Pydantic model before DB write — no raw dicts past `parse_*`.
- Rate limit: 1–3 sec jittered sleep between requests. No exceptions without my approval.
- Rotating User-Agent on every request.

### Error handling
- Never catch bare `Exception`. Catch the narrowest applicable type.
- Network errors → `tenacity` retry with exponential backoff, max 3 attempts.
- Parse errors → log + write to `ScrapeAlert`, do NOT crash the run.
- Telegram bot errors → log + reply to user with a friendly message.

## Rules for Claude Code (read carefully)

### Do without asking
- Generate boilerplate (Pydantic models from a field list, Django admin classes, test scaffolding).
- Refactor for readability within a single file.
- Add type hints to existing functions.
- Write docstrings.
- Suggest improvements in chat — but don't apply them until I say go.

### Ask before doing
- Adding or removing a dependency in `pyproject.toml`.
- Creating or modifying a Django migration.
- Changing model fields once data exists.
- Touching `docker-compose.yml`, `.env.example`, or CI config.
- Anything that costs money (paid APIs, proxies).
- Writing code that handles auth tokens, passwords, or PII.

### Never do
- Use `pip` or `poetry` — this project uses `uv` exclusively.
- Catch `Exception` without a narrower type.
- Hardcode secrets — always `os.environ` via `python-decouple` or Django settings.
- Generate CSS selectors without seeing the actual HTML — ask me for a sample.
- Add `# noqa`, `# type: ignore`, or disable lints to silence errors. Fix the root cause.
- Auto-commit. I review every diff manually.

## Working session checklist (for me, the human)
Before asking Claude to write code:
1. Have I shown it the actual HTML / API response / error message? Not a description — the real thing.
2. Have I named the file it should edit?
3. Have I said what NOT to touch?
4. Will I read every line of the diff before accepting?

## AI workflow log
Every meaningful session I add an entry to `AI_WORKFLOW.md`: what I delegated, what Claude got wrong, what I had to fix, which prompts worked. This file is part of my portfolio.
