from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


APPROVED_STATUS = "approved"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy approved GBIF candidates into formal reference_species folders.")
    parser.add_argument("--review-root", type=Path, default=Path("reference_species") / "待复核" / "gbif")
    parser.add_argument("--reference-root", type=Path, default=Path("reference_species"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_review_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("species") and row.get("filename")]


def read_metadata(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {row.get("filename", ""): row for row in csv.DictReader(file) if row.get("filename")}


def append_metadata(path: Path, row: dict[str, str]) -> None:
    fieldnames = ["filename", "species", "scientific_name", "source", "author", "license", "source_url", "gbif_id", "country", "locality", "sex", "note"]
    existing_rows = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            existing_rows = list(csv.DictReader(file))
    if any(item.get("filename") == row.get("filename") for item in existing_rows):
        return
    for item in [*existing_rows, row]:
        for key in item:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: item.get(key, "") for key in fieldnames} for item in existing_rows)
        writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> int:
    args = parse_args()
    review_rows = read_review_rows(args.review_root / "review_status.csv")
    promoted = 0
    skipped = 0

    for review in review_rows:
        if review.get("status") != APPROVED_STATUS:
            skipped += 1
            continue

        species = review["species"]
        filename = review["filename"]
        source_path = args.review_root / species / filename
        if not source_path.exists():
            print(f"[skip] missing source file: {source_path}")
            skipped += 1
            continue

        metadata = read_metadata(args.review_root / species / "metadata.csv")
        metadata_row = metadata.get(filename, {"filename": filename, "species": species, "source": "GBIF"})
        destination_dir = args.reference_root / species
        destination_path = destination_dir / filename
        if destination_path.exists():
            if not args.dry_run:
                append_metadata(destination_dir / "metadata.csv", metadata_row)
            skipped += 1
            continue

        print(f"[promote] {source_path} -> {destination_path}")
        if not args.dry_run:
            destination_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            append_metadata(destination_dir / "metadata.csv", metadata_row)
        promoted += 1

    print(f"promoted={promoted} skipped={skipped} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
