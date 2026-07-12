from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageDraw, ImageOps

from app.models.model_registry import ModelRegistry
from app.schemas import AnalysisResponse, DetectionResult
from app.services.result_store import ResultStore
from app.settings import Settings


class InferenceService:
    def __init__(self, settings: Settings, registry: ModelRegistry, store: ResultStore):
        self.settings = settings
        self.registry = registry
        self.store = store

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
        demo_label = self._demo_species_label(source_name)
        if demo_label == "empty":
            return []

        detector_predictions = self.registry.detector.predict(image)
        results: list[DetectionResult] = []

        for index, prediction in enumerate(detector_predictions):
            if prediction.confidence < confidence_threshold and not include_low_confidence:
                continue

            crop = self._crop(image, prediction.bbox)
            classification = self.registry.classifier.classify(crop)
            if demo_label and self.registry.classifier.name == "fallback-classifier":
                classification.species_label = demo_label
                classification.confidence = 0.92
            combined_confidence = round(min(prediction.confidence, classification.confidence), 3)
            if combined_confidence < confidence_threshold and not include_low_confidence:
                continue

            crop_name = f"{media_id}_{int(frame_time * 1000):08d}_{index}.jpg"
            crop_path = self.settings.crops_dir / crop_name
            crop.save(crop_path, quality=88)

            results.append(
                DetectionResult(
                    media_id=media_id,
                    frame_time=frame_time,
                    bbox=prediction.bbox,
                    detected_type=prediction.detected_type,
                    species_label=classification.species_label,
                    confidence=combined_confidence,
                    preview_crop_path=f"/media/crops/{crop_name}",
                )
            )
        return results

    def _crop(self, image: Image.Image, bbox) -> Image.Image:
        width, height = image.size
        x1 = max(0, bbox.x)
        y1 = max(0, bbox.y)
        x2 = min(width, bbox.x + bbox.width)
        y2 = min(height, bbox.y + bbox.height)
        return image.crop((x1, y1, x2, y2))

    def _save_annotated_preview(self, media_id: str, image: Image.Image, detections: list[DetectionResult]) -> str:
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        for detection in detections:
            x1 = detection.bbox.x
            y1 = detection.bbox.y
            x2 = detection.bbox.x + detection.bbox.width
            y2 = detection.bbox.y + detection.bbox.height
            label = f"{detection.species_label} {round(detection.confidence * 100)}%"
            draw.rectangle((x1, y1, x2, y2), outline=(185, 212, 107), width=4)
            text_box = draw.textbbox((x1, max(0, y1 - 24)), label)
            draw.rectangle(text_box, fill=(185, 212, 107))
            draw.text((x1, max(0, y1 - 24)), label, fill=(20, 32, 21))

        preview_name = f"{media_id}_annotated.jpg"
        preview_path = self.settings.uploads_dir / preview_name
        annotated.save(preview_path, quality=90)
        return f"/media/uploads/{preview_name}"

    def _demo_species_label(self, source_name: str) -> str | None:
        normalized = source_name.lower()
        if "empty" in normalized:
            return "empty"
        demo_labels = {
            "deer": "梅花鹿",
            "boar": "野猪",
            "fox": "狐狸",
            "wolf": "狼",
        }
        for key, label in demo_labels.items():
            if key in normalized:
                return label
        return None

    def _response(self, media_id: str, media_type: str, preview_url: str | None, detections: list[DetectionResult]) -> AnalysisResponse:
        summary = Counter(item.species_label for item in detections)
        if not detections:
            message = "未发现达到阈值的动物目标"
        elif self.registry.classifier.name == "fallback-classifier":
            demo_labels = {"梅花鹿", "野猪", "狐狸", "狼"}
            if all(item.species_label in demo_labels for item in detections):
                message = "检测完成，当前使用轻量演示分类"
            else:
                message = "检测完成，物种分类模型未接入"
        else:
            message = "识别完成"
        return AnalysisResponse(
            media_id=media_id,
            media_type=media_type,
            preview_url=preview_url,
            detections=detections,
            species_summary=dict(summary),
            model_status=self.registry.status(),
            message=message,
        )
