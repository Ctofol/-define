from __future__ import annotations

import base64
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from app.schemas import BoundingBox
from app.settings import Settings


@dataclass
class DetectorPrediction:
    bbox: BoundingBox
    detected_type: str
    confidence: float


@dataclass
class ClassifierPrediction:
    species_label: str
    confidence: float


@dataclass
class BackendState:
    requested: str
    active: str
    ready: bool
    detail: str


class Detector(Protocol):
    name: str

    def predict(self, image: Image.Image) -> list[DetectorPrediction]:
        ...


class Classifier(Protocol):
    name: str

    def classify(self, image: Image.Image) -> ClassifierPrediction:
        ...


class MockDetector:
    name = "fallback-detector"

    def predict(self, image: Image.Image) -> list[DetectorPrediction]:
        width, height = image.size
        if width < 32 or height < 32:
            return []

        bbox_width = max(32, int(width * 0.84))
        bbox_height = max(32, int(height * 0.82))
        x = max(0, int(width * 0.08))
        y = max(0, int(height * 0.09))
        return [
            DetectorPrediction(
                bbox=BoundingBox(x=x, y=y, width=bbox_width, height=bbox_height),
                detected_type="animal",
                confidence=0.88,
            )
        ]


class MockClassifier:
    name = "fallback-classifier"

    def classify(self, image: Image.Image) -> ClassifierPrediction:
        return ClassifierPrediction(species_label="未分类动物", confidence=1.0)


