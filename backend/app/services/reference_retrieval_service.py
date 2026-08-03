from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat

from app.schemas import SpeciesCandidate
from app.settings import get_settings


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
CANONICAL_LABELS = {
    "亚洲黑熊": "黑熊",
}
IGNORED_REVIEW_STATUSES = {"reject", "duplicate", "reference_only"}


@dataclass(frozen=True)
class ReferenceVector:
    label: str
    file_path: Path
    file_url: str
    vector: tuple[float, ...]
    source_name: str
    confidence_cap: float


class ReferenceRetrievalService:
    def __init__(
        self,
        reference_root: Path | None = None,
        manifest_path: Path | None = None,
        weak_manifest_path: Path | None = None,
        media_prefix: str = "/media/reference-species",
        max_images_per_label: int = 80,
        backend: str | None = None,
        embedding_model_path: Path | None = None,
        weak_reference_max_confidence: float | None = None,
        weak_reference_confidence_boost: float | None = None,
    ):
        settings = get_settings()
        self.reference_root = reference_root or settings.reference_species_dir
        self.manifest_path = manifest_path or self._default_manifest_path(settings.storage_dir)
        self.weak_manifest_path = weak_manifest_path if weak_manifest_path is not None else settings.weak_reference_manifest_path
        self.media_prefix = media_prefix.rstrip("/")
        self.max_images_per_label = max_images_per_label
        self.backend = backend or settings.reference_retrieval_backend
        self.embedding_model_path = embedding_model_path or settings.reference_embedding_model_path
        self.weak_reference_max_confidence = (
            weak_reference_max_confidence
            if weak_reference_max_confidence is not None
            else settings.weak_reference_max_confidence
        )
        self.weak_reference_confidence_boost = (
            weak_reference_confidence_boost
            if weak_reference_confidence_boost is not None
            else settings.weak_reference_confidence_boost
        )
        self._index: list[ReferenceVector] | None = None
        self._processor = None
        self._embedding_model = None

    def retrieve(self, image: Image.Image, limit: int = 5, exclude_paths: set[Path] | None = None) -> list[SpeciesCandidate]:
        index = self._ensure_index()
        if not index:
            return []

        resolved_excludes = {path.resolve() for path in (exclude_paths or set())}
        query = self._feature_vector(image)
        by_label: dict[str, tuple[float, ReferenceVector]] = {}
        for item in index:
            if item.file_path.resolve() in resolved_excludes:
                continue
            similarity = self._cosine_similarity(query, item.vector)
            current = by_label.get(item.label)
            if current is None or similarity > current[0] or (similarity == current[0] and item.confidence_cap > current[1].confidence_cap):
                by_label[item.label] = (similarity, item)

        ranked = sorted(by_label.items(), key=lambda item: item[1][0], reverse=True)
        candidates: list[SpeciesCandidate] = []
        for index, (label, (similarity, item)) in enumerate(ranked):
            next_similarity = ranked[index + 1][1][0] if index + 1 < len(ranked) else 0.0
            confidence = self._calibrated_confidence(similarity, similarity - next_similarity)
            if item.source_name == "pdf-weak-reference":
                confidence += self.weak_reference_confidence_boost
            confidence = min(item.confidence_cap, confidence)
            candidates.append(
                SpeciesCandidate(
                    label=label,
                    confidence=round(confidence, 3),
                    source=item.source_name,
                    evidence=f"相似参考图：{item.file_path.name}",
                    sample_url=item.file_url,
                )
            )
        return candidates[:limit]

    def status(self) -> dict[str, str]:
        if self._index is None:
            return {"reference_retrieval": self.backend, "reference_retrieval_detail": "lazy index"}
        labels = {item.label for item in self._index}
        weak_count = sum(1 for item in self._index if item.source_name == "pdf-weak-reference")
        return {
            "reference_retrieval": self.backend,
            "reference_retrieval_detail": f"{len(self._index)} samples / {len(labels)} labels / {weak_count} weak",
        }

    def warmup(self) -> None:
        self._ensure_index()

    def _ensure_index(self) -> list[ReferenceVector]:
        if self._index is None:
            self._index = self._build_index()
        return self._index

    def _build_index(self) -> list[ReferenceVector]:
        rows = self._manifest_rows()
        rows.extend(self._weak_manifest_rows())
        if not rows:
            rows = self._fallback_reference_rows()

        vectors: list[ReferenceVector] = []
        per_label_count: dict[str, int] = {}
        for row in rows:
            label = self._canonical_label(row["label"])
            if per_label_count.get(label, 0) >= self.max_images_per_label:
                continue
            path = self._resolve_reference_path(row)
            if not path.exists() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                with Image.open(path) as image:
                    vector = self._feature_vector(image)
            except Exception:
                continue
            vectors.append(
                ReferenceVector(
                    label=label,
                    file_path=path,
                    file_url=self._file_url(path),
                    vector=vector,
                    source_name=row.get("source_name", "reference-retrieval"),
                    confidence_cap=float(row.get("confidence_cap", 0.98)),
                )
            )
            per_label_count[label] = per_label_count.get(label, 0) + 1
        if not vectors and rows:
            for row in self._fallback_reference_rows():
                label = self._canonical_label(row["label"])
                if per_label_count.get(label, 0) >= self.max_images_per_label:
                    continue
                path = self._resolve_reference_path(row)
                if not path.exists() or path.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                try:
                    with Image.open(path) as image:
                        vector = self._feature_vector(image)
                except Exception:
                    continue
                vectors.append(
                    ReferenceVector(
                        label=label,
                        file_path=path,
                        file_url=self._file_url(path),
                        vector=vector,
                        source_name=row.get("source_name", "reference-retrieval"),
                        confidence_cap=float(row.get("confidence_cap", 0.98)),
                    )
                )
                per_label_count[label] = per_label_count.get(label, 0) + 1
        return vectors

    def _manifest_rows(self) -> list[dict[str, str]]:
        if not self.manifest_path.exists():
            return []
        rows: list[dict[str, str]] = []
        with self.manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                status = row.get("review_status", "")
                if status in IGNORED_REVIEW_STATUSES:
                    continue
                if row.get("file_path") and row.get("label"):
                    rows.append(
                        {
                            "file_path": row["file_path"],
                            "relative_path": row.get("relative_path", ""),
                            "label": row["label"],
                            "source_name": "reference-retrieval",
                            "confidence_cap": "0.98",
                        }
                    )
        return rows

    def _default_manifest_path(self, storage_dir: Path) -> Path:
        round5_cleaned = storage_dir / "training" / "species_manifest_v20_round5_cleaned.csv"
        if round5_cleaned.exists():
            return round5_cleaned
        round4_cleaned = storage_dir / "training" / "species_manifest_v19_round4_cleaned.csv"
        if round4_cleaned.exists():
            return round4_cleaned
        round3_cleaned = storage_dir / "training" / "species_manifest_v18_round3_cleaned.csv"
        if round3_cleaned.exists():
            return round3_cleaned
        cleaned_round2 = storage_dir / "training" / "species_manifest_v17_cleaned_confusion_round2.csv"
        if cleaned_round2.exists():
            return cleaned_round2
        cleaned_confusion = storage_dir / "training" / "species_manifest_v16_cleaned_confusion.csv"
        if cleaned_confusion.exists():
            return cleaned_confusion
        reviewed_supplement = storage_dir / "training" / "species_manifest_v15_reviewed_supplement.csv"
        if reviewed_supplement.exists():
            return reviewed_supplement
        return storage_dir / "training" / "species_manifest.csv"

    def _weak_manifest_rows(self) -> list[dict[str, str]]:
        if not self.weak_manifest_path or not self.weak_manifest_path.exists():
            return []
        rows: list[dict[str, str]] = []
        with self.weak_manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                if row.get("file_path") and row.get("label"):
                    rows.append(
                        {
                            "file_path": row["file_path"],
                            "relative_path": row.get("relative_path", ""),
                            "label": row["label"],
                            "source_name": "pdf-weak-reference",
                            "confidence_cap": str(self.weak_reference_max_confidence),
                        }
                    )
        return rows

    def _fallback_reference_rows(self) -> list[dict[str, str]]:
        if not self.reference_root.exists():
            return []
        rows: list[dict[str, str]] = []
        for folder in sorted(path for path in self.reference_root.iterdir() if path.is_dir()):
            if folder.name.startswith("_") or folder.name == "待复核":
                continue
            label = self._canonical_label(folder.name)
            for image_path in sorted(folder.iterdir()):
                if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
                    rows.append(
                        {
                            "file_path": str(image_path),
                            "relative_path": str(image_path.relative_to(self.reference_root).as_posix()),
                            "label": label,
                            "source_name": "reference-retrieval",
                            "confidence_cap": "0.98",
                        }
                    )
        return rows

    def _feature_vector(self, image: Image.Image) -> tuple[float, ...]:
        if self.backend == "transformers":
            return self._embedding_vector(image)
        prepared = ImageOps.exif_transpose(image).convert("RGB").resize((96, 96))
        histogram_image = prepared.quantize(colors=64).convert("RGB")
        hist = histogram_image.histogram()
        total = sum(hist) or 1
        color_features = [value / total for value in hist]

        gray = prepared.convert("L")
        edge = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(gray)
        edge_stat = ImageStat.Stat(edge)
        shape_features = [
            stat.mean[0] / 255,
            stat.stddev[0] / 128,
            edge_stat.mean[0] / 255,
            edge_stat.stddev[0] / 128,
            prepared.size[0] / max(1, prepared.size[1]),
        ]
        vector = [*color_features, *shape_features]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return tuple(value / norm for value in vector)

    def _cosine_similarity(self, left: tuple[float, ...], right: tuple[float, ...]) -> float:
        return sum(a * b for a, b in zip(left, right))

    def _calibrated_confidence(self, similarity: float, margin: float) -> float:
        # Color/texture similarity is useful as weak evidence, but absolute cosine scores
        # are often overconfident. Calibrate by both score and separation from the next label.
        score_component = max(0.0, min(0.6, (similarity - 0.92) / 0.08 * 0.6))
        margin_component = max(0.0, min(0.4, margin * 8.0))
        return max(0.05, min(0.98, score_component + margin_component))

    def _canonical_label(self, label: str) -> str:
        return CANONICAL_LABELS.get(label, label)

    def _resolve_reference_path(self, row: dict[str, str]) -> Path:
        relative_path = row.get("relative_path", "").replace("\\", "/").strip()
        if relative_path:
            candidate = self.reference_root / relative_path
            if candidate.exists():
                return candidate

        raw_path = Path(row["file_path"])
        if raw_path.exists():
            return raw_path

        normalized = str(row["file_path"]).replace("\\", "/")
        marker = "reference_species/"
        if marker in normalized:
            candidate = self.reference_root / normalized.split(marker, 1)[1]
            if candidate.exists():
                return candidate

        return raw_path

    def _file_url(self, path: Path) -> str:
        try:
            relative = path.relative_to(self.reference_root).as_posix()
        except ValueError:
            return ""
        parts = [self._quote(part) for part in relative.split("/")]
        return f"{self.media_prefix}/{'/'.join(parts)}"

    def _quote(self, value: str) -> str:
        from urllib.parse import quote

        return quote(value)

    def _embedding_vector(self, image: Image.Image) -> tuple[float, ...]:
        if self.embedding_model_path is None:
            return self._feature_vector_histogram(image)
        if self._processor is None or self._embedding_model is None:
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            self._processor = AutoImageProcessor.from_pretrained(str(self.embedding_model_path), local_files_only=True)
            self._embedding_model = AutoModelForImageClassification.from_pretrained(str(self.embedding_model_path), local_files_only=True)
            self._embedding_model.eval()

        import torch

        inputs = self._processor(images=ImageOps.exif_transpose(image).convert("RGB"), return_tensors="pt")
        with torch.no_grad():
            outputs = self._embedding_model.mobilenet_v2(**inputs)
            vector = outputs.pooler_output[0]
        norm = torch.linalg.vector_norm(vector).item() or 1.0
        return tuple(float(value / norm) for value in vector.tolist())

    def _feature_vector_histogram(self, image: Image.Image) -> tuple[float, ...]:
        prepared = ImageOps.exif_transpose(image).convert("RGB").resize((96, 96))
        histogram_image = prepared.quantize(colors=64).convert("RGB")
        hist = histogram_image.histogram()
        total = sum(hist) or 1
        color_features = [value / total for value in hist]

        gray = prepared.convert("L")
        edge = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(gray)
        edge_stat = ImageStat.Stat(edge)
        shape_features = [
            stat.mean[0] / 255,
            stat.stddev[0] / 128,
            edge_stat.mean[0] / 255,
            edge_stat.stddev[0] / 128,
            prepared.size[0] / max(1, prepared.size[1]),
        ]
        vector = [*color_features, *shape_features]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return tuple(value / norm for value in vector)


@lru_cache
def get_reference_retrieval_service() -> ReferenceRetrievalService:
    return ReferenceRetrievalService()
