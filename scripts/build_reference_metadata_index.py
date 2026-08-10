from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
IGNORED_FOLDERS = {"_supplement_candidates", "待复核"}
INDEX_FIELDS = [
    "folder",
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
    knowledge_path = Path("backend") / "app" / "data" / "species_knowledge.json"
    species_latin = load_species_latin(knowledge_path)
    rows: list[dict[str, str]] = []

    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        if folder.name.startswith(".") or folder.name in IGNORED_FOLDERS:
            continue
        metadata = read_metadata(folder / "metadata.csv")
        images = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
        for image in images:
            row = metadata.get(image.name, {})
            width, height = image_size(image)
            species = value(row, "species") or folder.name
            rows.append(
                {
                    "folder": folder.name,
                    "filename": image.name,
                    "species": species,
                    "scientific_name": value(row, "scientific_name") or species_latin.get(species, ""),
                    "source": value(row, "source"),
                    "author": value(row, "author"),
                    "license": value(row, "license"),
                    "source_url": value(row, "source_url"),
                    "gbif_id": value(row, "gbif_id"),
                    "country": value(row, "country"),
                    "locality": value(row, "locality", "location"),
                    "subspecies": value(row, "subspecies"),
                    "sex": value(row, "sex"),
                    "width": str(width or ""),
                    "height": str(height or ""),
                    "review_status": review_status(row, image.name),
                    "note": value(row, "note"),
                }
            )

    output_path = root / "metadata_index.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")
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


def read_metadata(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        raw_rows = list(csv.reader(file))
    if not raw_rows:
        return {}

    header = raw_rows[0]
    rows = [normalize_row(header, row) for row in raw_rows[1:] if row]
    metadata: dict[str, dict[str, str]] = {}
    for row in rows:
        filename = value(row, "filename", "file_name", "candidate")
        if filename:
            metadata[filename] = row
    return metadata


def normalize_row(header: list[str], row: list[str]) -> dict[str, object]:
    # Some early per-species files kept a short header, then received later GBIF
    # rows with the richer 12-column schema. Rebuild those rows by position.
    if len(row) == 12 and len(header) < 12 and looks_like_latin(row[2]):
        keys = [
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
            "sex",
            "note",
        ]
        return dict(zip(keys, row))

    normalized: dict[str, object] = {}
    for index, key in enumerate(header):
        normalized[key] = row[index] if index < len(row) else ""
    if len(row) > len(header):
        normalized["_extra"] = row[len(header) :]
    return normalized


def looks_like_latin(text: str) -> bool:
    parts = text.strip().split()
    return len(parts) >= 2 and all(part[:1].isupper() or part.islower() for part in parts[:2])


def value(row: dict[str, object], *keys: str) -> str:
    for key in keys:
        raw = row.get(key)
        if raw is None:
            continue
        if isinstance(raw, list):
            raw = " | ".join(str(part) for part in raw if part)
        text = str(raw).strip()
        if text:
            return text
    return ""


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def review_status(row: dict[str, object], filename: str) -> str:
    source = value(row, "source")
    note = value(row, "note")
    if "待复核" in note or "待授权" in filename:
        return "pending_review"
    if source in {"用户提供", "PDF图册", "GBIF/iNaturalist"}:
        return "reviewed_reference"
    return "pending_review"


if __name__ == "__main__":
    raise SystemExit(main())
