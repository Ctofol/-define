from __future__ import annotations

import argparse
import tarfile
from pathlib import Path


REQUIRED_PATHS = [
    Path("backend") / "app",
    Path("backend") / "requirements.txt",
    Path("backend") / "requirements-models.txt",
]


def add_path(archive: tarfile.TarFile, root: Path, relative: Path) -> None:
    source = root / relative
    if source.is_dir():
        archive.add(source, arcname=relative.as_posix(), recursive=True)
    else:
        archive.add(source, arcname=relative.as_posix(), recursive=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="backend-code-formal-latest.tar.gz")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    for relative in REQUIRED_PATHS:
        source = root / relative
        if not source.exists():
            raise SystemExit(f"Required backend code path is missing: {source}")

    if output.exists():
        output.unlink()

    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for relative in REQUIRED_PATHS:
            add_path(archive, root, relative)

    print(f"Backend code release written: {output}")
    print(f"Size: {output.stat().st_size}")


if __name__ == "__main__":
    main()
