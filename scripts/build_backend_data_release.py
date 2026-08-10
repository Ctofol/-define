from __future__ import annotations

import argparse
import tarfile
from pathlib import Path


REQUIRED_PATHS = [
    Path("reference_species") / "pdf_guangxi_species_images_v2" / "crops",
    Path("reference_species") / "pdf_guangxi_species_images_v2" / "metadata.csv",
    Path("reference_species") / "pdf_guangxi_species_images_v2" / "quality_flags.csv",
    Path("reference_species") / "pdf_guangxi_species_images_v2" / "weak_reference_manifest.csv",
    Path("reference_species") / "豹猫",
    Path("reference_species") / "大灵猫",
    Path("reference_species") / "野猪",
    Path("reference_species") / "黑熊",
    Path("reference_species") / "梅花鹿",
    Path("reference_species") / "水鹿",
    Path("reference_species") / "中华斑羚",
    Path("reference_species") / "_supplement_candidates",
    Path("storage") / "training" / "species_manifest_v20_round5_cleaned.csv",
    Path("docs") / "viverrid_source_verification" / "knowledge_open_set_candidates.csv",
]


def add_path(archive: tarfile.TarFile, source: Path, arcname: Path) -> None:
    if source.is_dir():
        archive.add(source, arcname=arcname.as_posix(), recursive=True)
    else:
        archive.add(source, arcname=arcname.as_posix(), recursive=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="backend-data-formal-latest.tar.gz")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    for relative in REQUIRED_PATHS:
        source = root / relative
        if not source.exists():
            raise SystemExit(f"Required backend data path is missing: {source}")

    if output.exists():
        output.unlink()

    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for relative in REQUIRED_PATHS:
            add_path(archive, root / relative, relative)

    print(f"Backend data release written: {output}")
    print(f"Size: {output.stat().st_size}")


if __name__ == "__main__":
    main()
