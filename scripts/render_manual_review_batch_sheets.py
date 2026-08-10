from __future__ import annotations

import argparse
import csv
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render contact sheets for manual GBIF review batches.")
    parser.add_argument("--batch-dir", type=Path, default=Path("docs") / "manual_review_batches")
    parser.add_argument("--thumb-width", type=int, default=300)
    parser.add_argument("--thumb-height", type=int, default=220)
    parser.add_argument("--columns", type=int, default=4)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def wrap_text(value: str, width: int = 32, max_lines: int = 2) -> list[str]:
    lines = textwrap.wrap(value, width=width, break_long_words=False, replace_whitespace=False)
    return lines[:max_lines] if lines else [""]


def load_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ):
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def render_batch_sheet(csv_path: Path, output_path: Path, rows: list[dict[str, str]], args: argparse.Namespace) -> None:
    columns = max(1, args.columns)
    thumb_w = args.thumb_width
    thumb_h = args.thumb_height
    label_h = 86
    title_h = 36
    grid_rows = (len(rows) + columns - 1) // columns
    width = columns * thumb_w
    height = title_h + grid_rows * (thumb_h + label_h) + 12

    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(16)
    label_font = load_font(12)
    draw.text((8, 9), f"{csv_path.stem} manual review", fill=(0, 0, 0), font=title_font)

    for index, row in enumerate(rows):
        col = index % columns
        grid_row = index // columns
        x = col * thumb_w
        y = title_h + grid_row * (thumb_h + label_h)
        image_path = Path(row["image_path"])
        try:
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                image.thumbnail((thumb_w - 10, thumb_h - 10))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 5))
        except Exception as exc:  # noqa: BLE001
            draw.rectangle((x + 6, y + 6, x + thumb_w - 6, y + thumb_h - 6), outline=(180, 0, 0), width=2)
            draw.text((x + 10, y + 36), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0))

        label_lines = [
            f"#{row.get('item', '')} {row.get('species', '')}",
            row.get("filename", ""),
            f"status: {row.get('current_status', '')}",
            *wrap_text(row.get("country", "")),
        ]
        for line_index, line in enumerate(label_lines[:6]):
            draw.text((x + 5, y + thumb_h + 4 + line_index * 14), line, fill=(0, 0, 0), font=label_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)


def main() -> int:
    args = parse_args()
    rendered = 0
    for csv_path in sorted(args.batch_dir.glob("batch_*.csv")):
        rows = read_csv(csv_path)
        if not rows:
            continue
        output_path = csv_path.with_name(f"{csv_path.stem}_sheet.jpg")
        render_batch_sheet(csv_path, output_path, rows, args)
        rendered += 1
    print(f"rendered {rendered} batch sheets in {args.batch_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
