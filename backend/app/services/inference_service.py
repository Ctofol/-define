from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageDraw, ImageOps

from app.models.model_registry import ClassifierPrediction, DetectorPrediction, ModelRegistry
from app.schemas import AnalysisResponse, BoundingBox, DetectionResult, SpeciesCandidate
from app.services.reference_retrieval_service import ReferenceRetrievalService
from app.services.result_store import ResultStore
from app.services.species_catalog_service import SpeciesCatalogService
from app.settings import Settings


DIRECT_READY_TIERS = {"high_demo", "knowledge_first"}
FULL_FRAME_FALLBACK_CLASSIFICATION_THRESHOLD = 0.55
FULL_FRAME_FALLBACK_DETECTION_CONFIDENCE = 0.72
CROP_CONTEXT_PADDING_RATIO = 0.14
STRICT_REVIEW_LABELS = {"中华斑羚", "野猪", "黑熊", "大灵猫", "豹猫", "白鹇", "环颈雉"}
STRICT_REVIEW_LABEL_KEYS = {"".join(ch.lower() for ch in label if ch.isalnum()) for label in STRICT_REVIEW_LABELS}


class InferenceService:
    def __init__(
        self,
        settings: Settings,
        registry: ModelRegistry,
        store: ResultStore,
        retrieval: ReferenceRetrievalService | None = None,
        species_catalog: SpeciesCatalogService | None = None,
    ):
        self.settings = settings
        self.registry = registry
        self.store = store
        self.retrieval = retrieval
        self.species_catalog = species_catalog

    async def analyze_image(self, file: UploadFile, confidence_threshold: float, include_low_confidence: bool) -> AnalysisResponse:
        media_id = uuid4().hex
        source_name = file.filename or ""
        upload_path = await self._save_upload(media_id, file)
        image = ImageOps.exif_transpose(Image.open(upload_path)).convert("RGB")
        detections = self._analyze_frame(media_id, image, 0.0, confidence_threshold, include_low_confidence, source_name)
        preview_url = self._save_annotated_preview(media_id, image, detections)
        response = self._response(media_id, "image", preview_url, detections)
        self.store.save(response)
        return response

    async def analyze_video(
        self,
        file: UploadFile,
        confidence_threshold: float,
        frame_interval_seconds: float,
        include_low_confidence: bool,
    ) -> AnalysisResponse:
        media_id = uuid4().hex
        upload_path = await self._save_upload(media_id, file)
        detections = self._analyze_video_file(media_id, upload_path, confidence_threshold, frame_interval_seconds, include_low_confidence)
        response = self._response(media_id, "video", None, detections)
        self.store.save(response)
        return response

    async def _save_upload(self, media_id: str, file: UploadFile) -> Path:
        suffix = Path(file.filename or "upload").suffix.lower() or ".bin"
        destination = self.settings.uploads_dir / f"{media_id}{suffix}"
        with destination.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        return destination

    def _analyze_video_file(
        self,
        media_id: str,
        video_path: Path,
        confidence_threshold: float,
        frame_interval_seconds: float,
        include_low_confidence: bool,
    ) -> list[DetectionResult]:
        try:
            import cv2
        except ImportError:
            return []

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            return []

        fps = capture.get(cv2.CAP_PROP_FPS) or 25
        frame_step = max(1, int(fps * max(0.2, frame_interval_seconds)))
        detections: list[DetectionResult] = []
        frame_index = 0
        sampled_frames = 0

        while sampled_frames < self.settings.max_video_frames:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % frame_step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(rgb)
                frame_time = round(frame_index / fps, 2)
                detections.extend(self._analyze_frame(media_id, image, frame_time, confidence_threshold, include_low_confidence, video_path.name))
                sampled_frames += 1
            frame_index += 1

        capture.release()
        return detections

    def _analyze_frame(
        self,
        media_id: str,
        image: Image.Image,
        frame_time: float,
        confidence_threshold: float,
        include_low_confidence: bool,
        source_name: str = "",
    ) -> list[DetectionResult]:
        if self._is_empty_demo_source(source_name):
            return []

        detector_predictions = self.registry.detector.predict(image)
        if not detector_predictions:
            detector_predictions = self._full_frame_fallback_predictions(image)
        results: list[DetectionResult] = []
        frame_classification = self._classify_frame_context(image, detector_predictions)

        for index, prediction in enumerate(detector_predictions):
            if prediction.confidence < confidence_threshold and not include_low_confidence:
                continue

            crop = self._crop(image, prediction.bbox)
            crop_classification = self.registry.classifier.classify(crop)
            classification = self._select_contextual_classification(crop_classification, frame_classification, prediction)
            combined_confidence = round(min(prediction.confidence, classification.confidence), 3)
            if combined_confidence < confidence_threshold and not include_low_confidence:
                continue

            crop_name = f"{media_id}_{int(frame_time * 1000):08d}_{index}.jpg"
            crop_path = self.settings.crops_dir / crop_name
            crop.save(crop_path, quality=88)
            retrieval_candidates = self.retrieval.retrieve(crop) if self.retrieval else []
            top_candidates = self._top_candidates(classification.species_label, classification.confidence, retrieval_candidates)
            if self.species_catalog:
                top_candidates = self.species_catalog.enrich_candidates(top_candidates)
            retrieval_confidence = retrieval_candidates[0].confidence if retrieval_candidates else 0.0
            display_label = classification.species_label
            if self.registry.classifier.name == "fallback-classifier" and retrieval_candidates:
                display_label = retrieval_candidates[0].label
                combined_confidence = round(min(prediction.confidence, retrieval_confidence), 3)
            elif self._should_use_retrieval_display(classification.species_label, classification.confidence, retrieval_candidates):
                display_label = retrieval_candidates[0].label
                combined_confidence = round(min(prediction.confidence, retrieval_confidence), 3)
            evidence_state = self._retrieval_evidence_state(display_label, retrieval_candidates)
            review_status = self._review_status(
                prediction.confidence,
                classification.confidence,
                combined_confidence,
                display_label,
                retrieval_candidates,
                evidence_state,
            )
            review_reasons = self._review_reasons(top_candidates, evidence_state, review_status)

            results.append(
                DetectionResult(
                    media_id=media_id,
                    frame_time=frame_time,
                    bbox=prediction.bbox,
                    detected_type=prediction.detected_type,
                    species_label=display_label,
                    confidence=combined_confidence,
                    detection_confidence=round(prediction.confidence, 3),
                    classification_confidence=round(classification.confidence, 3),
                    retrieval_confidence=round(retrieval_confidence, 3),
                    top_candidates=top_candidates,
                    review_status=review_status,
                    review_reasons=review_reasons,
                    preview_crop_path=f"/media/crops/{crop_name}",
                )
            )
        return results

    def _full_frame_fallback_predictions(self, image: Image.Image) -> list[DetectorPrediction]:
        if self.registry.classifier.name == "fallback-classifier":
            return []
        classification = self.registry.classifier.classify(image)
        if classification.confidence < FULL_FRAME_FALLBACK_CLASSIFICATION_THRESHOLD:
            return []
        width, height = image.size
        return [
            DetectorPrediction(
                bbox=BoundingBox(x=0, y=0, width=width, height=height),
                detected_type="animal_candidate",
                confidence=FULL_FRAME_FALLBACK_DETECTION_CONFIDENCE,
            )
        ]

    def _classify_frame_context(self, image: Image.Image, predictions: list[DetectorPrediction]) -> ClassifierPrediction | None:
        if not predictions or self.registry.classifier.name == "fallback-classifier":
            return None
        if len(predictions) == 1 and self._covers_most_of_frame(predictions[0].bbox, image.size):
            return None
        return self.registry.classifier.classify(image)

    def _select_contextual_classification(
        self,
        crop_classification: ClassifierPrediction,
        frame_classification: ClassifierPrediction | None,
        prediction: DetectorPrediction,
    ) -> ClassifierPrediction:
        if frame_classification is None:
            return crop_classification
        if self._is_generalized_classifier_label(crop_classification.species_label) and not self._is_generalized_classifier_label(frame_classification.species_label):
            return frame_classification
        if self._is_generalized_classifier_label(frame_classification.species_label):
            return crop_classification
        crop_species = self.species_catalog.match(crop_classification.species_label) if self.species_catalog else None
        frame_species = self.species_catalog.match(frame_classification.species_label) if self.species_catalog else None
        if self._species_taxon_group(crop_species) != self._species_taxon_group(frame_species):
            if frame_classification.confidence >= crop_classification.confidence + 0.08:
                return frame_classification
            if prediction.confidence < self.settings.species_ready_threshold and frame_classification.confidence >= crop_classification.confidence:
                return frame_classification
        return crop_classification

    def _top_candidates(
        self,
        species_label: str,
        classification_confidence: float,
        retrieval_candidates: list[SpeciesCandidate] | None = None,
    ) -> list[SpeciesCandidate]:
        if self.registry.classifier.name == "fallback-classifier" and retrieval_candidates:
            return retrieval_candidates[:5]
        candidates = [
            SpeciesCandidate(
                label=species_label,
                confidence=round(classification_confidence, 3),
                source=self.registry.classifier.name,
                evidence="本地分类模型输出",
            )
        ]
        candidates.extend(retrieval_candidates or [])
        candidates.sort(key=lambda candidate: candidate.confidence, reverse=True)
        return candidates[:5]

    def _review_status(
        self,
        detection_confidence: float,
        classification_confidence: float,
        combined_confidence: float,
        species_label: str,
        retrieval_candidates: list[SpeciesCandidate],
        evidence_state: str | None = None,
    ) -> str:
        if self.registry.classifier.name == "fallback-classifier":
            return "needs_review"
        evidence_state = evidence_state or self._retrieval_evidence_state(species_label, retrieval_candidates)
        if evidence_state == "conflict":
            return "needs_review" if combined_confidence >= self.settings.species_candidate_threshold else "low_confidence"
        if (
            detection_confidence >= self.settings.species_ready_threshold
            and classification_confidence >= self.settings.species_ready_threshold
            and combined_confidence >= self.settings.species_ready_threshold
            and evidence_state == "aligned"
        ):
            if not self._label_can_be_ready(species_label):
                return "needs_review"
            return "ready"
        if combined_confidence >= self.settings.species_candidate_threshold:
            return "needs_review"
        return "low_confidence"

    def _review_reasons(self, candidates: list[SpeciesCandidate], evidence_state: str, review_status: str) -> list[str]:
        if self.species_catalog:
            return self.species_catalog.review_reasons(candidates, evidence_state, review_status, self._top_candidate_gap(candidates))
        if review_status == "ready":
            return []
        if evidence_state == "conflict":
            return ["model_reference_conflict"]
        if evidence_state == "weak":
            return ["weak_reference_evidence"]
        if review_status == "low_confidence":
            return ["low_confidence"]
        return ["candidate_needs_confirmation"]

    def _top_candidate_gap(self, candidates: list[SpeciesCandidate]) -> float:
        if len(candidates) < 2:
            return 1.0
        return candidates[0].confidence - candidates[1].confidence

    def _label_can_be_ready(self, species_label: str) -> bool:
        normalized_label = self._normalize_label(species_label)
        if normalized_label in STRICT_REVIEW_LABEL_KEYS:
            return False
        if not self.species_catalog:
            return True
        species = self.species_catalog.match(species_label)
        if species is None:
            return False
        return species.recognition_tier in DIRECT_READY_TIERS

    def _should_use_retrieval_display(
        self,
        classification_label: str,
        classification_confidence: float,
        retrieval_candidates: list[SpeciesCandidate],
    ) -> bool:
        if not retrieval_candidates:
            return False
        top_candidate = retrieval_candidates[0]
        if self._normalize_label(top_candidate.label) == "":
            return False
        if self._is_generalized_classifier_label(classification_label):
            return False
        if self._should_use_weak_reference_refinement(top_candidate, retrieval_candidates):
            return True
        next_confidence = retrieval_candidates[1].confidence if len(retrieval_candidates) > 1 else 0.0
        classifier_species = self.species_catalog.match(classification_label) if self.species_catalog else None
        return (
            classification_confidence < self.settings.retrieval_display_override_classifier_max_confidence
            and top_candidate.confidence >= self.settings.retrieval_display_override_threshold
            and (top_candidate.confidence - next_confidence) >= self.settings.retrieval_display_override_margin
            and not self._has_cross_taxon_conflict(classifier_species, top_candidate.label)
        )

    def _should_use_weak_reference_refinement(
        self,
        top_candidate: SpeciesCandidate,
        retrieval_candidates: list[SpeciesCandidate],
    ) -> bool:
        if top_candidate.source != "pdf-weak-reference":
            return False
        if top_candidate.confidence < self.settings.species_candidate_threshold:
            return False
        next_confidence = retrieval_candidates[1].confidence if len(retrieval_candidates) > 1 else 0.0
        return (top_candidate.confidence - next_confidence) >= self.settings.weak_reference_override_margin

    def _retrieval_evidence_state(self, species_label: str, retrieval_candidates: list[SpeciesCandidate]) -> str:
        if not retrieval_candidates:
            return "missing"
        classifier_label = self._normalize_label(species_label)
        confident_candidates = [
            candidate
            for candidate in retrieval_candidates[:3]
            if candidate.confidence >= self.settings.species_candidate_threshold
        ]
        if not confident_candidates:
            return "weak"
        top_candidate = confident_candidates[0]
        if self._normalize_label(top_candidate.label) == classifier_label:
            return "aligned"
        if any(self._normalize_label(candidate.label) == classifier_label for candidate in confident_candidates[1:]):
            return "supported"
        return "conflict"

    def _is_generalized_classifier_label(self, label: str) -> bool:
        normalized = self._normalize_label(label)
        if not normalized:
            return True
        return label.startswith("未知") or "候选" in label

    def _has_cross_taxon_conflict(self, classifier_species, retrieval_label: str) -> bool:
        if not self.species_catalog:
            return False
        retrieval_species = self.species_catalog.match(retrieval_label)
        classifier_group = self._species_taxon_group(classifier_species)
        retrieval_group = self._species_taxon_group(retrieval_species)
        return bool(classifier_group and retrieval_group and classifier_group != retrieval_group)

    def _species_taxon_group(self, species) -> str:
        if species is None:
            return ""
        return (getattr(species, "taxon_group", "") or "").strip()

    def _covers_most_of_frame(self, bbox, image_size: tuple[int, int]) -> bool:
        image_width, image_height = image_size
        frame_area = max(1, image_width * image_height)
        return (bbox.width * bbox.height) / frame_area >= 0.86

    def _normalize_label(self, value: str) -> str:
        return "".join(ch.lower() for ch in value if ch.isalnum())

    def _crop(self, image: Image.Image, bbox) -> Image.Image:
        width, height = image.size
        pad_x = int(bbox.width * CROP_CONTEXT_PADDING_RATIO)
        pad_y = int(bbox.height * CROP_CONTEXT_PADDING_RATIO)
        x1 = max(0, bbox.x - pad_x)
        y1 = max(0, bbox.y - pad_y)
        x2 = min(width, bbox.x + bbox.width + pad_x)
        y2 = min(height, bbox.y + bbox.height + pad_y)
        return image.crop((x1, y1, x2, y2))

    def _save_annotated_preview(self, media_id: str, image: Image.Image, detections: list[DetectionResult]) -> str:
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        for detection in detections:
            x1 = detection.bbox.x
            y1 = detection.bbox.y
            x2 = detection.bbox.x + detection.bbox.width
            y2 = detection.bbox.y + detection.bbox.height
            label = self._annotation_label(detection)
            draw.rectangle((x1, y1, x2, y2), outline=(185, 212, 107), width=4)
            text_box = draw.textbbox((x1, max(0, y1 - 24)), label)
            draw.rectangle(text_box, fill=(185, 212, 107))
            draw.text((x1, max(0, y1 - 24)), label, fill=(20, 32, 21))

        preview_name = f"{media_id}_annotated.jpg"
        preview_path = self.settings.uploads_dir / preview_name
        annotated.save(preview_path, quality=90)
        return f"/media/uploads/{preview_name}"

    def _annotation_label(self, detection: DetectionResult) -> str:
        confidence = round(detection.confidence * 100)
        if detection.review_status == "ready":
            return f"{detection.species_label} {confidence}%"
        if detection.review_status == "low_confidence":
            return f"低置信 {confidence}%"
        return f"待复核 {confidence}%"

    def _is_empty_demo_source(self, source_name: str) -> bool:
        return "empty" in source_name.lower()

    def _response(self, media_id: str, media_type: str, preview_url: str | None, detections: list[DetectionResult]) -> AnalysisResponse:
        summary = Counter(item.species_label for item in detections)
        if not detections:
            message = "未发现达到阈值的动物目标"
        elif self.registry.classifier.name == "fallback-classifier":
            message = "检测完成，物种分类模型未接入"
        elif all(item.review_status == "ready" for item in detections):
            message = "识别完成，当前结果达到展示阈值，仍建议结合原始画面复核"
        else:
            message = "已生成候选结果，存在低置信或待复核目标"
        model_status = self.status()
        return AnalysisResponse(
            media_id=media_id,
            media_type=media_type,
            preview_url=preview_url,
            detections=detections,
            species_summary=dict(summary),
            model_status=model_status,
            message=message,
        )

    def status(self) -> dict[str, str]:
        model_status = self.registry.status()
        if self.retrieval:
            model_status = {**model_status, **self.retrieval.status()}
        if self.species_catalog:
            model_status = {**model_status, **self.species_catalog.status()}
        return model_status
