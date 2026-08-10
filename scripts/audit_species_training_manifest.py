from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a species training manifest for class balance and image quality.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest.csv")
    parser.add_argument("--output", type=Path, default=Path("storage") / "training" / "species_manifest_audit.json")
    parser.add_argument("--min-train-images", type=int, default=20)
    parser.add_argument("--min-val-images", type=int, default=5)
    parser.add_argument("--min-width", type=int, default=256)
    parser.add_argument("--min-height", type=int, default=256)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("file_path") and row.get("label")]


def inspect_image(path: Path, min_width: int, min_height: int) -> dict[str, int | bool]:
    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
    return {"width": width, "height": height, "meets_min_size": width >= min_width and height >= min_height}


def main() -> int:
    args = parse_args()
    rows = read_manifest(args.manifest)
    if not rows:
        raise ValueError(f"manifest has no rows: {args.manifest}")

    per_label_split = defaultdict(Counter)
    per_label_quality: dict[str, dict[str, int | float | bool]] = {}
    image_errors: list[str] = []

    for row in rows:
        label = row["label"]
        split = row.get("split") or "train"
        file_path = Path(row["file_path"])
        per_label_split[label][split] += 1

        try:
            image_info = inspect_image(file_path, args.min_width, args.min_height)
        except Exception as exc:  # noqa: BLE001
            image_errors.append(f"{file_path}: {exc.__class__.__name__}: {exc}")
            continue

        current = per_label_quality.setdefault(
            label,
            {"count": 0, "min_width": image_info["width"], "min_height": image_info["height"], "small_images": 0},
        )
        current["count"] = int(current["count"]) + 1
        current["min_width"] = min(int(current["min_width"]), int(image_info["width"]))
        current["min_height"] = min(int(current["min_height"]), int(image_info["height"]))
        current["small_images"] = int(current["small_images"]) + (0 if image_info["meets_min_size"] else 1)

    class_reports: list[dict[str, object]] = []
    for label in sorted(per_label_split):
        train_count = per_label_split[label]["train"]
        val_count = per_label_split[label]["val"]
        total = train_count + val_count
        quality = per_label_quality.get(label, {"count": 0, "min_width": 0, "min_height": 0, "small_images": 0})
        status = "ready"
        if total < args.min_train_images:
            status = "need_more_samples"
        elif val_count < args.min_val_images:
            status = "need_more_validation"
        elif int(quality["small_images"]) > 0:
            status = "has_small_images"

        needed_total = max(0, args.min_train_images - total)
        needed_val = max(0, args.min_val_images - val_count)
        class_reports.append(
            {
                "label": label,
                "train_count": train_count,
                "val_count": val_count,
                "total": total,
                "needed_total": needed_total,
                "needed_val": needed_val,
                "min_width": quality["min_width"],
                "min_height": quality["min_height"],
                "small_images": quality["small_images"],
                "status": status,
            }
        )

    report = {
        "manifest": str(args.manifest),
        "total_rows": len(rows),
        "label_count": len(class_reports),
        "thresholds": {
            "min_train_images": args.min_train_images,
            "min_val_images": args.min_val_images,
            "min_width": args.min_width,
            "min_height": args.min_height,
        },
        "image_errors": image_errors,
        "classes": class_reports,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote audit report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
