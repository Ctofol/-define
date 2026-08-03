from pathlib import Path
import csv

from PIL import Image

from app.services.reference_retrieval_service import ReferenceRetrievalService


def test_reference_retrieval_returns_nearest_reference_candidate(tmp_path: Path):
    bear_dir = tmp_path / "黑熊"
    deer_dir = tmp_path / "水鹿"
    bear_dir.mkdir()
    deer_dir.mkdir()
    Image.new("RGB", (96, 96), color=(220, 30, 30)).save(bear_dir / "bear.jpg")
    Image.new("RGB", (96, 96), color=(30, 120, 220)).save(deer_dir / "deer.jpg")

    service = ReferenceRetrievalService(
        reference_root=tmp_path,
        manifest_path=tmp_path / "missing.csv",
        weak_manifest_path=tmp_path / "missing_weak.csv",
        backend="histogram",
    )
    candidates = service.retrieve(Image.new("RGB", (96, 96), color=(220, 30, 30)), limit=2)

    assert candidates
    assert candidates[0].label == "黑熊"
    assert candidates[0].source == "reference-retrieval"
    assert candidates[0].sample_url.endswith("/%E9%BB%91%E7%86%8A/bear.jpg")


def test_reference_retrieval_uses_canonical_label_for_asian_black_bear(tmp_path: Path):
    folder = tmp_path / "亚洲黑熊"
    folder.mkdir()
    Image.new("RGB", (96, 96), color=(220, 30, 30)).save(folder / "asian.jpg")

    service = ReferenceRetrievalService(
        reference_root=tmp_path,
        manifest_path=tmp_path / "missing.csv",
        weak_manifest_path=tmp_path / "missing_weak.csv",
        backend="histogram",
    )
    candidates = service.retrieve(Image.new("RGB", (96, 96), color=(220, 30, 30)), limit=1)

    assert candidates[0].label == "黑熊"


def test_reference_retrieval_uses_weak_manifest_as_capped_candidate(tmp_path: Path):
    weak_image = tmp_path / "weak_bird.jpg"
    Image.new("RGB", (96, 96), color=(80, 140, 60)).save(weak_image)
    primary_image = tmp_path / "primary_bear.jpg"
    Image.new("RGB", (96, 96), color=(220, 30, 30)).save(primary_image)
    weak_manifest = tmp_path / "weak_manifest.csv"
    write_manifest(weak_manifest, weak_image, "橙胸咬鹃")

    primary_manifest = tmp_path / "primary_manifest.csv"
    write_manifest(primary_manifest, primary_image, "黑熊")

    service = ReferenceRetrievalService(
        reference_root=tmp_path,
        manifest_path=primary_manifest,
        weak_manifest_path=weak_manifest,
        backend="histogram",
        weak_reference_max_confidence=0.46,
        weak_reference_confidence_boost=0.08,
    )

    candidates = service.retrieve(Image.new("RGB", (96, 96), color=(80, 140, 60)), limit=1)

    assert candidates[0].label == "橙胸咬鹃"
    assert candidates[0].source == "pdf-weak-reference"
    assert candidates[0].confidence == 0.46
    assert "1 weak" in service.status()["reference_retrieval_detail"]


def test_reference_retrieval_prefers_primary_reference_over_weak_reference(tmp_path: Path):
    primary_dir = tmp_path / "黑熊"
    primary_dir.mkdir()
    primary_image = primary_dir / "bear.jpg"
    weak_image = tmp_path / "weak_bear.jpg"
    Image.new("RGB", (96, 96), color=(220, 30, 30)).save(primary_image)
    Image.new("RGB", (96, 96), color=(220, 30, 30)).save(weak_image)
    primary_manifest = tmp_path / "primary_manifest.csv"
    write_manifest(primary_manifest, primary_image, "黑熊")
    weak_manifest = tmp_path / "weak_manifest.csv"
    write_manifest(weak_manifest, weak_image, "黑熊")

    service = ReferenceRetrievalService(
        reference_root=tmp_path,
        manifest_path=primary_manifest,
        weak_manifest_path=weak_manifest,
        backend="histogram",
        weak_reference_max_confidence=0.46,
        weak_reference_confidence_boost=0.08,
    )

    candidates = service.retrieve(Image.new("RGB", (96, 96), color=(220, 30, 30)), limit=1)

    assert candidates[0].label == "黑熊"
    assert candidates[0].source == "reference-retrieval"
    assert candidates[0].sample_url.endswith("/bear.jpg")


def test_default_manifest_prefers_latest_cleaned_training_manifest(tmp_path: Path):
    storage_dir = tmp_path / "storage"
    training_dir = storage_dir / "training"
    training_dir.mkdir(parents=True)
    older = training_dir / "species_manifest_v15_reviewed_supplement.csv"
    round2 = training_dir / "species_manifest_v17_cleaned_confusion_round2.csv"
    round3 = training_dir / "species_manifest_v18_round3_cleaned.csv"
    round4 = training_dir / "species_manifest_v19_round4_cleaned.csv"
    latest = training_dir / "species_manifest_v20_round5_cleaned.csv"
    older.write_text("file_path,label\n", encoding="utf-8")
    round2.write_text("file_path,label\n", encoding="utf-8")
    round3.write_text("file_path,label\n", encoding="utf-8")
    round4.write_text("file_path,label\n", encoding="utf-8")
    latest.write_text("file_path,label\n", encoding="utf-8")

    service = ReferenceRetrievalService(reference_root=tmp_path)

    assert service._default_manifest_path(storage_dir) == latest


def write_manifest(path: Path, image_path: Path, label: str) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["file_path", "label"])
        writer.writeheader()
        writer.writerow({"file_path": str(image_path), "label": label})
