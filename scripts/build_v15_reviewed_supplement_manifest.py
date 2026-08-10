from __future__ import annotations

import csv
import hashlib
import argparse
from pathlib import Path


BASE_MANIFEST = Path("storage") / "training" / "species_manifest.csv"
SUPPLEMENT_ROOT = Path("reference_species") / "_supplement_candidates"
OUTPUT = Path("storage") / "training" / "species_manifest_v15_reviewed_supplement.csv"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SKIP_DIRS = {"viverrids_quality_pass"}
LABEL_ALIASES = {
    "亚洲黑熊": "黑熊",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manifest with reviewed supplement candidate images.")
    parser.add_argument("--base-manifest", type=Path, default=BASE_MANIFEST)
    parser.add_argument("--supplement-root", type=Path, default=SUPPLEMENT_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_reviewed_images(root: Path) -> list[tuple[str, Path]]:
    images: list[tuple[str, Path]] = []
    for species_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if species_dir.name in SKIP_DIRS:
            continue
        for image_path in sorted(species_dir.iterdir()):
            if image_path.name.startswith("contact_sheet"):
                continue
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            images.append((species_dir.name, image_path))
    return images


def main() -> int:
    args = parse_args()
    rows = [row for row in read_csv(args.base_manifest) if row.get("file_path") and row.get("label")]
    seen_hashes = {row.get("sha256", "") for row in rows if row.get("sha256")}
    added_by_label: dict[str, int] = {}
    skipped_duplicates = 0

    for raw_label, image_path in iter_reviewed_images(args.supplement_root):
        label = LABEL_ALIASES.get(raw_label, raw_label)
        resolved_image_path = image_path.resolve()
        sha256 = file_sha256(image_path)
        if sha256 in seen_hashes:
            skipped_duplicates += 1
            continue
        rows.append(
            {
                "file_path": str(resolved_image_path),
                "folder_name": f"_supplement_candidates/{raw_label}",
                "label": label,
                "split": "train",
                "relative_path": resolved_image_path.relative_to(Path.cwd()).as_posix(),
                "review_status": "manual_review_confirmed_supplement",
                "sha256": sha256,
            }
        )
        seen_hashes.add(sha256)
        added_by_label[label] = added_by_label.get(label, 0) + 1

    fieldnames = ["file_path", "folder_name", "label", "split", "relative_path", "review_status", "sha256"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)

    print(f"base_rows={len(rows) - sum(added_by_label.values())}")
    print(f"supplement_added={sum(added_by_label.values())}")
    print(f"skipped_duplicates={skipped_duplicates}")
    for label, count in sorted(added_by_label.items()):
        print(f"{label}={count}")
    print(f"output_rows={len(rows)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
