# Loading the Ukrainian gazetteer

The location resolver in `webapp/listings/locations.py` falls back to a
`GazetteerLocation` table when a typed place isn't in our own scraped data
(see [Two-tier resolver](#two-tier-resolver) below). That table is populated
from the official **HDX UNOCHA Ukraine admin-boundaries gazetteer**.

The CSV files themselves are **not committed** to keep the repo lean (~21 MB
of redundant reference data that anyone can re-download). The DB row count
is what matters; the source files are needed only for the one-shot loader.

## Get the files

1. Open <https://data.humdata.org/dataset/cod-ab-ukr> (Common Operational
   Datasets — Administrative Boundaries — Ukraine).
2. Download the most recent CSV bundle — looks like
   `ukr_admgz_<DATE>.zip` or individual files
   `ukr_admgz_adm{0,1,2,3,4}_<DATE>.csv`.
3. Unzip into a `gazetteer/` folder at the repo root. Expected layout:

   ```
   gazetteer/
   ├── ukr_admgz_adm1_*.csv   # oblasts (~27)
   ├── ukr_admgz_adm2_*.csv   # raions (~139)
   └── ukr_admgz_adm4_*.csv   # settlements (~30 000)
   ```

   `adm0` and `adm3` files are ignored by the loader if present.

## Load into the DB

### Docker mode

```bash
docker compose cp gazetteer web:/app/gazetteer
docker compose exec web python manage.py load_gazetteer /app/gazetteer
```

Reload from scratch:

```bash
docker compose exec web python manage.py load_gazetteer /app/gazetteer --truncate
```

### Local (no Docker)

```bash
uv run python webapp/manage.py load_gazetteer gazetteer/
```

## Two-tier resolver

`resolve_location("Дніпро")` tries in this order:

1. **In-data tier** — distinct `Listing.city ∪ district` values. ~50–200
   names. Cached 5 min. Powers the `<datalist>` autocomplete on the site so
   users see only places that actually have listings.
2. **Gazetteer tier** — the `GazetteerLocation` table loaded by this command.
   ~30 000 names. Cached 24 h (admin boundaries don't change often).

Fuzzy match across both tiers uses `rapidfuzz.fuzz.ratio` (C++,
20-50× faster than stdlib `difflib`).

## Why this isn't in git

- The CSVs are public-domain reference data — anyone can re-download.
- `gazetteer/ukr_admgz_adm4_*.csv` alone is 13 MB. With history this would
  bloat the repo.
- The actual project data (Postgres `listings_gazetteerlocation`) is a Docker
  volume, persistent across restarts. If you ever `docker compose down -v`
  (wipes volumes), rerun the loader.

## Updating the snapshot

HDX republishes the file when admin boundaries change (rare — last big change
was the 2020 raion consolidation). To update:

1. Download newer `ukr_admgz_<DATE>.zip` from HDX.
2. Replace files in `gazetteer/`.
3. `manage.py load_gazetteer gazetteer/ --truncate` — wipes the old set and
   loads the new one in one transaction.