class OpenAICompatibleVisionClassifier:
    name = "openai-compatible-vision-classification"

    def __init__(self, api_key: str, base_url: str, model: str, timeout_seconds: float, target_labels: list[str]):
        if not api_key:
            raise ValueError("multimodal API key is not configured")
        self.api_key = api_key
        self.endpoint = self._chat_completions_endpoint(base_url)
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.target_labels = target_labels or ["未知动物"]

    def classify(self, image: Image.Image) -> ClassifierPrediction:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是广西野生动物图片识别助手。只返回合法 JSON，不要 markdown。"
                        "格式：{\"species_label\":\"候选标签之一\",\"confidence\":0.0}。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "候选标签："
                                + ", ".join(self.target_labels)
                                + "。请识别图片中的主要动物，只能从候选标签中选一个；"
                                + "如果不是这些动物才选未知动物。"
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": self._image_data_url(image)}},
                    ],
                },
            ],
            "temperature": 0,
            "max_tokens": 120,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"multimodal classifier request failed: HTTP {exc.code} {detail[:300]}") from exc
        except URLError as exc:
            raise RuntimeError(f"multimodal classifier request failed: {exc}") from exc

        content = data["choices"][0]["message"]["content"]
        result = self._parse_content(content)
        label = str(result.get("species_label") or "未知动物").strip() or "未知动物"
        if label not in self.target_labels:
            label = "未知动物"
        confidence = self._normalize_confidence(result.get("confidence", 0.0))
        return ClassifierPrediction(species_label=label, confidence=confidence)

    def _chat_completions_endpoint(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"

    def _image_data_url(self, image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=88)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def _parse_content(self, content: str | dict) -> dict:
        if isinstance(content, dict):
            return content
        text = str(content).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise

    def _normalize_confidence(self, raw: object) -> float:
        try:
            confidence = float(raw)
        except (TypeError, ValueError):
            return 0.0
        if confidence > 1:
            confidence = confidence / 100
        return max(0.0, min(1.0, round(confidence, 3)))


class TransformersClassifier:
    name = "transformers-image-classification"

    def __init__(self, model_path: Path):
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        if not model_path.exists():
            raise FileNotFoundError(f"classifier model path does not exist: {model_path}")
        self.processor = AutoImageProcessor.from_pretrained(str(model_path), local_files_only=True)
        self.model = AutoModelForImageClassification.from_pretrained(str(model_path), local_files_only=True)
        self.model.eval()

    def classify(self, image: Image.Image) -> ClassifierPrediction:
        import torch

        inputs = self.processor(images=image.convert("RGB"), return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = outputs.logits.softmax(dim=-1)[0]
            confidence, label_id = torch.max(probabilities, dim=0)
        label = self.model.config.id2label[int(label_id)]
        return ClassifierPrediction(species_label=str(label), confidence=float(confidence))


class BioCLIPClassifier:
    """Zero-shot species classifier backed by the BioCLIP 2 vision-language model."""

    name = "bioclip-2-zero-shot"

    def __init__(
        self,
        model_name: str,
        device: str,
        min_confidence: float,
        min_margin: float,
        target_labels: list[tuple[str, str]],
        hf_endpoint: str,
    ):
        if not target_labels:
            raise ValueError("BioCLIP target labels are not configured")

        if hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", hf_endpoint.rstrip("/"))

        import open_clip
        import torch

        self.device = device if device.startswith("cuda") and torch.cuda.is_available() else "cpu"
        self.min_confidence = min_confidence
        self.min_margin = min_margin
        self.target_labels = target_labels
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name)
        self.model.to(self.device)
        self.model.eval()
        tokenizer = open_clip.get_tokenizer(model_name)
        prompts = [f"a photo of a {latin}" for _, latin in target_labels]
        with torch.no_grad():
            text_features = self.model.encode_text(tokenizer(prompts).to(self.device))
            self.text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    def classify(self, image: Image.Image) -> ClassifierPrediction:
        import torch

        image_tensor = self.preprocess(image.convert("RGB")).unsqueeze(0).to(self.device)
        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            logits = self.model.logit_scale.exp() * image_features @ self.text_features.T
            probabilities = logits.softmax(dim=-1)[0]
            top_values, top_indices = torch.topk(probabilities, k=min(2, len(self.target_labels)))

        normalized_confidence = float(top_values[0])
        label_index = int(top_indices[0])
        margin = normalized_confidence - (float(top_values[1]) if len(top_values) > 1 else 0.0)
        selected_label = self.target_labels[label_index][0]
        if normalized_confidence < self.min_confidence or margin < self.min_margin or selected_label.startswith("未知"):
            return ClassifierPrediction(species_label="未知动物", confidence=normalized_confidence)
        return ClassifierPrediction(selected_label, normalized_confidence)


class AmazonRainforestClassifier:
    name = "pytorch-wildlife-amazon-rainforest"

    label_map = {
        "Dasyprocta": "刺豚鼠属",
        "Bos": "牛属",
        "Pecari": "西猯属",
        "Mazama": "短角鹿属",
        "Cuniculus": "低地帕卡",
        "Leptotila": "鸠类",
        "Human": "人",
        "Aramides": "林秧鸡属",
        "Tinamus": "䳍属",
        "Eira": "泰拉貂",
        "Crax": "凤冠雉属",
        "Procyon": "浣熊属",
        "Capra": "山羊属",
        "Dasypus": "犰狳属",
        "Sciurus": "松鼠属",
        "Crypturellus": "隐䳍属",
        "Tamandua": "小食蚁兽属",
        "Proechimys": "刺鼠属",
        "Leopardus": "虎猫属",
        "Equus": "马属",
        "Columbina": "地鸠属",
        "Nyctidromus": "夜鹰属",
        "Ortalis": "小冠雉属",
        "Emballonura": "鞘尾蝠属",
        "Odontophorus": "林鹑属",
        "Geotrygon": "鹑鸠属",
        "Metachirus": "褐四眼负鼠",
        "Catharus": "夜鸫属",
        "Cerdocyon": "食蟹狐",
        "Momotus": "翠鴗属",
        "Tapirus": "貘属",
        "Canis": "犬属",
        "Furnarius": "灶鸟属",
        "Didelphis": "负鼠属",
        "Sylvilagus": "棉尾兔属",
        "Unknown": "未知动物",
    }

    def __init__(self, weights_path: Path, device: str, min_confidence: float):
        if weights_path.is_dir():
            weights_path = weights_path / "amazon_v2.ckpt"
        if not weights_path.exists():
            raise FileNotFoundError(f"species classifier weights path does not exist: {weights_path}")

        from PytorchWildlife.models import classification as pw_classification

        self.model = pw_classification.AI4GAmazonRainforest(weights=str(weights_path), device=device, pretrained=False)
        self.min_confidence = min_confidence

    def classify(self, image: Image.Image) -> ClassifierPrediction:
        import numpy as np

        result = self.model.single_image_classification(np.array(image.convert("RGB")), img_id="crop")
        latin_label = str(result.get("prediction", "Unknown"))
        confidence = float(result.get("confidence", 0.0))
        if confidence < self.min_confidence or latin_label == "Unknown":
            chinese_label = self.label_map.get(latin_label, latin_label)
            if latin_label == "Unknown":
                return ClassifierPrediction(species_label="未知动物", confidence=confidence)
            return ClassifierPrediction(species_label=f"未知动物（候选：{chinese_label}）", confidence=confidence)
        chinese_label = self.label_map.get(latin_label, latin_label)
        return ClassifierPrediction(species_label=f"{chinese_label} ({latin_label})", confidence=confidence)


class MegaDetectorAdapter:
    name = "pytorch-wildlife-megadetector"

    def __init__(self, model_path: Path, device: str):
        from PytorchWildlife.models import detection as pw_detection

        if not model_path.exists():
            raise FileNotFoundError(f"detector weights path does not exist: {model_path}")
        self.model = pw_detection.MegaDetectorV6(
            weights=str(model_path),
            device=device,
            pretrained=False,
            version="MDV6-yolov9-c",
        )

    def predict(self, image: Image.Image) -> list[DetectorPrediction]:
        import numpy as np

        results = self.model.single_image_detection(np.array(image.convert("RGB")))
        raw_detections = results.get("detections", [])
        detections: list[DetectorPrediction] = []

        if hasattr(raw_detections, "xyxy"):
            xyxy_values = raw_detections.xyxy
            confidences = getattr(raw_detections, "confidence", None)
            class_ids = getattr(raw_detections, "class_id", None)
            confidences = confidences if confidences is not None else []
            class_ids = class_ids if class_ids is not None else []
            for index, xyxy in enumerate(xyxy_values):
                x1, y1, x2, y2 = [int(v) for v in xyxy[:4]]
                class_id = int(class_ids[index]) if index < len(class_ids) else 0
                category = getattr(self.model, "CLASS_NAMES", {}).get(class_id, "animal")
                conf = float(confidences[index]) if index < len(confidences) else 0.0
                detections.append(
                    DetectorPrediction(
                        bbox=BoundingBox(x=x1, y=y1, width=max(1, x2 - x1), height=max(1, y2 - y1)),
                        detected_type=category,
                        confidence=conf,
                    )
                )
            return self._merge_adjacent_boxes(detections, image.size)

        for item in raw_detections:
            if isinstance(item, tuple):
                continue
            conf = float(item.get("conf", item.get("confidence", 0)))
            xyxy = item.get("bbox", item.get("xyxy"))
            if not xyxy or len(xyxy) < 4:
                continue
            x1, y1, x2, y2 = [int(v) for v in xyxy[:4]]
            category = str(item.get("category", "animal"))
            detections.append(
                DetectorPrediction(
                    bbox=BoundingBox(x=x1, y=y1, width=max(1, x2 - x1), height=max(1, y2 - y1)),
                    detected_type=category,
                    confidence=conf,
                )
            )
        return self._merge_adjacent_boxes(detections, image.size)

    def _merge_adjacent_boxes(self, detections: list[DetectorPrediction], image_size: tuple[int, int]) -> list[DetectorPrediction]:
        if len(detections) < 2:
            return detections

        image_width, image_height = image_size
        merge_gap_x = max(12, int(image_width * 0.08))
        merge_gap_y = max(12, int(image_height * 0.08))
        merged = detections[:]
        changed = True

        while changed:
            changed = False
            next_round: list[DetectorPrediction] = []
            used: set[int] = set()

            for left_index, left in enumerate(merged):
                if left_index in used:
                    continue

                current = left
                for right_index in range(left_index + 1, len(merged)):
                    if right_index in used:
                        continue
                    right = merged[right_index]
                    if current.detected_type != right.detected_type:
                        continue
                    if self._should_merge(current.bbox, right.bbox, merge_gap_x, merge_gap_y):
                        current = self._merge_pair(current, right)
                        used.add(right_index)
                        changed = True

                used.add(left_index)
                next_round.append(current)

            merged = next_round

        return merged

    def _should_merge(self, left: BoundingBox, right: BoundingBox, gap_x: int, gap_y: int) -> bool:
        left_x2 = left.x + left.width
        left_y2 = left.y + left.height
        right_x2 = right.x + right.width
        right_y2 = right.y + right.height

        horizontal_overlap = max(0, min(left_x2, right_x2) - max(left.x, right.x))
        vertical_overlap = max(0, min(left_y2, right_y2) - max(left.y, right.y))
        horizontal_gap = max(0, max(left.x, right.x) - min(left_x2, right_x2))
        vertical_gap = max(0, max(left.y, right.y) - min(left_y2, right_y2))

        min_width = max(1, min(left.width, right.width))
        min_height = max(1, min(left.height, right.height))
        strong_vertical_alignment = vertical_overlap / min_height >= 0.55
        strong_horizontal_alignment = horizontal_overlap / min_width >= 0.55

        return (
            strong_vertical_alignment and horizontal_gap <= gap_x
        ) or (
            strong_horizontal_alignment and vertical_gap <= gap_y
        )

    def _merge_pair(self, left: DetectorPrediction, right: DetectorPrediction) -> DetectorPrediction:
        x1 = min(left.bbox.x, right.bbox.x)
        y1 = min(left.bbox.y, right.bbox.y)
        x2 = max(left.bbox.x + left.bbox.width, right.bbox.x + right.bbox.width)
        y2 = max(left.bbox.y + left.bbox.height, right.bbox.y + right.bbox.height)
        return DetectorPrediction(
            bbox=BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1),
            detected_type=left.detected_type,
            confidence=max(left.confidence, right.confidence),
        )


