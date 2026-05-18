"""Load HDX UNOCHA Ukraine admin-boundaries CSVs into GazetteerLocation.

    python manage.py load_gazetteer gazetteer/        # default path
    python manage.py load_gazetteer /path/to/dir --truncate

Files expected (HDX naming convention):
    ukr_admgz_adm1_*.csv   — oblasts            (~27)
    ukr_admgz_adm2_*.csv   — raions             (~139)
    ukr_admgz_adm4_*.csv   — settlements        (~30 000)

We deliberately skip adm0 (just Ukraine) and adm3 (территоріальні громади —
names like "Іллінецька Рада" aren't what users type when searching).
"""

from __future__ import annotations

import csv
from argparse import ArgumentParser
from collections.abc import Iterator
from glob import glob
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from listings.locations import invalidate_known_locations_cache, normalize_location
from listings.models import GazetteerLocation

# ADM4_TYPE_UA → our Kind enum value.
_TYPE_MAP: dict[str, str] = {
    "Міста": GazetteerLocation.Kind.CITY,
    "Mіста": GazetteerLocation.Kind.CITY,  # the data has a typo here (latin M)
    "Селища міського типу (СМТ)": GazetteerLocation.Kind.TOWN,
    "Сільські населені пункти (СНП)": GazetteerLocation.Kind.VILLAGE,
}


def _open_utf8_bom(path: Path) -> Any:
    return open(path, encoding="utf-8-sig", newline="")


def _iter_adm1(path: Path) -> Iterator[dict[str, Any]]:
    with _open_utf8_bom(path) as f:
        for row in csv.DictReader(f):
            name = (row.get("ADM1_UA") or "").strip()
            if not name:
                continue
            yield {
                "name": name,
                "kind": GazetteerLocation.Kind.OBLAST,
                "parent_path": "",
                "koatuu": (row.get("KOATUU") or "").strip(),
                "lat": _to_float(row.get("ADM1_RP_LAT")),
                "lon": _to_float(row.get("ADM1_RP_LON")),
            }


def _iter_adm2(path: Path) -> Iterator[dict[str, Any]]:
    with _open_utf8_bom(path) as f:
        for row in csv.DictReader(f):
            name = (row.get("ADM2_UA") or "").strip()
            if not name:
                continue
            yield {
                "name": name,
                "kind": GazetteerLocation.Kind.RAION,
                "parent_path": (row.get("ADM1_UA") or "").strip(),
                "koatuu": (row.get("KOATUU") or "").strip(),
                "lat": _to_float(row.get("ADM2_RP_LAT")),
                "lon": _to_float(row.get("ADM2_RP_LON")),
            }


def _iter_adm4(path: Path) -> Iterator[dict[str, Any]]:
    with _open_utf8_bom(path) as f:
        for row in csv.DictReader(f):
            name = (row.get("ADM4_UA") or "").strip()
            if not name:
                continue
            type_ua = (row.get("ADM4_TYPE_UA") or "").strip()
            kind = _TYPE_MAP.get(type_ua, GazetteerLocation.Kind.OTHER)
            parent = " > ".join(
                p
                for p in (
                    (row.get("ADM1_UA") or "").strip(),
                    (row.get("ADM2_UA") or "").strip(),
                )
                if p
            )
            yield {
                "name": name,
                "kind": kind,
                "parent_path": parent,
                "koatuu": (row.get("KOATUU") or "").strip(),
                "lat": _to_float(row.get("ADM4_RP_LAT")),
                "lon": _to_float(row.get("ADM4_RP_LON")),
            }


def _to_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _resolve_one(pattern: Path) -> Path | None:
    matches = glob(str(pattern))
    return Path(matches[0]) if matches else None


class Command(BaseCommand):
    help = "Load HDX UNOCHA Ukraine admin boundaries into GazetteerLocation."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "directory",
            type=Path,
            nargs="?",
            default=Path("gazetteer"),
            help="Directory with ukr_admgz_adm{1,2,4}_*.csv files (default: gazetteer/).",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Delete existing GazetteerLocation rows first.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="bulk_create batch size (default: 1000).",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        directory: Path = opts["directory"]
        if not directory.is_dir():
            raise CommandError(f"{directory} is not a directory")

        adm1 = _resolve_one(directory / "ukr_admgz_adm1_*.csv")
        adm2 = _resolve_one(directory / "ukr_admgz_adm2_*.csv")
        adm4 = _resolve_one(directory / "ukr_admgz_adm4_*.csv")
        missing = [
            label
            for label, path in (("adm1", adm1), ("adm2", adm2), ("adm4", adm4))
            if path is None
        ]
        if missing:
            raise CommandError(f"missing CSV files: {', '.join(missing)}")

        with transaction.atomic():
            if opts["truncate"]:
                deleted, _ = GazetteerLocation.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"deleted {deleted} existing rows"))

            total = 0
            for label, path, iterator in (
                ("adm1 oblasts", adm1, _iter_adm1(adm1)),
                ("adm2 raions", adm2, _iter_adm2(adm2)),
                ("adm4 settlements", adm4, _iter_adm4(adm4)),
            ):
                self.stdout.write(f"loading {label} from {path.name}...")
                count = self._load(iterator, batch_size=opts["batch_size"])
                self.stdout.write(self.style.SUCCESS(f"  + {count}"))
                total += count

        invalidate_known_locations_cache()
        self.stdout.write(self.style.SUCCESS(f"done: {total} GazetteerLocation rows"))

    def _load(self, rows: Iterator[dict[str, Any]], *, batch_size: int) -> int:
        batch: list[GazetteerLocation] = []
        count = 0
        for row in rows:
            batch.append(
                GazetteerLocation(
                    name=row["name"],
                    normalized=normalize_location(row["name"]),
                    kind=row["kind"],
                    parent_path=row["parent_path"],
                    koatuu=row["koatuu"],
                    latitude=row["lat"],
                    longitude=row["lon"],
                )
            )
            if len(batch) >= batch_size:
                GazetteerLocation.objects.bulk_create(batch, ignore_conflicts=True)
                count += len(batch)
                batch = []
        if batch:
            GazetteerLocation.objects.bulk_create(batch, ignore_conflicts=True)
            count += len(batch)
        return count
