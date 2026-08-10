from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render contact sheets for formal training images.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest.csv")
    parser.add_argument("--output-dir", type=Path, default=Path("docs") / "training_contact_sheets")
    parser.add_argument("--species", nargs="*", default=None)
    parser.add_argument("--thumb-width", type=int, default=260)
    parser.add_argument("--thumb-height", type=int, default=190)
    parser.add_argument("--columns", type=int, default=3)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("file_path") and row.get("label")]


def render_sheet(label: str, rows: list[dict[str, str]], output_path: Path, args: argparse.Namespace) -> None:
    columns = max(1, args.columns)
    thumb_w = args.thumb_width
    thumb_h = args.thumb_height
    label_h = 70
    title_h = 36
    grid_rows = (len(rows) + columns - 1) // columns
    width = columns * thumb_w
    height = title_h + grid_rows * (thumb_h + label_h) + 12
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 8), f"{label} formal training images ({len(rows)})", fill=(0, 0, 0))

    for index, row in enumerate(rows):
        image_path = Path(row["file_path"])
        col = index % columns
        grid_row = index // columns
        x = col * thumb_w
        y = title_h + grid_row * (thumb_h + label_h)
        try:
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                image.thumbnail((thumb_w - 8, thumb_h - 8))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 4))
        except Exception as exc:  # noqa: BLE001
            draw.text((x + 8, y + 30), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0))

        relative_path = row.get("relative_path", image_path.name)
        split = row.get("split", "train")
        folder = row.get("folder_name", "")
        label_lines = [Path(relative_path).name[:34], f"split: {split}", f"folder: {folder[:28]}"]
        for line_index, line in enumerate(label_lines):
            draw.text((x + 4, y + thumb_h + 2 + line_index * 14), line, fill=(0, 0, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)


def main() -> int:
    args = parse_args()
    requested = set(args.species) if args.species else None
    rows_by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_manifest(args.manifest):
        if requested and row["label"] not in requested:
            continue
        rows_by_label[row["label"]].append(row)

    for label, rows in sorted(rows_by_label.items()):
        render_sheet(label, rows, args.output_dir / f"{label}.jpg", args)

    print(f"rendered {len(rows_by_label)} training contact sheets to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
