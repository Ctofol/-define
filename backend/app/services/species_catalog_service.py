from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas import SpeciesCandidate, SpeciesEntry
from app.services.species_service import SpeciesService

DEFAULT_PDF_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "pdf_species_catalog.json"
DEFAULT_PLANT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "plant_species_catalog.json"


class SpeciesCatalogService:
    """Adds region and review metadata to model candidates.

    This is the adapter point for a larger 400-500 species checklist. Today it
    is backed by the curated species knowledge file, but the inference pipeline
    only depends on this service interface.
    """

    def __init__(
        self,
        species_service: SpeciesService | None = None,
        pdf_catalog_path: Path | None = None,
        plant_catalog_path: Path | None = None,
    ):
        self.species_service = species_service or SpeciesService()
        self._species = self.species_service.list_species()
        if pdf_catalog_path is not None or species_service is None:
            self._species = self._merge_species(self._species, self._load_pdf_catalog(pdf_catalog_path or DEFAULT_PDF_CATALOG_PATH))
        if plant_catalog_path is not None or species_service is None:
            self._species = self._merge_species(self._species, self._load_pdf_catalog(plant_catalog_path or DEFAULT_PLANT_CATALOG_PATH))
        self._by_id = {item.species_id: item for item in self._species}
        self._by_label, self._by_similar_label = self._build_label_indexes(self._species)

    def list_species(self, category: str | None = None, recognition_tier: str | None = None) -> list[SpeciesEntry]:
        species = self._species
        if category:
            species = [item for item in species if item.category == category]
        if recognition_tier:
            species = [item for item in species if item.recognition_tier == recognition_tier]
        return species

    def get_species(self, species_id: str) -> SpeciesEntry | None:
        return self._by_id.get(species_id)

    def enrich_candidates(self, candidates: list[SpeciesCandidate]) -> list[SpeciesCandidate]:
        return [self.enrich_candidate(candidate) for candidate in candidates]

    def enrich_candidate(self, candidate: SpeciesCandidate) -> SpeciesCandidate:
        species = self.match(candidate.label)
        if species is None:
            flags = list(dict.fromkeys([*candidate.review_flags, "not_in_local_checklist"]))
            return candidate.model_copy(
                update={
                    "region_status": "out_of_catalog",
                    "priority": "external_candidate",
                    "review_flags": flags,
                }
            )

        flags = list(candidate.review_flags)
        if species.protection_level.startswith("国家") or "一级" in species.protection_level or "二级" in species.protection_level:
            flags.append("protected_species")
        if species.recognition_tier not in {"high_demo", "candidate"}:
            flags.append("knowledge_only_species")

        return candidate.model_copy(
            update={
                "species_id": species.species_id,
                "latin_name": species.latin_name,
                "taxon_group": species.taxon_group,
                "protection_level": species.protection_level,
                "region_status": "local_checklist",
                "priority": species.recognition_tier,
                "review_flags": list(dict.fromkeys(flags)),
            }
        )

    def match(self, label: str) -> SpeciesEntry | None:
        normalized = self._normalize(label)
        if not normalized:
            return None
        if normalized in self._by_id:
            return self._by_id[normalized]
        return self._by_label.get(normalized) or self._by_similar_label.get(normalized)

    def review_reasons(
        self,
        candidates: list[SpeciesCandidate],
        evidence_state: str,
        review_status: str,
        top_gap: float,
    ) -> list[str]:
        reasons: list[str] = []
        if review_status == "low_confidence":
            reasons.append("low_confidence")
        if evidence_state == "conflict":
            reasons.append("model_reference_conflict")
        if evidence_state == "weak":
            reasons.append("weak_reference_evidence")
        if candidates and candidates[0].region_status == "out_of_catalog":
            reasons.append("not_in_local_checklist")
        if top_gap < 0.12 and len(candidates) > 1:
            reasons.append("close_top_candidates")
        if any("protected_species" in candidate.review_flags and candidate.confidence >= 0.45 for candidate in candidates[:3]):
            reasons.append("protected_species_candidate")
        if not reasons and review_status == "needs_review":
            reasons.append("candidate_needs_confirmation")
        return list(dict.fromkeys(reasons))

    def status(self) -> dict[str, str]:
        plant_count = len(self.list_species(category="plant"))
        return {
            "species_catalog": "local-checklist",
            "species_catalog_detail": f"{len(self._species)} species / enrichment ready",
            "plant_catalog_detail": f"{plant_count} plants / knowledge ready",
        }

    def _build_label_indexes(self, species: list[SpeciesEntry]) -> tuple[dict[str, SpeciesEntry], dict[str, SpeciesEntry]]:
        exact_index: dict[str, SpeciesEntry] = {}
        similar_index: dict[str, SpeciesEntry] = {}
        for item in species:
            for label in [item.species_id, item.cn_name, item.latin_name or "", item.genus or ""]:
                normalized = self._normalize(label)
                if normalized:
                    exact_index.setdefault(normalized, item)
            for label in item.similar_species:
                normalized = self._normalize(label)
                if normalized and normalized not in exact_index:
                    similar_index.setdefault(normalized, item)
        return exact_index, similar_index

    def _normalize(self, value: str) -> str:
        return "".join(ch.lower() for ch in value if ch.isalnum())

    def _load_pdf_catalog(self, path: Path) -> list[SpeciesEntry]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8-sig") as file:
            raw_items = json.load(file)
        return [SpeciesEntry.model_validate(item) for item in raw_items]

    def _merge_species(self, curated: list[SpeciesEntry], pdf_catalog: list[SpeciesEntry]) -> list[SpeciesEntry]:
        merged = list(curated)
        indexed_labels: set[str] = set()
        for item in curated:
            for label in [item.species_id, item.cn_name, item.latin_name or ""]:
                normalized = self._normalize(label)
                if normalized:
                    indexed_labels.add(normalized)

        for item in pdf_catalog:
            labels = [item.species_id, item.cn_name, item.latin_name or ""]
            if any(self._normalize(label) in indexed_labels for label in labels):
                continue
            merged.append(item)
            for label in labels:
                normalized = self._normalize(label)
                if normalized:
                    indexed_labels.add(normalized)
        return merged


@lru_cache
def get_species_catalog_service() -> SpeciesCatalogService:
    return SpeciesCatalogService()
