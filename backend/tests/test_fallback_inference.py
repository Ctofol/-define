from pathlib import Path

from PIL import Image

from app.models.model_registry import MockClassifier, MockDetector


def test_mock_detector_returns_center_box():
    image = Image.new("RGB", (640, 480), color=(80, 100, 70))
    detections = MockDetector().predict(image)

    assert len(detections) == 1
    assert detections[0].bbox.width > 0
    assert detections[0].detected_type == "animal"


def test_mock_classifier_returns_species_label():
    image = Image.new("RGB", (128, 128), color=(80, 100, 70))
    prediction = MockClassifier().classify(image)

    assert prediction.species_label
    assert 0 <= prediction.confidence <= 1
