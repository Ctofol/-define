from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas import SpeciesEntry


class SpeciesService:
    def __init__(self, data_path: Path | None = None):
        self.data_path = data_path or Path(__file__).resolve().parents[1] / "data" / "species_knowledge.json"
        self._species = self._load_species()
        self._by_id = {item.species_id: item for item in self._species}

    def list_species(self, recognition_tier: str | None = None, category: str | None = None) -> list[SpeciesEntry]:
        species = self._species
        if recognition_tier:
            species = [item for item in species if item.recognition_tier == recognition_tier]
        if category:
            species = [item for item in species if item.category == category]
        return species

    def get_species(self, species_id: str) -> SpeciesEntry | None:
        return self._by_id.get(species_id)

    def _load_species(self) -> list[SpeciesEntry]:
        with self.data_path.open("r", encoding="utf-8-sig") as file:
            raw_items = json.load(file)
        return [SpeciesEntry.model_validate(item) for item in raw_items]


@lru_cache
def get_species_service() -> SpeciesService:
    return SpeciesService()
