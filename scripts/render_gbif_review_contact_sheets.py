from __future__ import annotations

import argparse
import csv
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render visual contact sheets for GBIF candidate review.")
    parser.add_argument("--root", type=Path, default=Path("reference_species") / "待复核" / "gbif")
    parser.add_argument("--output-dir", type=Path, default=Path("docs") / "gbif_review_contact_sheets")
    parser.add_argument("--species", nargs="*", default=None)
    parser.add_argument("--thumb-width", type=int, default=260)
    parser.add_argument("--thumb-height", type=int, default=190)
    parser.add_argument("--columns", type=int, default=3)
    return parser.parse_args()


def read_review_status(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    rows: dict[tuple[str, str], dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            species = row.get("species", "")
            filename = row.get("filename", "")
            if species and filename:
                rows[(species, filename)] = row
    return rows


def wrap_text(text: str, width: int = 34, max_lines: int = 3) -> list[str]:
    wrapped = textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=False)
    return wrapped[:max_lines] if wrapped else [""]


def load_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ):
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def render_species_sheet(folder: Path, output_path: Path, status_rows: dict[tuple[str, str], dict[str, str]], args: argparse.Namespace) -> None:
    images = [path for path in sorted(folder.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
    if not images:
        return

    columns = max(1, args.columns)
    thumb_w = args.thumb_width
    thumb_h = args.thumb_height
    label_h = 74
    title_h = 34
    rows = (len(images) + columns - 1) // columns
    width = columns * thumb_w
    height = title_h + rows * (thumb_h + label_h) + 12
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(16)
    label_font = load_font(12)
    draw.text((8, 8), f"{folder.name} GBIF candidates", fill=(0, 0, 0), font=title_font)

    for index, image_path in enumerate(images):
        col = index % columns
        row = index // columns
        x = col * thumb_w
        y = title_h + row * (thumb_h + label_h)
        try:
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                image.thumbnail((thumb_w - 8, thumb_h - 8))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 4))
        except Exception as exc:  # noqa: BLE001
            draw.text((x + 8, y + 30), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0))

        status = status_rows.get((folder.name, image_path.name), {})
        status_text = status.get("status", "unreviewed")
        reason = status.get("reason", "")
        label_lines = [image_path.name, f"status: {status_text}", *wrap_text(reason)]
        for line_index, line in enumerate(label_lines[:5]):
            fill = (160, 0, 0) if status_text == "reject" and line_index == 1 else (0, 0, 0)
            draw.text((x + 4, y + thumb_h + 2 + line_index * 13), line, fill=fill, font=label_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)


def main() -> int:
    args = parse_args()
    requested = set(args.species) if args.species else None
    status_rows = read_review_status(args.root / "review_status.csv")
    folders = [folder for folder in sorted(args.root.iterdir()) if folder.is_dir()] if args.root.exists() else []
    rendered = 0
    for folder in folders:
        if requested and folder.name not in requested:
            continue
        render_species_sheet(folder, args.output_dir / f"{folder.name}.jpg", status_rows, args)
        rendered += 1
    print(f"rendered {rendered} contact sheets to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
