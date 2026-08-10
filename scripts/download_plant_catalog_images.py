from __future__ import annotations

"""Download one reusable GBIF image per plant knowledge-card entry.

Only CC0, CC BY 4.0 and CC BY-SA 4.0 media are accepted.  The catalog keeps the original
GBIF occurrence URL, creator and license beside the local display image.
"""

import argparse
import json
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image


GBIF_API = "https://api.gbif.org/v1"
ALLOWED_LICENSE_MARKERS = (
    "creativecommons.org/publicdomain/zero/1.0",
    "creativecommons.org/licenses/by/4.0",
    "creativecommons.org/licenses/by-sa/4.0",
    "cc0_1_0",
    "cc_by_4_0",
    "cc_by_sa_4_0",
)
COUNTRIES = ("CN", "VN", "LA", "MM", "TH")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download CC0/CC BY GBIF plant images for the local knowledge catalog.")
    parser.add_argument("--catalog", type=Path, default=Path("backend/app/data/plant_species_catalog.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("frontend/public/plants"))
    parser.add_argument("--limit", type=int, default=0, help="0 processes every entry.")
    parser.add_argument("--species-ids", nargs="*", default=[], help="Optional exact species_id subset for resume runs.")
    parser.add_argument("--remove-species-ids", nargs="*", default=[], help="Remove named locally generated covers and their metadata.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--audit-existing", action="store_true", help="Remove generated covers backed by specimen records before retrying.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.25)
    return parser.parse_args()


def get_json(url: str, timeout: int) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "WildlifePlantKnowledge/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_bytes(url: str, timeout: int) -> bytes:
    request = Request(url, headers={"User-Agent": "WildlifePlantKnowledge/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def is_allowed(value: object) -> bool:
    return isinstance(value, str) and any(marker in value.lower() for marker in ALLOWED_LICENSE_MARKERS)


def first_candidate(latin_name: str, timeout: int, rejected_sources: list[str]) -> tuple[dict[str, object], dict[str, object]] | None:
    match = get_json(f"{GBIF_API}/species/match?{urlencode({'name': latin_name})}", timeout)
    key = match.get("usageKey")
    if not key:
        return None
    params: list[tuple[str, str]] = [("taxon_key", str(key)), ("media_type", "StillImage"), ("limit", "60")]
    params.extend(("country", code) for code in COUNTRIES)
    payload = get_json(f"{GBIF_API}/occurrence/search?{urlencode(params)}", timeout)
    for occurrence in payload.get("results", []):
        if not isinstance(occurrence, dict):
            continue
        if str(occurrence.get("basisOfRecord") or "").upper() in {"PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "FOSSIL_SPECIMEN"}:
            continue
        occurrence_id = occurrence.get("gbifID") or occurrence.get("key")
        source_url = f"https://www.gbif.org/occurrence/{occurrence_id}"
        if source_url in set(rejected_sources):
            continue
        for media in occurrence.get("media") or []:
            if not isinstance(media, dict):
                continue
            license_value = media.get("license") or occurrence.get("license")
            identifier = media.get("identifier") or media.get("references")
            if is_allowed(license_value) and isinstance(identifier, str) and identifier.startswith("http"):
                return occurrence, media
    return None


def occurrence_key(source_url: object) -> str:
    return str(source_url or "").rstrip("/").rsplit("/", 1)[-1]


def clear_image_metadata(row: dict[str, object]) -> None:
    source_url = str(row.get("image_source_url") or "")
    if source_url:
        rejected = list(row.get("rejected_image_sources") or [])
        row["rejected_image_sources"] = list(dict.fromkeys([*rejected, source_url]))
    for key in ("image_url", "image_source_url", "image_author", "image_license", "image_basis_of_record"):
        row.pop(key, None)


def save_jpeg(data: bytes, destination: Path) -> bool:
    try:
        with Image.open(BytesIO(data)) as image:
            image = image.convert("RGB")
            if min(image.size) < 280:
                return False
            image.thumbnail((1280, 1280))
            image.save(destination, format="JPEG", quality=88, optimize=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    args = parse_args()
    rows = json.loads(args.catalog.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    removed = 0
    for row in rows:
        if row["species_id"] not in set(args.remove_species_ids):
            continue
        image_path = args.output_dir / f"{row['species_id']}.jpg"
        if image_path.exists():
            image_path.unlink()
        if row.get("image_url"):
            clear_image_metadata(row)
            removed += 1
    if removed:
        args.catalog.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"removed={removed}")
    selected = [row for row in rows if not args.species_ids or row["species_id"] in set(args.species_ids)]
    selected = selected[: args.limit] if args.limit else selected
    updated = 0
    skipped = 0
    for row in selected:
        image_path = args.output_dir / f"{row['species_id']}.jpg"
        if args.audit_existing and image_path.exists() and row.get("image_source_url"):
            try:
                existing = get_json(f"{GBIF_API}/occurrence/{occurrence_key(row['image_source_url'])}", args.timeout)
                basis = str(existing.get("basisOfRecord") or "").upper()
                if basis in {"PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "FOSSIL_SPECIMEN"}:
                    image_path.unlink()
                    clear_image_metadata(row)
                    args.catalog.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    print(f"[removed-specimen] {row['cn_name']}")
                else:
                    row["image_basis_of_record"] = basis
                    args.catalog.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                print(f"[audit-skip] {row['cn_name']}: {exc.__class__.__name__}")
        if image_path.exists() and row.get("image_url") and not args.overwrite:
            skipped += 1
            continue
        try:
            candidate = first_candidate(str(row["latin_name"]), args.timeout, list(row.get("rejected_image_sources") or []))
            if not candidate:
                print(f"[skip] {row['cn_name']}: no CC0/CC BY GBIF image")
                skipped += 1
                continue
            occurrence, media = candidate
            image_url = str(media.get("identifier") or media.get("references"))
            if not save_jpeg(get_bytes(image_url, args.timeout), image_path):
                print(f"[skip] {row['cn_name']}: unreadable or too small")
                skipped += 1
                continue
            occurrence_id = occurrence.get("gbifID") or occurrence.get("key")
            row.update(
                {
                    "image_url": f"/plants/{image_path.name}",
                    "image_source_url": f"https://www.gbif.org/occurrence/{occurrence_id}",
                    "image_author": str(media.get("creator") or occurrence.get("recordedBy") or "GBIF contributor"),
                    "image_license": str(media.get("license") or occurrence.get("license") or "CC BY/CC0"),
                    "image_basis_of_record": str(occurrence.get("basisOfRecord") or ""),
                }
            )
            updated += 1
            args.catalog.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[done] {row['cn_name']}: {image_path.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {row['cn_name']}: {exc.__class__.__name__}")
            skipped += 1
        time.sleep(args.sleep)
    print(f"updated={updated} skipped={skipped} total={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
