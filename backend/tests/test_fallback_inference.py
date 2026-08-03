from pathlib import Path

from PIL import Image

from app.models.model_registry import MockClassifier, MockDetector, ModelRegistry, OpenAICompatibleVisionClassifier
from app.settings import Settings


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


def test_openai_compatible_vision_classifier_parses_json_content():
    classifier = OpenAICompatibleVisionClassifier(
        api_key="test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-vl-plus",
        timeout_seconds=1,
        target_labels=["豹猫", "未知动物"],
    )

    result = classifier._parse_content('{"species_label":"豹猫","confidence":82}')

    assert result["species_label"] == "豹猫"
    assert classifier._normalize_confidence(result["confidence"]) == 0.82


def test_bioclip_label_configuration_parses_chinese_and_latin_names():
    settings = Settings(
        bioclip_target_labels="豹猫|Prionailurus bengalensis,黑熊|Ursus thibetanus",
        bioclip_expand_catalog=False,
    )
    registry = ModelRegistry.__new__(ModelRegistry)
    registry.settings = settings

    assert registry._bioclip_target_labels() == [
        ("豹猫", "Prionailurus bengalensis"),
        ("黑熊", "Ursus thibetanus"),
    ]


def test_bioclip_catalog_expansion_includes_birds_and_unknown_exit():
    settings = Settings(bioclip_expand_catalog=True)
    registry = ModelRegistry.__new__(ModelRegistry)
    registry.settings = settings

    labels = registry._bioclip_target_labels()

    assert len(labels) >= 400
    assert ("白腹军舰鸟", "Fregata andrewsi") in labels
    assert ("未知鸟类", "Aves") in labels
    assert ("未知动物", "Animalia") in labels
