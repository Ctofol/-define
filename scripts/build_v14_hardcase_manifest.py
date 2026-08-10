from __future__ import annotations

import csv
import hashlib
from pathlib import Path


BASE_MANIFEST = Path("storage") / "training" / "species_manifest.csv"
HARDCASE_ROOT = Path("reference_species") / "_supplement_candidates" / "大灵猫"
OUTPUT = Path("storage") / "training" / "species_manifest_v14_hardcase.csv"


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
    rows = [row for row in read_csv(BASE_MANIFEST) if row.get("file_path") and row.get("label")]
    seen_hashes = {row.get("sha256", "") for row in rows if row.get("sha256")}
    added = 0

    for image_path in sorted(HARDCASE_ROOT.glob("*.jpg")):
        resolved_image_path = image_path.resolve()
        sha256 = file_sha256(image_path)
        if sha256 in seen_hashes:
            continue
        rows.append(
            {
                "file_path": str(resolved_image_path),
                "folder_name": "_supplement_candidates/大灵猫",
                "label": "大灵猫",
                "split": "train",
                "relative_path": str(resolved_image_path.relative_to(Path.cwd()).as_posix()),
                "review_status": "hard_case_confirmed_candidate",
                "sha256": sha256,
            }
        )
        seen_hashes.add(sha256)
        added += 1

    fieldnames = ["file_path", "folder_name", "label", "split", "relative_path", "review_status", "sha256"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)

    print(f"base_rows={len(rows) - added}")
    print(f"hardcase_added={added}")
    print(f"output_rows={len(rows)}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
