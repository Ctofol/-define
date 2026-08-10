from __future__ import annotations

import csv
import hashlib
from pathlib import Path


BASE_MANIFEST = Path("storage") / "training" / "species_manifest.csv"
VIVERRID_CANDIDATES = Path("docs") / "viverrid_source_verification" / "model_training_candidates.csv"
OUTPUT = Path("storage") / "training" / "species_manifest_v14_viverrid.csv"
DUPLICATES_OUTPUT = Path("storage") / "training" / "species_manifest_v14_viverrid_duplicates.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    base_rows = [row for row in read_csv(BASE_MANIFEST) if row.get("file_path") and row.get("label")]
    candidate_rows = [
        row
        for row in read_csv(VIVERRID_CANDIDATES)
        if row.get("species") == "大灵猫" and row.get("promotion_gate", "").startswith("ready_model_training")
    ]

    output_rows = list(base_rows)
    duplicate_rows: list[dict[str, str]] = []
    seen_hashes = {row.get("sha256", ""): row.get("relative_path", "") for row in base_rows if row.get("sha256")}
    existing_paths = {Path(row["file_path"]).resolve() for row in base_rows}

    for candidate in candidate_rows:
        path = Path(candidate["copied_path"]).resolve()
        if not path.exists():
            raise FileNotFoundError(f"missing candidate image: {path}")
        sha256 = file_sha256(path)
        relative_path = str(path.relative_to(Path.cwd()).as_posix()) if path.is_relative_to(Path.cwd()) else str(path)
        if path in existing_paths or sha256 in seen_hashes:
            duplicate_rows.append(
                {
                    "file_path": str(path),
                    "relative_path": relative_path,
                    "label": "大灵猫",
                    "duplicate_of": seen_hashes.get(sha256, ""),
                    "sha256": sha256,
                }
            )
            continue
        seen_hashes[sha256] = relative_path
        output_rows.append(
            {
                "file_path": str(path),
                "folder_name": "viverrids_quality_pass/大灵猫",
                "label": "大灵猫",
                "split": "train",
                "relative_path": relative_path,
                "review_status": candidate.get("promotion_gate", ""),
                "sha256": sha256,
            }
        )

    fieldnames = ["file_path", "folder_name", "label", "split", "relative_path", "review_status", "sha256"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in output_rows)

    with DUPLICATES_OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["file_path", "relative_path", "label", "duplicate_of", "sha256"])
        writer.writeheader()
        writer.writerows(duplicate_rows)

    print(f"base_rows={len(base_rows)}")
    print(f"candidate_rows={len(candidate_rows)}")
    print(f"added_rows={len(output_rows) - len(base_rows)}")
    print(f"duplicates={len(duplicate_rows)}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