class DirectUltralyticsDetector:
    name = "ultralytics-megadetector"

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"detector weights path does not exist: {model_path}")

        from ultralytics import YOLO

        self.model = YOLO(str(model_path))

    def predict(self, image: Image.Image) -> list[DetectorPrediction]:
        import numpy as np

        results = self.model.predict(source=np.array(image.convert("RGB")), verbose=False)
        if not results:
            return []

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        names = getattr(result, "names", {}) or {}
        xyxy_values = getattr(boxes, "xyxy", [])
        conf_values = getattr(boxes, "conf", [])
        cls_values = getattr(boxes, "cls", [])
        detections: list[DetectorPrediction] = []

        for index, xyxy in enumerate(xyxy_values):
            x1, y1, x2, y2 = [int(v) for v in xyxy.tolist()[:4]]
            confidence = float(conf_values[index]) if index < len(conf_values) else 0.0
            class_id = int(cls_values[index]) if index < len(cls_values) else 0
            detected_type = str(names.get(class_id, "animal"))
            detections.append(
                DetectorPrediction(
                    bbox=BoundingBox(x=x1, y=y1, width=max(1, x2 - x1), height=max(1, y2 - y1)),
                    detected_type=detected_type,
                    confidence=confidence,
                )
            )

        return detections


class ModelRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        os.environ.setdefault("YOLO_CONFIG_DIR", str(settings.ultralytics_dir))
        os.environ.setdefault("YOLO_AUTOINSTALL", "false")
        self.detector_state = BackendState(settings.detector_backend, "unknown", False, "not loaded")
        self.classifier_state = BackendState(settings.classifier_backend, "unknown", False, "not loaded")
        self.detector = self._load_detector()
        self.classifier = self._load_classifier()

    def _load_detector(self) -> Detector:
        if self.settings.detector_backend in {"auto", "megadetector"}:
            model_path = self.settings.detector_model_path or self.settings.models_dir / "megadetector" / "md_v6.pt"
            try:
                detector = MegaDetectorAdapter(model_path, self.settings.inference_device)
                self.detector_state = BackendState(self.settings.detector_backend, detector.name, True, f"loaded from {model_path}")
                return detector
            except Exception as exc:
                first_error = f"{exc.__class__.__name__}: {exc}"
                try:
                    detector = DirectUltralyticsDetector(model_path)
                    self.detector_state = BackendState(
                        self.settings.detector_backend,
                        detector.name,
                        True,
                        f"loaded from {model_path} via ultralytics after PytorchWildlife failed: {first_error}",
                    )
                    return detector
                except Exception as fallback_exc:
                    fallback_error = f"{fallback_exc.__class__.__name__}: {fallback_exc}"
                if self.settings.detector_backend == "megadetector":
                    raise RuntimeError(f"MegaDetector failed: {first_error}; ultralytics fallback failed: {fallback_error}") from fallback_exc
                self.detector_state = BackendState(
                    self.settings.detector_backend,
                    MockDetector.name,
                    False,
                    f"fallback: PytorchWildlife {first_error}; ultralytics {fallback_error}",
                )
                return MockDetector()
        self.detector_state = BackendState(self.settings.detector_backend, MockDetector.name, True, "forced fallback backend")
        return MockDetector()

    def _load_classifier(self) -> Classifier:
        if self.settings.classifier_backend in {"bioclip", "bioclip2", "bio"}:
            try:
                classifier = BioCLIPClassifier(
                    self.settings.bioclip_model_name,
                    self.settings.inference_device,
                    self.settings.bioclip_min_confidence,
                    self.settings.bioclip_min_margin,
                    self._bioclip_target_labels(),
                    self.settings.bioclip_hf_endpoint,
                )
                self.classifier_state = BackendState(
                    self.settings.classifier_backend,
                    classifier.name,
                    True,
                    f"loaded model {self.settings.bioclip_model_name} with {len(classifier.target_labels)} labels",
                )
                return classifier
            except Exception as exc:
                raise RuntimeError(f"BioCLIP classifier failed: {exc}") from exc

        if self.settings.classifier_backend in {"multimodal", "qwen", "vision"}:
            try:
                classifier = OpenAICompatibleVisionClassifier(
                    self.settings.multimodal_api_key,
                    self.settings.multimodal_base_url,
                    self.settings.multimodal_model,
                    self.settings.multimodal_timeout_seconds,
                    self._multimodal_target_labels(),
                )
                self.classifier_state = BackendState(
                    self.settings.classifier_backend,
                    classifier.name,
                    True,
                    f"loaded model {self.settings.multimodal_model} from {self.settings.multimodal_base_url}",
                )
                return classifier
            except Exception as exc:
                raise RuntimeError(f"multimodal classifier failed: {exc}") from exc

        if self.settings.classifier_backend in {"auto", "amazon"}:
            try:
                model_path = self.settings.classifier_model_path or self.settings.models_dir / "species-classifier" / "amazon_v2.ckpt"
                classifier = AmazonRainforestClassifier(
                    model_path,
                    self.settings.inference_device,
                    self.settings.species_confidence_threshold,
                )
                self.classifier_state = BackendState(self.settings.classifier_backend, classifier.name, True, f"loaded from {model_path}")
                return classifier
            except Exception as exc:
                if self.settings.classifier_backend == "amazon":
                    raise
                self.classifier_state = BackendState(
                    self.settings.classifier_backend,
                    MockClassifier.name,
                    False,
                    f"fallback: {exc.__class__.__name__}: {exc}",
                )

        if self.settings.classifier_backend in {"auto", "transformers"}:
            try:
                model_path = self.settings.classifier_model_path or self.settings.models_dir / "species-classifier"
                classifier = TransformersClassifier(model_path)
                self.classifier_state = BackendState(self.settings.classifier_backend, classifier.name, True, f"loaded from {model_path}")
                return classifier
            except Exception as exc:
                if self.settings.classifier_backend == "transformers":
                    raise
                self.classifier_state = BackendState(
                    self.settings.classifier_backend,
                    MockClassifier.name,
                    False,
                    f"fallback: {exc.__class__.__name__}: {exc}",
                )
                return MockClassifier()
        self.classifier_state = BackendState(self.settings.classifier_backend, MockClassifier.name, True, "forced fallback backend")
        return MockClassifier()

    def _multimodal_target_labels(self) -> list[str]:
        return [label.strip() for label in self.settings.multimodal_target_labels.split(",") if label.strip()]

    def _bioclip_target_labels(self) -> list[tuple[str, str]]:
        labels: list[tuple[str, str]] = []
        for raw_label in self.settings.bioclip_target_labels.split(","):
            chinese, separator, latin = raw_label.strip().partition("|")
            if chinese and separator and latin:
                labels.append((chinese.strip(), latin.strip()))

        if self.settings.bioclip_expand_catalog:
            data_dir = Path(__file__).resolve().parents[1] / "data"
            for catalog_name in ("species_knowledge.json", "pdf_species_catalog.json"):
                catalog_path = data_dir / catalog_name
                if not catalog_path.exists():
                    continue
                try:
                    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                entries = payload.get("species", []) if isinstance(payload, dict) else payload
                for entry in entries if isinstance(entries, list) else []:
                    if not isinstance(entry, dict) or entry.get("category") == "plant":
                        continue
                    chinese = str(entry.get("cn_name") or "").strip()
                    latin = str(entry.get("latin_name") or "").strip()
                    if chinese and latin:
                        labels.append((chinese, latin))

            labels.extend(
                [
                    ("未知鸟类", "Aves"),
                    ("未知哺乳动物", "Mammalia"),
                    ("未知爬行动物", "Reptilia"),
                    ("未知两栖动物", "Amphibia"),
                    ("未知动物", "Animalia"),
                ]
            )

        deduplicated: list[tuple[str, str]] = []
        seen_latin: set[str] = set()
        for chinese, latin in labels:
            latin_key = " ".join(latin.lower().split())
            if latin_key in seen_latin:
                continue
            seen_latin.add(latin_key)
            deduplicated.append((chinese, latin))
        return deduplicated

    def status(self) -> dict[str, str]:
        return {
            "detector": self.detector.name,
            "classifier": self.classifier.name,
            "detector_requested": self.detector_state.requested,
            "detector_detail": self.detector_state.detail,
            "classifier_requested": self.classifier_state.requested,
            "classifier_detail": self.classifier_state.detail,
            "device": self.settings.inference_device,
        }
