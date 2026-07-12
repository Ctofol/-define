from __future__ import annotations

import json
from pathlib import Path

from app.schemas import AnalysisResponse


class ResultStore:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def save(self, response: AnalysisResponse) -> None:
        path = self.results_dir / f"{response.media_id}.json"
        path.write_text(response.model_dump_json(indent=2), encoding="utf-8")

    def get(self, media_id: str) -> AnalysisResponse | None:
        path = self.results_dir / f"{media_id}.json"
        if not path.exists():
            return None
        return AnalysisResponse.model_validate_json(path.read_text(encoding="utf-8"))

    def list_recent(self, limit: int = 25) -> list[AnalysisResponse]:
        paths = sorted(self.results_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        responses: list[AnalysisResponse] = []
        for path in paths[:limit]:
            try:
                responses.append(AnalysisResponse.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return responses
