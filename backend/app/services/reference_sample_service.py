from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from app.schemas import ReferenceLibraryResponse, ReferenceSampleEntry, ReferenceSpeciesEntry
from app.settings import get_settings


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
IGNORED_FOLDERS = {"_supplement_candidates"}
IGNORED_FOLDER_PREFIXES = ("pdf_guangxi_species_",)
SUPPLEMENT_SKIP_FOLDERS = {"viverrids_quality_pass"}
SUPPLEMENT_LABEL_ALIASES = {
    "亚洲黑熊": "黑熊",
}


class ReferenceSampleService:
    def __init__(
        self,
        root_path: Path | None = None,
        media_prefix: str = "/media/reference-species",
        open_set_candidates_path: Path | None = None,
    ):
        self.root_path = root_path or get_settings().reference_species_dir
        self.media_prefix = media_prefix.rstrip("/")
        self.project_root = self.root_path.resolve().parent
        self.open_set_candidates_path = (
            open_set_candidates_path
            or self.project_root / "docs" / "viverrid_source_verification" / "knowledge_open_set_candidates.csv"
        )

    def list_species(self, include_empty: bool = True) -> ReferenceLibraryResponse:
        if not self.root_path.exists():
            return ReferenceLibraryResponse(species=[])

        entries = [
            self._build_species_entry(folder)
            for folder in self.root_path.iterdir()
            if folder.is_dir() and not self._is_operational_folder(folder.name)
        ]
        if not include_empty:
            entries = [entry for entry in entries if entry.image_count > 0]
        entries.sort(key=lambda entry: (entry.image_count == 0, entry.folder_name))
        return ReferenceLibraryResponse(species=entries)

    def get_species(self, folder_name: str) -> ReferenceSpeciesEntry | None:
        folder = self.root_path / folder_name
        if not folder.is_dir() or self._is_operational_folder(folder.name):
            return None
        return self._build_species_entry(folder)

    def list_pdf_weak_reference_species(self) -> ReferenceLibraryResponse:
        folder = self.root_path / "pdf_guangxi_species_images_v2"
        metadata_path = folder / "metadata.csv"
        quality_flags_path = folder / "quality_flags.csv"
        crops_folder = folder / "crops"
        if not metadata_path.exists() or not crops_folder.is_dir():
            return ReferenceLibraryResponse(species=[])

        rows = self._read_metadata_rows(metadata_path)
        quality_flags = self._read_quality_flags(quality_flags_path)
        entries: list[ReferenceSpeciesEntry] = []
        for row in rows:
            file_name = row.get("filename", "")
            cn_name = row.get("cn_name", "").strip()
            image_path = crops_folder / file_name
            if not file_name or not cn_name or not image_path.is_file():
                continue
            if quality_flags.get(file_name, "display") != "display":
                continue
            sample = ReferenceSampleEntry(
                file_name=file_name,
                file_url=self._versioned_media_url(image_path, folder.name, "crops", file_name),
                source="广西重点保护野生动物口袋书",
                license="reference_only",
                cn_name=cn_name,
                scientific_name=row.get("latin_name") or None,
                category=row.get("category") or None,
                taxon_group=row.get("taxon_group") or None,
                protection_level=row.get("protection_level") or None,
                source_pdf=row.get("source_pdf") or None,
                source_page=self._parse_int(row.get("source_page")),
                match_status=row.get("match_status") or None,
                subspecies=row.get("latin_name") or None,
                note="口袋书图鉴图片，可用于物种浏览、查询和识别结果对照。",
            )
            entries.append(
                ReferenceSpeciesEntry(
                    folder_name=cn_name,
                    image_count=1,
                    metadata_rows=1,
                    cover_url=sample.file_url,
                    sample_urls=[sample.file_url],
                    samples=[sample],
                )
            )
        entries.sort(key=lambda entry: entry.folder_name)
        return ReferenceLibraryResponse(species=entries)

    def _append_reviewed_supplement_samples(self, grouped: dict[str, list[ReferenceSampleEntry]]) -> None:
        supplement_root = self.root_path / "_supplement_candidates"
        if not supplement_root.is_dir():
            return

        for species_folder in sorted(path for path in supplement_root.iterdir() if path.is_dir()):
            if species_folder.name in SUPPLEMENT_SKIP_FOLDERS:
                continue
            species = SUPPLEMENT_LABEL_ALIASES.get(species_folder.name, species_folder.name)
            metadata = self._read_metadata(species_folder / "metadata.csv")
            for image_path in sorted(species_folder.iterdir()):
                if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                if image_path.name.startswith("contact_sheet"):
                    continue
                row = metadata.get(image_path.name, {})
                grouped.setdefault(species, []).append(
                    ReferenceSampleEntry(
                        file_name=image_path.name,
                        file_url=self._versioned_media_url(image_path, "_supplement_candidates", species_folder.name, image_path.name),
                        source=row.get("source") or "manual-reviewed-reference",
                        author=row.get("author") or None,
                        license=row.get("license") or None,
                        sex=row.get("sex") or None,
                        cn_name=species,
                        scientific_name=row.get("scientific_name") or row.get("latin_name") or None,
                        category="animal",
                        taxon_group=row.get("taxon_group") or None,
                        protection_level=row.get("protection_level") or None,
                        subspecies=row.get("subspecies") or row.get("scientific_name") or row.get("latin_name") or None,
                        note=row.get("note") or "manual-reviewed reference image",
                    )
                )

    def list_knowledge_open_set_species(self) -> ReferenceLibraryResponse:
        rows = self._read_metadata_rows(self.open_set_candidates_path)
        grouped: dict[str, list[ReferenceSampleEntry]] = {}
        for row in rows:
            species = row.get("species", "").strip()
            filename = row.get("filename", "").strip()
            copied_path = Path(row.get("copied_path", "").replace("\\", "/"))
            if copied_path and not copied_path.is_absolute():
                copied_path = self.project_root / copied_path
            if not species or not filename or not copied_path.is_file():
                continue
            try:
                relative_parts = copied_path.resolve().relative_to(self.root_path.resolve()).parts
            except ValueError:
                continue
            grouped.setdefault(species, []).append(
                ReferenceSampleEntry(
                    file_name=filename,
                    file_url=self._versioned_media_url(copied_path, *relative_parts),
                    source=row.get("source") or "GBIF",
                    author=row.get("author") or None,
                    license=row.get("license") or None,
                    cn_name=species,
                    scientific_name=row.get("scientific_name") or None,
                    category="animal",
                    taxon_group="兽类",
                    protection_level="相似物种参考",
                    subspecies=row.get("scientific_name") or None,
                    note="相似物种参考图，用于知识库展示和识别结果解释，不作为当前模型正类训练样本。",
                )
            )

        self._append_reviewed_supplement_samples(grouped)

        entries = [
            ReferenceSpeciesEntry(
                folder_name=species,
                image_count=len(samples),
                metadata_rows=len(samples),
                cover_url=samples[0].file_url if samples else None,
                sample_urls=[sample.file_url for sample in samples[:6]],
                samples=samples,
            )
            for species, samples in grouped.items()
        ]
        entries.sort(key=lambda entry: entry.folder_name)
        return ReferenceLibraryResponse(species=entries)

    def _read_quality_flags(self, quality_flags_path: Path) -> dict[str, str]:
        flags: dict[str, str] = {}
        for row in self._read_metadata_rows(quality_flags_path):
            file_name = row.get("filename", "")
            status = row.get("quality_status", "display") or "display"
            if file_name:
                flags[file_name] = status
        return flags

    def _is_operational_folder(self, folder_name: str) -> bool:
        return (
            folder_name.startswith(".")
            or folder_name in IGNORED_FOLDERS
            or any(folder_name.startswith(prefix) for prefix in IGNORED_FOLDER_PREFIXES)
        )

    def _build_species_entry(self, folder: Path) -> ReferenceSpeciesEntry:
        images = sorted([path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES])
        metadata = self._read_metadata(folder / "metadata.csv")
        sample_entries = [self._sample_entry(folder, image, metadata.get(image.name)) for image in images]
        sample_urls = [sample.file_url for sample in sample_entries[:6]]
        return ReferenceSpeciesEntry(
            folder_name=folder.name,
            image_count=len(images),
            metadata_rows=len(metadata),
            cover_url=sample_urls[0] if sample_urls else None,
            sample_urls=sample_urls,
            samples=sample_entries,
        )

    def _read_metadata(self, metadata_path: Path) -> dict[str, dict[str, str]]:
        metadata: dict[str, dict[str, str]] = {}
        for row in self._read_metadata_rows(metadata_path):
            file_name = row.get("filename") or row.get("file_name") or row.get("candidate")
            if file_name:
                metadata[file_name] = row
        return metadata

    def _read_metadata_rows(self, metadata_path: Path) -> list[dict[str, str]]:
        if not metadata_path.exists():
            return []
        with metadata_path.open("r", encoding="utf-8-sig", newline="") as file:
            raw_rows = list(csv.reader(file))
        if not raw_rows:
            return []
        header = [column.lstrip("\ufeff") for column in raw_rows[0]]
        return [self._normalize_metadata_row(header, raw_row) for raw_row in raw_rows[1:]]

    def _normalize_metadata_row(self, header: list[str], row: list[str]) -> dict[str, str]:
        if len(row) == 12 and len(header) < 12 and self._looks_like_latin(row[2]):
            keys = [
                "filename",
                "species",
                "scientific_name",
                "source",
                "author",
                "license",
                "source_url",
                "gbif_id",
                "country",
                "locality",
                "sex",
                "note",
            ]
            return dict(zip(keys, row))
        return {key: row[index] if index < len(row) else "" for index, key in enumerate(header)}

    def _looks_like_latin(self, text: str) -> bool:
        parts = text.strip().split()
        return len(parts) >= 2 and all(part[:1].isupper() or part.islower() for part in parts[:2])

    def _parse_int(self, value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _sample_entry(self, folder: Path, image: Path, metadata: dict[str, str] | None) -> ReferenceSampleEntry:
        metadata = metadata or {}
        return ReferenceSampleEntry(
            file_name=image.name,
            file_url=self._media_url(folder.name, image.name),
            source=metadata.get("source"),
            author=metadata.get("author"),
            license=metadata.get("license"),
            sex=metadata.get("sex"),
            cn_name=metadata.get("species") or metadata.get("cn_name"),
            scientific_name=metadata.get("scientific_name") or metadata.get("latin_name"),
            category=metadata.get("category"),
            taxon_group=metadata.get("taxon_group"),
            protection_level=metadata.get("protection_level"),
            source_pdf=metadata.get("source_pdf"),
            source_page=self._parse_int(metadata.get("source_page")),
            match_status=metadata.get("match_status"),
            subspecies=metadata.get("subspecies") or metadata.get("scientific_name") or metadata.get("latin_name"),
            note=metadata.get("note"),
        )

    def _media_url(self, folder_name: str, *path_parts: str) -> str:
        encoded_parts = [quote(part) for part in (folder_name, *path_parts)]
        return f"{self.media_prefix}/{'/'.join(encoded_parts)}"

    def _versioned_media_url(self, file_path: Path, folder_name: str, *path_parts: str) -> str:
        version = file_path.stat().st_mtime_ns
        return f"{self._media_url(folder_name, *path_parts)}?v={version}"


@lru_cache
def get_reference_sample_service() -> ReferenceSampleService:
    return ReferenceSampleService()
