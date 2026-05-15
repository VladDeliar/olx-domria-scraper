# AI Workflow Log

A running log of how I work with Claude Code on this project. Each entry covers: what I delegated, what the AI did well, what it got wrong, how I fixed it, which prompts worked.

This file is part of my portfolio — it's evidence behind any answer to "how do you actually use AI".

---

## Operating principles

1. **Real artefacts beat descriptions.** Before asking Claude to write a scraper for a page, I paste the actual HTML. Before asking it to fix an error, I paste the full traceback. Vague prompts produce vague code.
2. **Name the file and the scope.** "Edit `scraper/sources/olx.py`, only the `parse_listing` function" works. "Improve the scraper" does not.
3. **Read every diff.** Claude can produce plausible-looking code that silently swallows exceptions, hardcodes assumptions, or misuses the framework. The cost of skipping review is non-obvious bugs in production.
4. **Persist rules, don't re-state them.** Anything I correct twice goes into [`CLAUDE.md`](CLAUDE.md). Within a project I stop repeating myself; across projects I keep a personal library of these conventions.
5. **AI generates, I decide.** Architecture, dependencies, data-model trade-offs — I own. Boilerplate, repetitive refactors, test scaffolding — Claude owns.

---

## Session log

### Day 0 — project bootstrap

**Delegated:** drafting `CLAUDE.md` from a structured outline (stack, conventions, do/don't rules), `README.md` skeleton with roadmap, `.gitignore` for Python + Django + Docker + IDE, project init via `uv init`, first git commit.

**Worked well:** the `CLAUDE.md` rules turn out to be the single highest-leverage artefact for the rest of the project. Each subsequent session reuses them — no re-stating conventions, no drift on naming or error-handling style.

**Got wrong:** nothing significant on Day 0. The plan is small, the AI is good at boilerplate.

**Takeaway:** invest in the conventions file early. The 30 min of writing it returned multiple hours over the project.

### Day 1 — OLX scraper via embedded JSON state

**Delegated:** scaffold of `scraper/sources/olx.py` and `scraper/models.py`. Initial prompt was *"write an OLX rental parser"*.

**Got wrong:** first cut produced generic CSS selectors (`.css-a3xv7p`) that would have broken on OLX's first front-end deploy. Selectors were also invented — not derived from the actual HTML.

**How I fixed it:** opened OLX in DevTools myself, found `window.__PRERENDERED_STATE__=` in the page source — a JSON dump of the entire React state. Rewrote the prompt: *"Don't parse HTML. Find the JSON state in the script tag, decode it, and parse `state.listing.listing.ads`."* That worked first try.

**Prompts that worked:** "Here is the actual structure of one ad in the state JSON. Build a Pydantic model and a parser that extracts these specific fields. Skip ads that fail validation, don't crash the run."

**Takeaway:** AI defaults to the most-common pattern in its training data. For scraping that's HTML+CSS parsing. **The first question I now ask on any new site is "is there a JSON state blob?"** — `scraper/recon.py` (written this day) automates that probe.

### Day 4–5 — Playwright detail enrichment, mobile-UA bug

**Delegated:** `scraper/browser.py` (Playwright context manager), `scraper/sources/olx_detail.py` (detail parser), `manage.py enrich` command.

**Got wrong (subtle one):** smoke-test of one listing worked, returning a 3300-char description. But running the same code on 5 listings via the management command returned `desc=0 chars` every time. The Playwright selector was the same, the URLs were valid, no errors raised.

**How I fixed it:** added a flag to dump the raw rendered HTML to disk. Grepped for `ad_description`. Not found. But found `data-platform="mobile"` on the `<html>` tag — OLX was serving the **mobile** layout, which has a different DOM. Root cause: `fake_useragent.random` was returning mobile UAs by chance. Pinned a fixed desktop Chrome UA in `browser.py`. All 5 listings now return 119–3371 char descriptions.

**Prompts that worked:** "Add an env-flag debug dump of the raw HTML to a file. I want to see what the page actually looks like when it fails, not when it succeeds."

**Takeaway:** when AI code "just works" on one input and silently fails on N inputs, the difference is in the inputs, not the code. Build a fast feedback loop (HTML dump, screenshot) before guessing at the bug.

### Day 6 — bot notifier, sync ORM in async function

**Delegated:** aiogram bot with FSM (`/subscribe`, `/list`, `/clear`), notifier that matches new listings to subscriptions.

**Got wrong (×3, all caught by running the real scrape with a live subscription):**

1. `SynchronousOnlyOperation`: the notifier's `_candidate_subscriptions` called `Subscription.objects.filter(...).select_related(...)` from inside an async function. Django 5 has async ORM (`aget`, `acreate`), but mixing async + sync mid-function gets messy. **Fix:** push all ORM work into a sync helper, wrap with `sync_to_async` once.
2. OLX stores `number_of_rooms_string.normalized_value` as a category slug (`'odnokomnatnye'`), not an int. The matcher did `int(value)` and crashed. **Fix:** parser-side coercion + a matcher-side fallback map for legacy rows.
3. OLX puts small towns (Kolomyia, etc.) in the `city` field with `district` empty. A subscription typed as "district=Коломия" never matched. **Fix:** the matcher now checks the user-typed "district" against either `listing.district` or `listing.city`.

**How I caught them:** real end-to-end test. Created a subscription via the bot, scraped real URLs, watched what the notifier did. None of these bugs would surface in an integration test that didn't cross the sync/async boundary or use real OLX data.

**Takeaway:** test pyramid for AI-generated code skews toward **integration tests over real data**. Unit tests miss exactly the kinds of bugs AI produces — interface assumptions and field-shape mismatches.

### Day 10 — Celery + Beat on Windows without Docker

**Delegated:** `config/celery.py`, settings wiring, `listings/tasks.py` with `run_scrape` + `@shared_task`, refactor of `manage.py scrape` to call the same core.

**Side quest:** project plan wanted Redis-in-Docker. BIOS virtualisation is disabled → Docker Desktop won't start → no Postgres, no Redis. Found **Memurai** (Redis-compatible Windows-native service, installs via winget, no virtualisation needed). One `winget install` later, broker on `redis://localhost:6379/0` works.

**Got wrong (Windows-specific):** first `celery -A config worker` run hung with no output. Cause: Celery defaults to a `prefork` worker pool, which uses `fork()`, which Windows doesn't have. **Fix:** `--pool=solo`.

**Takeaway:** AI-generated config presumes Linux. On Windows, expect to add `--pool=solo` flags, `setx` env vars instead of `export`, and to watch for path-separator issues in scripts. Worth documenting these once in the conventions file so the AI stops suggesting Linux-only fixes.

### Day 11 — anomaly detection, the bi-modal-catalog story

**Delegated:** `ScrapeAlert` model, `anomaly.py` with `check_listing` + `check_run`.

**First implementation worked structurally but produced 26 alerts on a single scrape.** Cause: the OLX URL we use mixes apartment **sales** (millions of UAH) and **rents** (tens of thousands). Mean peer price was ~3.7M UAH, so every rent listing flagged as "0.0× of avg".

**How I fixed it without adding a new model field:** restricted the peer cohort to listings within ±100× of the candidate's own price (effectively "same order of magnitude"). Switched mean → median for robustness against the remaining skew. Same re-scrape now generates 6 outlier alerts instead of 26, and they're genuine — the real fix (an `operation_type` field) is documented in the README's "Known limitations".

**Takeaway:** anomaly thresholds tuned in isolation always fire on real data. Always run a real workload before claiming the detector "works".

### Day 12 — tests + CI, ruff revealed 3 real bugs

**Delegated:** scaffolding 32 pytest cases across 6 files, fixture builders for OLX/Dom.ria, GitHub Actions workflow, applying `ruff format` across the repo.

**What `ruff check` caught that I missed reading the diffs:**

1. `try/except PlaywrightTimeout: pass` in `olx_detail.py` — `ruff` says use `contextlib.suppress`. It's right.
2. `Notification` model missing `__str__` — `DJ008` from `flake8-django`. Added.
3. `class Source(str, Enum)` in `scraper/models.py` — `UP042` recommends `StrEnum`, which is the right idiom in Python 3.11+.

**False positives I had to ignore:** `RUF012` (mutable class default) fires on every Django `Meta.indexes`, `Meta.fields`, `list_display`, etc. — these are framework conventions, not Python class attributes in the bug-prone sense. Same with `RUF001-3` on Ukrainian text (Cyrillic 'а' vs Latin 'a' looks ambiguous to ruff but is intentional in user-facing strings). Added all four to `ignore` in `pyproject.toml` with comments explaining why.

**Takeaway:** tests catch behaviour bugs, linting catches code-smell bugs. The two categories barely overlap, and skipping either one leaves visible holes. Worth ~20 minutes per project to get both green from day one.

---

## Misc principles I've started keeping

- **One commit = one verifiable change**, with the *why* in the message. Bug fixes describe the symptom + root cause + how it was found, not just the diff.
- Never let the AI add `# noqa` or `# type: ignore` to "silence" an error. Either fix it or document why the rule is wrong (and ignore the rule globally with a comment).
- When AI suggests adding a library to solve a 30-line problem, push back. `dj-database-url`, `python-dotenv-vault`, etc. are usually replaceable by a function you can read end-to-end in a minute.
