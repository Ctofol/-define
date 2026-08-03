from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.models.model_registry import MockClassifier, MockDetector
from app.schemas import SpeciesCandidate
from app.services.inference_service import InferenceService
from app.services.result_store import ResultStore
from app.settings import Settings


class LowConfidenceClassifier:
    name = "transformers-image-classification"

    def classify(self, image: Image.Image):
        from app.models.model_registry import ClassifierPrediction

        return ClassifierPrediction(species_label="黑熊", confidence=0.25)


class HighConfidenceMacaqueClassifier:
    name = "transformers-image-classification"

    def classify(self, image: Image.Image):
        from app.models.model_registry import ClassifierPrediction

        return ClassifierPrediction(species_label="猕猴", confidence=0.84)


class MidConfidenceBearClassifier:
    name = "transformers-image-classification"

    def classify(self, image: Image.Image):
        from app.models.model_registry import ClassifierPrediction

        return ClassifierPrediction(species_label="榛戠唺", confidence=0.62)


class UnknownBirdClassifier:
    name = "bioclip-2-zero-shot"

    def classify(self, image: Image.Image):
        from app.models.model_registry import ClassifierPrediction

        return ClassifierPrediction(species_label="未知鸟类", confidence=0.61)


class PheasantClassifier:
    name = "bioclip-2-zero-shot"

    def classify(self, image: Image.Image):
        from app.models.model_registry import ClassifierPrediction

        return ClassifierPrediction(species_label="白鹇", confidence=0.62)


class FakeRegistry:
    detector = MockDetector()
    classifier = MockClassifier()

    def status(self) -> dict[str, str]:
        return {"detector": self.detector.name, "classifier": self.classifier.name}


class OverrideRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return [SpeciesCandidate(label="野猪", confidence=0.45, source="reference-retrieval", evidence="mock")]


class CivetRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return [SpeciesCandidate(label="大灵猫", confidence=0.7, source="reference-retrieval", evidence="mock")]


class FakeSpeciesCatalog:
    def match(self, label: str):
        groups = {"白鹇": "鸟类", "大灵猫": "兽类"}
        group = groups.get(label)
        if group is None:
            return None
        return SimpleNamespace(taxon_group=group, recognition_tier="candidate")

    def enrich_candidates(self, candidates):
        return candidates

    def review_reasons(self, candidates, evidence_state, review_status, top_gap):
        return ["mock_review"]

    def status(self):
        return {"species_catalog": "fake"}


class AmbiguousOverrideRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return [
            SpeciesCandidate(label="candidate-a", confidence=0.45, source="reference-retrieval", evidence="mock"),
            SpeciesCandidate(label="candidate-b", confidence=0.42, source="reference-retrieval", evidence="mock"),
        ]


class WeakPdfOverrideRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return [SpeciesCandidate(label="短尾猴", confidence=0.46, source="pdf-weak-reference", evidence="mock")]


class StrongWeakPdfRefinementRetrieval:
    def retrieve(self, image: Image.Image, limit: int = 5):
        return [
            SpeciesCandidate(label="短尾猴", confidence=0.46, source="pdf-weak-reference", evidence="mock"),
            SpeciesCandidate(label="猕猴", confidence=0.36, source="reference-retrieval", evidence="mock"),
        ]


def test_low_confidence_classifier_can_display_stronger_retrieval_candidate(tmp_path: Path):
    settings = Settings(
        storage_dir=tmp_path,
        species_candidate_threshold=0.5,
        retrieval_display_override_threshold=0.4,
    )
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = LowConfidenceClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), OverrideRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == "野猪"
    assert detection.classification_confidence == 0.25
    assert detection.retrieval_confidence == 0.45
    assert detection.top_candidates[0].label == "野猪"
    assert detection.review_status == "low_confidence"

def test_mid_confidence_classifier_can_be_refined_by_reliable_retrieval(tmp_path: Path):
    settings = Settings(
        storage_dir=tmp_path,
        retrieval_display_override_classifier_max_confidence=0.65,
        retrieval_display_override_threshold=0.35,
    )
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = MidConfidenceBearClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), OverrideRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == OverrideRetrieval().retrieve(Image.new("RGB", (1, 1)))[0].label
    assert detection.classification_confidence == 0.62
    assert detection.retrieval_confidence == 0.45


def test_ambiguous_retrieval_does_not_override_display_label(tmp_path: Path):
    settings = Settings(
        storage_dir=tmp_path,
        retrieval_display_override_classifier_max_confidence=0.65,
        retrieval_display_override_threshold=0.35,
        retrieval_display_override_margin=0.08,
    )
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = MidConfidenceBearClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), AmbiguousOverrideRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == MidConfidenceBearClassifier().classify(Image.new("RGB", (1, 1))).species_label
    assert detection.retrieval_confidence == 0.45
    assert detection.review_status == "needs_review"


def test_low_confidence_classifier_can_display_pdf_weak_reference_but_requires_review(tmp_path: Path):
    settings = Settings(
        storage_dir=tmp_path,
        species_candidate_threshold=0.45,
        retrieval_display_override_threshold=0.4,
    )
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = LowConfidenceClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), WeakPdfOverrideRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == "短尾猴"
    assert detection.retrieval_confidence == 0.46
    assert detection.top_candidates[0].source == "pdf-weak-reference"
    assert detection.review_status == "needs_review"


def test_pdf_weak_reference_can_refine_high_confidence_closed_set_classifier(tmp_path: Path):
    settings = Settings(
        storage_dir=tmp_path,
        species_candidate_threshold=0.45,
        retrieval_display_override_threshold=0.4,
        weak_reference_override_margin=0.06,
    )
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = HighConfidenceMacaqueClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), StrongWeakPdfRefinementRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == "短尾猴"
    assert detection.classification_confidence == 0.84
    assert detection.retrieval_confidence == 0.46
    assert detection.review_status == "needs_review"


def test_generalized_bioclip_label_is_not_overridden_by_specific_reference(tmp_path: Path):
    settings = Settings(
        storage_dir=tmp_path,
        retrieval_display_override_classifier_max_confidence=0.65,
        retrieval_display_override_threshold=0.35,
    )
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = UnknownBirdClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), CivetRetrieval())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == "未知鸟类"
    assert detection.retrieval_confidence == 0.7
    assert detection.review_status == "needs_review"


def test_cross_taxon_reference_does_not_override_bioclip_label(tmp_path: Path):
    settings = Settings(
        storage_dir=tmp_path,
        retrieval_display_override_classifier_max_confidence=0.65,
        retrieval_display_override_threshold=0.35,
    )
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    registry = FakeRegistry()
    registry.classifier = PheasantClassifier()
    service = InferenceService(settings, registry, ResultStore(tmp_path / "results"), CivetRetrieval(), FakeSpeciesCatalog())

    detection = service._analyze_frame(
        media_id="sample",
        image=Image.new("RGB", (640, 480), color=(80, 100, 70)),
        frame_time=0.0,
        confidence_threshold=0.1,
        include_low_confidence=False,
    )[0]

    assert detection.species_label == "白鹇"
    assert detection.retrieval_confidence == 0.7
    assert detection.review_status == "needs_review"
