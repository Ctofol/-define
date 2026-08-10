from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import SpeciesEntry  # noqa: E402
from app.services.species_catalog_service import SpeciesCatalogService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the merged species catalog as an admin-import JSON file.")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=ROOT / "exports" / "species_resources_import_454.json",
    )
    args = parser.parse_args()

    species = [entry.model_dump(mode="json") for entry in SpeciesCatalogService().list_species()]
    for row in species:
        SpeciesEntry.model_validate(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"species": species}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(f"exported {len(species)} species to {args.output}")


if __name__ == "__main__":
    main()
