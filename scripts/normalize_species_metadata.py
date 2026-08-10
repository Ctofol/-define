from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image

from build_reference_metadata_index import IGNORED_FOLDERS, IMAGE_SUFFIXES, read_metadata, review_status, value


SPECIES_FIELDS = [
    "filename",
    "species",
    "scientific_name",
    "source",
    "author",
    "license",
    "source_url",
    "gbif_id",
    "country",
    "locality",
    "subspecies",
    "sex",
    "width",
    "height",
    "review_status",
    "note",
]


def main() -> int:
    root = Path("reference_species")
    species_latin = load_species_latin(Path("backend") / "app" / "data" / "species_knowledge.json")
    rewritten = 0

    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        if folder.name.startswith(".") or folder.name in IGNORED_FOLDERS:
            continue

        images = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
        if not images:
            continue

        metadata_path = folder / "metadata.csv"
        existing = read_metadata(metadata_path)
        rows: list[dict[str, str]] = []
        for image in images:
            row = existing.get(image.name, {})
            width, height = image_size(image)
            species = value(row, "species") or folder.name
            rows.append(
                {
                    "filename": image.name,
                    "species": species,
                    "scientific_name": value(row, "scientific_name") or species_latin.get(species, ""),
                    "source": value(row, "source") or "unknown",
                    "author": value(row, "author") or "unknown",
                    "license": value(row, "license") or "unknown",
                    "source_url": value(row, "source_url"),
                    "gbif_id": value(row, "gbif_id"),
                    "country": value(row, "country"),
                    "locality": value(row, "locality", "location"),
                    "subspecies": value(row, "subspecies"),
                    "sex": value(row, "sex") or "unknown",
                    "width": str(width or ""),
                    "height": str(height or ""),
                    "review_status": review_status(row, image.name),
                    "note": clean_note(value(row, "note")),
                }
            )

        write_metadata(metadata_path, rows)
        rewritten += 1

    print(f"Normalized metadata.csv in {rewritten} species folders.")
    return 0


def load_species_latin(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item.get("cn_name", "")).strip(): str(item.get("latin_name", "")).strip()
        for item in data
        if isinstance(item, dict) and item.get("cn_name") and item.get("latin_name")
    }


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def clean_note(note: str) -> str:
    if not note:
        return ""
    if "????" in note or "????????" in note:
        return "开放记录图片，需保留来源和授权信息，物种已按目录人工复核"
    return note


def write_metadata(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SPECIES_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
