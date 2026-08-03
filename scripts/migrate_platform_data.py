from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
# Settings load backend/.env relative to the process working directory.
# Normalise it here so migrations never fall back to development credentials.
os.chdir(ROOT / "backend")

from sqlalchemy import select  # noqa: E402

from app.auth import bootstrap_admin  # noqa: E402
from app.database import SessionLocal, initialize_database  # noqa: E402
from app.domain_models import AnalysisJob, MediaAsset, MigrationRecord, SpeciesResource, User  # noqa: E402
from app.schemas import AnalysisResponse  # noqa: E402
from app.services.species_catalog_service import get_species_catalog_service  # noqa: E402
from app.settings import get_settings  # noqa: E402


def already_migrated(db, source_type: str, source_key: str) -> bool:
    return db.scalar(select(MigrationRecord.id).where(MigrationRecord.source_type == source_type, MigrationRecord.source_key == source_key)) is not None


def migrate(dry_run: bool = False) -> dict[str, int]:
    initialize_database()
    bootstrap_admin()
    settings = get_settings()
    counts = {"species": 0, "results": 0, "assets": 0, "errors": 0, "skipped": 0}
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == settings.bootstrap_admin_username))
        if admin is None:
            raise RuntimeError("bootstrap administrator was not created")

        for entry in get_species_catalog_service().list_species():
            key = entry.species_id
            if already_migrated(db, "species", key):
                counts["skipped"] += 1
                continue
            if not dry_run:
                resource = db.get(SpeciesResource, key)
                if resource is None:
                    db.add(SpeciesResource(species_id=key, payload=entry.model_dump(mode="json")))
                else:
                    resource.payload = entry.model_dump(mode="json")
                    resource.is_deleted = False
                db.add(MigrationRecord(source_type="species", source_key=key, target_id=key))
            counts["species"] += 1

        for result_file in sorted(settings.results_dir.glob("*.json")):
            source_key = result_file.name
            if already_migrated(db, "result", source_key):
                counts["skipped"] += 1
                continue
            try:
                result = AnalysisResponse.model_validate_json(result_file.read_text(encoding="utf-8"))
                if not dry_run:
                    job = AnalysisJob(
                        owner_id=admin.id,
                        source="legacy_migration",
                        media_id=result.media_id,
                        file_name=result_file.name,
                        media_type=result.media_type,
                        status="succeeded",
                        progress=100,
                        result_json=result.model_dump(mode="json"),
                    )
                    db.add(job)
                    db.flush()
                    db.add(MigrationRecord(source_type="result", source_key=source_key, target_id=job.id))
                counts["results"] += 1
            except Exception as exc:
                counts["errors"] += 1
                if not dry_run:
                    db.add(MigrationRecord(source_type="result", source_key=source_key, status="error", error_message=str(exc)[:2000]))

        reference_root = settings.reference_species_dir
        if reference_root.exists():
            for media_path in reference_root.rglob("*"):
                if not media_path.is_file() or media_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                    continue
                source_key = media_path.relative_to(ROOT).as_posix()
                if already_migrated(db, "reference_asset", source_key):
                    counts["skipped"] += 1
                    continue
                if not dry_run:
                    asset = MediaAsset(object_key=source_key, original_name=media_path.name, media_type="reference_image", source="legacy_reference")
                    db.add(asset)
                    db.flush()
                    db.add(MigrationRecord(source_type="reference_asset", source_key=source_key, target_id=asset.id))
                counts["assets"] += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotently migrate legacy wildlife platform data.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate(dry_run=args.dry_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
