from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from PIL import Image


def test_audit_species_training_manifest_generates_report(tmp_path: Path):
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (320, 240), color=(120, 80, 60)).save(image_path)

    manifest_path = tmp_path / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["file_path", "folder_name", "label", "split", "relative_path"])
        writer.writeheader()
        writer.writerow(
            {
                "file_path": str(image_path),
                "folder_name": "猕猴",
                "label": "猕猴",
                "split": "train",
                "relative_path": "猕猴/sample.jpg",
            }
        )

    output_path = tmp_path / "audit.json"
    subprocess.run(
        [
            "python",
            "scripts\\audit_species_training_manifest.py",
            "--manifest",
            str(manifest_path),
            "--output",
            str(output_path),
            "--min-train-images",
            "1",
            "--min-val-images",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["total_rows"] == 1
    assert report["label_count"] == 1
    assert report["classes"][0]["label"] == "猕猴"


def test_build_species_training_manifest_ignores_black_bear_alias_folder(tmp_path: Path):
    reference_root = tmp_path / "reference_species"
    canonical_folder = reference_root / "黑熊"
    alias_folder = reference_root / "亚洲黑熊"
    canonical_folder.mkdir(parents=True)
    alias_folder.mkdir(parents=True)
    for index in range(5):
        color = (index * 40, 80 + index * 20, 60 + index * 30)
        Image.new("RGB", (320, 320), color=color).save(canonical_folder / f"black_bear_{index}.png")
        Image.new("RGB", (320, 320), color=color).save(alias_folder / f"alias_black_bear_{index}.png")

    output_path = tmp_path / "manifest.csv"
    subprocess.run(
        [
            "python",
            "scripts\\build_species_training_manifest.py",
            "--reference-root",
            str(reference_root),
            "--output",
            str(output_path),
            "--min-images",
            "5",
            "--validate-images",
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
    )

    with output_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    duplicate_path = output_path.with_name("manifest_duplicates.csv")
    with duplicate_path.open("r", encoding="utf-8-sig", newline="") as file:
        duplicate_rows = list(csv.DictReader(file))

    assert len(rows) == 5
    assert {row["folder_name"] for row in rows} == {"黑熊"}
    assert duplicate_rows == []
