from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "scripts"))

from download_gbif_reference_images import is_excluded_by_occurrence_metadata  # noqa: E402


def test_render_training_coverage_report_marks_under_sampled_animals(tmp_path: Path):
    species_path = tmp_path / "species.json"
    species_path.write_text(
        json.dumps(
            [
                {
                    "cn_name": "Test animal",
                    "latin_name": "Animal testus",
                    "category": "animal",
                    "recognition_tier": "high_demo",
                    "protection_level": "protected",
                },
                {
                    "cn_name": "Camera",
                    "latin_name": "",
                    "category": "monitoring_object",
                    "recognition_tier": "operational",
                    "protection_level": "monitoring",
                },
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["file_path", "folder_name", "label", "split", "relative_path"])
        writer.writeheader()
        writer.writerow(
            {
                "file_path": str(tmp_path / "sample.jpg"),
                "folder_name": "Test animal",
                "label": "Test animal",
                "split": "train",
                "relative_path": "Test animal/sample.jpg",
            }
        )

    output_json = tmp_path / "coverage.json"
    output_md = tmp_path / "coverage.md"
    subprocess.run(
        [
            "python",
            "scripts\\render_training_coverage_report.py",
            "--species-file",
            str(species_path),
            "--manifest",
            str(manifest_path),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--minimum-total",
            "2",
            "--target-total",
            "3",
            "--target-val",
            "1",
        ],
        cwd=REPO_ROOT,
        check=True,
    )

    report = json.loads(output_json.read_text(encoding="utf-8"))
    statuses = {row["cn_name"]: row["status"] for row in report["species"]}
    assert statuses["Test animal"] == "need_more_samples"
    assert statuses["Camera"] == "knowledge_only"
    assert "Test animal" in output_md.read_text(encoding="utf-8")


def test_flag_gbif_license_issues_rejects_non_open_media_license(tmp_path: Path):
    species_dir = tmp_path / "gbif" / "Test animal"
    species_dir.mkdir(parents=True)
    metadata_path = species_dir / "metadata.csv"
    with metadata_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["filename", "license"])
        writer.writeheader()
        writer.writerow({"filename": "bad.jpg", "license": "Copyright by the creator."})

    subprocess.run(
        [
            "python",
            "scripts\\flag_gbif_license_issues.py",
            "--root",
            str(tmp_path / "gbif"),
        ],
        cwd=REPO_ROOT,
        check=True,
    )

    with (tmp_path / "gbif" / "review_status.csv").open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows == [
        {
            "species": "Test animal",
            "filename": "bad.jpg",
            "status": "reject",
            "reason": "license_not_allowed",
            "note": "Copyright by the creator.",
        }
    ]


def test_render_gbif_review_queue_lists_unreviewed_candidates(tmp_path: Path):
    species_dir = tmp_path / "gbif" / "Test animal"
    species_dir.mkdir(parents=True)
    (species_dir / "good.jpg").write_bytes(b"fake")
    with (species_dir / "metadata.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["filename", "license", "country", "source_url"])
        writer.writeheader()
        writer.writerow(
            {
                "filename": "good.jpg",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "country": "China",
                "source_url": "https://www.gbif.org/occurrence/1",
            }
        )

    output_csv = tmp_path / "queue.csv"
    output_md = tmp_path / "queue.md"
    subprocess.run(
        [
            "python",
            "scripts\\render_gbif_review_queue.py",
            "--root",
            str(tmp_path / "gbif"),
            "--output-csv",
            str(output_csv),
            "--output-md",
            str(output_md),
        ],
        cwd=REPO_ROOT,
        check=True,
    )

    with output_csv.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["status"] == "unreviewed"
    assert rows[0]["license_allowed"] == "yes"
    assert rows[0]["suggested_action"] == "manual review needed"
    assert "Test animal" in output_md.read_text(encoding="utf-8")


def test_gbif_downloader_prefilters_non_live_occurrence_metadata():
    specimen = {"basisOfRecord": "PRESERVED_SPECIMEN", "occurrenceRemarks": "adult animal"}
    assert is_excluded_by_occurrence_metadata(specimen, None, ["dead"]) is True

    roadkill = {"basisOfRecord": "HUMAN_OBSERVATION", "occurrenceRemarks": "roadkill beside trail"}
    assert is_excluded_by_occurrence_metadata(roadkill, None, ["roadkill"]) is True

    live_observation = {"basisOfRecord": "HUMAN_OBSERVATION", "occurrenceRemarks": "live animal in forest"}
    media = {"title": "clear side view"}
    assert is_excluded_by_occurrence_metadata(live_observation, media, ["roadkill", "zoo"]) is False


def test_apply_manual_review_batch_updates_review_status(tmp_path: Path):
    batch_path = tmp_path / "batch_01.csv"
    with batch_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["item", "species", "filename", "your_decision", "reason"])
        writer.writeheader()
        writer.writerow(
            {
                "item": "1",
                "species": "Test animal",
                "filename": "good.jpg",
                "your_decision": "approved",
                "reason": "clear live subject",
            }
        )

    review_path = tmp_path / "review_status.csv"
    subprocess.run(
        [
            "python",
            "scripts\\apply_manual_review_batch.py",
            "--batch",
            str(batch_path),
            "--review-status",
            str(review_path),
        ],
        cwd=REPO_ROOT,
        check=True,
    )

    with review_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["species"] == "Test animal"
    assert rows[0]["filename"] == "good.jpg"
    assert rows[0]["status"] == "approved"
    assert rows[0]["reason"] == "clear live subject"
