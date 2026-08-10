from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a contact sheet for classifier validation errors.")
    parser.add_argument("--eval-json", type=Path, default=Path("storage") / "training" / "local_v3_eval.json")
    parser.add_argument("--output", type=Path, default=Path("docs") / "local_v3_error_contact_sheet.jpg")
    parser.add_argument("--only-wrong", action="store_true", default=True)
    parser.add_argument("--thumb-width", type=int, default=260)
    parser.add_argument("--thumb-height", type=int, default=190)
    parser.add_argument("--columns", type=int, default=3)
    return parser.parse_args()


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    font_path = next((path for path in candidates if path.exists()), None)
    return ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default()


def resolve_file_path(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path

    file_name = path.name
    matches = list(Path("reference_species").rglob(file_name))
    if matches:
        return matches[0]
    return path


def main() -> int:
    args = parse_args()
    report = json.loads(args.eval_json.read_text(encoding="utf-8"))
    records = report.get("records", [])
    rows = [row for row in records if not row.get("correct")] if args.only_wrong else records
    rows.sort(key=lambda row: (row.get("correct", False), -float(row.get("confidence", 0))))

    columns = max(1, args.columns)
    thumb_w = args.thumb_width
    thumb_h = args.thumb_height
    label_h = 96
    title_h = 54
    padding = 14
    row_count = (len(rows) + columns - 1) // columns
    width = columns * (thumb_w + padding) + padding
    height = title_h + row_count * (thumb_h + label_h + padding) + padding

    sheet = Image.new("RGB", (width, max(height, title_h + padding)), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(14)

    title = f"{args.eval_json.name} validation errors: {len(rows)}"
    draw.text((padding, 14), title, fill=(20, 20, 20), font=title_font)

    for index, row in enumerate(rows):
        col = index % columns
        line = index // columns
        x = padding + col * (thumb_w + padding)
        y = title_h + line * (thumb_h + label_h + padding)
        image_path = resolve_file_path(str(row.get("file_path", "")))

        try:
            with Image.open(image_path) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((thumb_w, thumb_h))
                background = Image.new("RGB", (thumb_w, thumb_h), (244, 246, 242))
                background.paste(image, ((thumb_w - image.width) // 2, (thumb_h - image.height) // 2))
                sheet.paste(background, (x, y))
        except Exception as exc:  # noqa: BLE001
            draw.rectangle((x, y, x + thumb_w, y + thumb_h), fill=(245, 230, 230), outline=(180, 60, 60))
            draw.text((x + 8, y + 20), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0), font=label_font)

        draw.rectangle((x, y, x + thumb_w, y + thumb_h), outline=(96, 73, 60), width=2)
        confidence = round(float(row.get("confidence", 0)) * 100)
        lines = [
            f"#{index + 1} {image_path.name}",
            f"true: {row.get('label', '')}",
            f"pred: {row.get('predicted_label', '')} ({confidence}%)",
        ]
        for line_index, text in enumerate(lines):
            draw.text((x + 5, y + thumb_h + 6 + line_index * 22), text, fill=(20, 20, 20), font=label_font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=92)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
