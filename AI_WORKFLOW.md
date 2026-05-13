# AI Workflow Log

A running log of how I work with Claude Code on this project. Each entry covers: what I delegated, what the AI did well, what it got wrong, how I fixed it, which prompts worked. This file is part of my portfolio — it's the evidence behind any answer to "how do you actually use AI".

---

## Operating principles

1. **Real artefacts beat descriptions.** Before asking Claude to write a scraper for a page, I paste the actual HTML. Before asking it to fix an error, I paste the full traceback. Vague prompts produce vague code.
2. **Name the file and the scope.** "Edit `scraper/sources/olx.py`, only the `parse_listing` function" works. "Improve the scraper" does not.
3. **Read every diff.** Claude can produce plausible-looking code that silently swallows exceptions, hardcodes assumptions, or misuses the framework. The cost of skipping review is non-obvious bugs in production.
4. **Persist rules, don't re-state them.** Anything I correct twice goes into [CLAUDE.md](CLAUDE.md). Within a project I stop repeating myself; across projects I keep a personal library of these conventions.
5. **AI generates, I decide.** Architecture, dependencies, data-model trade-offs — I own. Boilerplate, repetitive refactors, test scaffolding — Claude owns.

---

## Session log

### 2026-05-13 — Day 0: project setup

**Delegated:**
- Drafted `CLAUDE.md` from a structured outline I described (stack, conventions, do/don't rules).
- Drafted `README.md` skeleton with roadmap, stack table, quick-start.
- Drafted `.gitignore` for Python + Django + Docker + IDE.

**Worked well:**
- TODO

**Got wrong / had to fix:**
- TODO

**Prompts that worked:**
- TODO

**Takeaway:**
- TODO

---

<!-- Template for new entries:

### YYYY-MM-DD — Day N: <topic>

**Delegated:**
- 

**Worked well:**
- 

**Got wrong / had to fix:**
- 

**Prompts that worked:**
- 

**Takeaway:**
- 

---
-->
