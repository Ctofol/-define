from pathlib import Path

from PIL import Image

from app.models.model_registry import MockClassifier, MockDetector
from app.services.inference_service import InferenceService
from app.schemas import SpeciesCandidate, SpeciesEntry
from app.services.result_store import ResultStore
from app.settings import Settings


class FixedClassifier:
    name = "transformers-image-classification"

    def classify(self, image: Image.Image):
        from app.models.model_registry import ClassifierPrediction

        return ClassifierPrediction(species_label="榛戠唺", confidence=0.95)


class FakeRegistry:
    detector = MockDetector()
    classifier = MockClassifier()

    def status(self) -> dict[str, str]:
        return {"detector": self.detector.name, "classifier": self.classifier.name}


class FakeRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return [SpeciesCandidate(label="榛戠唺", confidence=0.91, source="reference-retrieval", evidence="mock")]


class ConflictingRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return [SpeciesCandidate(label="姘撮箍", confidence=0.91, source="reference-retrieval", evidence="mock")]


class MissingRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return []


class StrictReviewCatalog:
    def match(self, label: str):
        return SpeciesEntry(
            species_id="asiatic_black_bear",
            cn_name="黑熊",
            latin_name="Ursus thibetanus",
            category="animal",
            taxon_group="哺乳动物",
            protection_level="国家二级保护野生动物",
            source_scope="test",
            recognition_tier="candidate",
            features=[],
            habitat="",
            monitoring_value="",
            review_tips="",
        )

    def enrich_candidates(self, candidates: list[SpeciesCandidate]) -> list[SpeciesCandidate]:
        return candidates

    def review_reasons(self, candidates: list[SpeciesCandidate], evidence_state: str, review_status: str, top_gap: float) -> list[str]:
        return ["candidate_needs_confirmation"] if review_status == "needs_review" else []

    def status(self) -> dict[str, str]:
        return {"species_catalog": "test"}


def test_detection_result_splits_detection_and_classification_confidence(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    service = InferenceService(settings, FakeRegistry(), ResultStore(tmp_path / "results"), FakeRetrieval())

    detections = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )

    assert len(detections) == 1
    assert detections[0].detection_confidence == 0.88
    assert detections[0].classification_confidence == 1.0
    assert detections[0].retrieval_confidence == 0.91
    assert detections[0].top_candidates[0].label == "榛戠唺"
    assert detections[0].top_candidates[0].confidence == 0.91
    assert detections[0].review_status == "needs_review"


def test_aligned_high_confidence_result_is_ready_with_demo_thresholds(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path, species_ready_threshold=0.7, species_candidate_threshold=0.45)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = FixedClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), FakeRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == FixedClassifier().classify(Image.new("RGB", (1, 1))).species_label
    assert detection.review_status == "ready"
    assert service._annotation_label(detection) == f"{detection.species_label} 88%"


def test_fallback_classifier_uses_retrieval_candidate_instead_of_file_name(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    service = InferenceService(settings, FakeRegistry(), ResultStore(tmp_path / "results"), FakeRetrieval())

    detections = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
        source_name="black-bear-demo.jpg",
    )

    assert len(detections) == 1
    assert detections[0].species_label == "榛戠唺"
    assert detections[0].top_candidates[0].label == "榛戠唺"
    assert detections[0].review_status == "needs_review"


def test_annotation_label_uses_review_wording_for_unconfirmed_results(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    service = InferenceService(settings, FakeRegistry(), ResultStore(tmp_path / "results"), FakeRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.review_status == "needs_review"
    assert service._annotation_label(detection).endswith("88%")


def test_conflicting_reference_retrieval_keeps_result_in_review(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path, species_ready_threshold=0.85, species_candidate_threshold=0.5)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = FixedClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), ConflictingRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.classification_confidence == 0.95
    assert detection.retrieval_confidence == 0.91
    assert detection.top_candidates[0].label == "榛戠唺"
    assert detection.review_status == "needs_review"


def test_high_confidence_result_without_reference_support_stays_in_review(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path, species_ready_threshold=0.7, species_candidate_threshold=0.45)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = FixedClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), MissingRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.classification_confidence == 0.95
    assert detection.retrieval_confidence == 0.0
    assert detection.review_status == "needs_review"


def test_not_ready_species_stays_in_review_even_with_high_confidence(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path, species_ready_threshold=0.7, species_candidate_threshold=0.45)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = FixedClassifier()
    service = InferenceService(
        settings,
        registry,
        ResultStore(tmp_path / "results"),
        FakeRetrieval(),
        StrictReviewCatalog(),
    )

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.classification_confidence == 0.95
    assert detection.retrieval_confidence == 0.91
    assert detection.review_status == "needs_review"
