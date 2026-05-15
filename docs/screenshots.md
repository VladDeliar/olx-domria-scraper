# How to capture portfolio screenshots

Take these 4–5 screenshots and save them under `docs/img/` (PNG, ≤500 KB each).
After they're committed, the README will embed them automatically (see the
`<!-- screenshots -->` section).

## Recommended set

| File | What to capture | How |
|---|---|---|
| `list.png` | Listing list with sidebar filters and 6+ cards visible | http://127.0.0.1:8000/ — apply one filter (e.g. district=Печерський) so reviewers see filtering works |
| `detail.png` | Listing detail page with image carousel and params table | http://127.0.0.1:8000/<some-pk>/ — pick an enriched listing for a richer description |
| `dashboard.png` | Dashboard with 30-day Chart.js graph and the open-alerts panel | http://127.0.0.1:8000/dashboard/ — scrape a few times first so the chart has data |
| `admin.png` | Django admin Listing changelist with filters visible | http://127.0.0.1:8000/admin/listings/listing/ |
| `telegram.png` | Telegram chat with bot showing /start + /subscribe FSM dialog | screenshot from your phone or Telegram Desktop |

## Tips

- Use **Windows Snipping Tool** (`Win+Shift+S`) or **ShareX** for clean crops.
- Resize to ~1600 px wide before committing — full 4K screenshots bloat the repo.
- Use a clean browser profile (no random tabs, no extension toolbars).
- For Telegram, hide your real username/phone if visible.

## Compressing PNGs

After capture, run any of:

```powershell
# Optional, if installed
optipng -o4 docs\img\*.png
```

…or upload to https://tinypng.com/ and re-save.

## Embedding in README

Once you commit `docs/img/list.png` etc., uncomment the screenshots block in
`README.md` (the markers tell you which lines).
