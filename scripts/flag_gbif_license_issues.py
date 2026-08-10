from __future__ import annotations

import argparse
import csv
from pathlib import Path

from download_gbif_reference_images import is_allowed_media_license


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reject GBIF candidates whose media license is not allowed.")
    parser.add_argument("--root", type=Path, default=Path("reference_species") / "待复核" / "gbif")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    review_path = args.root / "review_status.csv"
    review_rows = read_csv(review_path)
    by_key = {(row.get("species", ""), row.get("filename", "")): row for row in review_rows}

    flagged = 0
    for folder in sorted([path for path in args.root.iterdir() if path.is_dir()]) if args.root.exists() else []:
        for metadata in read_csv(folder / "metadata.csv"):
            filename = metadata.get("filename", "")
            license_value = metadata.get("license", "")
            if not filename or is_allowed_media_license(license_value):
                continue

            key = (folder.name, filename)
            row = by_key.get(key, {"species": folder.name, "filename": filename})
            if row.get("status") != "reject" or row.get("reason") != "license_not_allowed":
                flagged += 1
            row["status"] = "reject"
            row["reason"] = "license_not_allowed"
            row["note"] = license_value
            by_key[key] = row

    merged_rows = sorted(by_key.values(), key=lambda row: (row.get("species", ""), row.get("filename", "")))
    fieldnames = ["species", "filename", "status", "reason", "note"]
    for row in merged_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    if not args.dry_run:
        write_csv(review_path, merged_rows, fieldnames)

    print(f"flagged={flagged} rows={len(merged_rows)} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
