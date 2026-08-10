from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_IGNORED_FOLDERS = {"_supplement_candidates", "待复核", "亚洲黑熊"}
DEFAULT_CANONICAL_LABELS = {
    "亚洲黑熊": "黑熊",
}
EXCLUDED_REVIEW_STATUSES = {"reject", "duplicate", "reference_only"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a training manifest from reference_species folders.")
    parser.add_argument("--reference-root", type=Path, default=Path("reference_species"))
    parser.add_argument("--output", type=Path, default=Path("storage") / "training" / "species_manifest.csv")
    parser.add_argument("--canonical-map", type=Path, default=None, help="Optional JSON file mapping folder names to canonical labels.")
    parser.add_argument("--review-status", type=Path, default=Path("reference_species") / "training_review_status.csv")
    parser.add_argument("--include-review-excluded", action="store_true")
    parser.add_argument("--min-images", type=int, default=1)
    parser.add_argument("--include-ignored", action="store_true")
    parser.add_argument("--validate-images", action="store_true")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    return parser.parse_args()


def load_canonical_map(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return DEFAULT_CANONICAL_LABELS
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return {str(key): str(value) for key, value in payload.items()}


def iter_image_files(folder: Path) -> Iterable[Path]:
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            yield path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_review_status(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        return {
            row["relative_path"].replace("\\", "/"): row.get("status", "")
            for row in rows
            if row.get("relative_path")
        }


def main() -> int:
    args = parse_args()
    canonical_map = load_canonical_map(args.canonical_map)
    review_status = load_review_status(args.review_status)
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    duplicate_rows: list[dict[str, str]] = []
    seen_hashes: dict[str, str] = {}
    reference_root = args.reference_root
    if not reference_root.exists():
        raise FileNotFoundError(f"reference root not found: {reference_root}")

    candidates_by_label: dict[str, list[dict[str, str]]] = {}
    for folder in sorted([item for item in reference_root.iterdir() if item.is_dir()]):
        if not args.include_ignored and (folder.name.startswith("_") or folder.name in DEFAULT_IGNORED_FOLDERS):
            continue

        images = list(iter_image_files(folder))
        if len(images) < args.min_images:
            continue

        label = canonical_map.get(folder.name, folder.name)
        for image_path in images:
            if args.validate_images:
                from PIL import Image

                with Image.open(image_path) as image:
                    image.verify()

            relative_path = str(image_path.relative_to(reference_root).as_posix())
            status = review_status.get(relative_path, "")
            if status in EXCLUDED_REVIEW_STATUSES and not args.include_review_excluded:
                continue
            image_hash = file_sha256(image_path)
            if image_hash in seen_hashes:
                duplicate_rows.append(
                    {
                        "file_path": str(image_path.resolve()),
                        "relative_path": relative_path,
                        "label": label,
                        "duplicate_of": seen_hashes[image_hash],
                        "sha256": image_hash,
                    }
                )
                continue
            seen_hashes[image_hash] = relative_path

            candidates_by_label.setdefault(label, []).append(
                {
                    "file_path": str(image_path.resolve()),
                    "folder_name": folder.name,
                    "label": label,
                    "split": "",
                    "relative_path": relative_path,
                    "review_status": status,
                    "sha256": image_hash,
                }
            )

    for label, label_rows in sorted(candidates_by_label.items()):
        label_rows.sort(key=lambda row: hashlib.sha1(f"{label}/{row['relative_path']}".encode("utf-8")).hexdigest())
        val_quota = max(1, round(len(label_rows) * args.val_ratio)) if len(label_rows) >= 5 else 0
        for index, row in enumerate(label_rows):
            row["split"] = "val" if index < val_quota else "train"
            rows.append(row)

    fieldnames = ["file_path", "folder_name", "label", "split", "relative_path", "review_status", "sha256"]
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    duplicate_output = output.with_name(f"{output.stem}_duplicates.csv")
    with duplicate_output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["file_path", "relative_path", "label", "duplicate_of", "sha256"])
        writer.writeheader()
        writer.writerows(duplicate_rows)

    print(f"wrote {len(rows)} rows to {output}")
    print(f"wrote {len(duplicate_rows)} duplicate rows to {duplicate_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
