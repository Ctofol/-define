from __future__ import annotations

import argparse
import csv
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


DEFAULT_SOURCE_DIR = Path("reference_species") / "pdf_guangxi_species_images_v2"
DEFAULT_OUTPUT_DIR = Path("docs") / "pdf_weak_reference_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render review batches for Guangxi PDF weak reference crops.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--thumb-width", type=int, default=220)
    parser.add_argument("--thumb-height", type=int, default=170)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata_path = args.source_dir / "metadata.csv"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata not found: {metadata_path}")

    rows = read_metadata(metadata_path, args.source_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_review_status(args.output_dir / "review_status.csv", rows)

    index_rows: list[dict[str, str]] = []
    for batch_number, start in enumerate(range(0, len(rows), args.batch_size), start=1):
        batch_rows = rows[start : start + args.batch_size]
        batch_id = f"batch_{batch_number:02d}"
        batch_csv = args.output_dir / f"{batch_id}.csv"
        batch_sheet = args.output_dir / f"{batch_id}_sheet.jpg"

        for local_index, row in enumerate(batch_rows, start=1):
            row["batch"] = batch_id
            row["item"] = str(local_index)

        write_batch_csv(batch_csv, batch_rows)
        render_sheet(batch_sheet, batch_rows, args)
        index_rows.append(
            {
                "batch": batch_id,
                "items": str(len(batch_rows)),
                "first_global_id": batch_rows[0]["global_id"],
                "last_global_id": batch_rows[-1]["global_id"],
                "csv": str(batch_csv),
                "sheet": str(batch_sheet),
            }
        )

    write_index(args.output_dir / "index.csv", index_rows)
    write_readme(args.output_dir / "README.md", args.source_dir, args.batch_size, len(rows), len(index_rows))
    print(f"Rendered {len(index_rows)} PDF weak-reference review batches for {len(rows)} images")
    print(f"Output: {args.output_dir}")
    return 0


def read_metadata(metadata_path: Path, source_dir: Path) -> list[dict[str, str]]:
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as file:
        raw_rows = list(csv.DictReader(file))

    rows: list[dict[str, str]] = []
    for index, row in enumerate(raw_rows, start=1):
        filename = row["filename"]
        image_path = (source_dir / "crops" / filename).resolve()
        rows.append(
            {
                "global_id": str(index),
                "batch": "",
                "item": "",
                "species_id": row.get("species_id", ""),
                "cn_name": row.get("cn_name", ""),
                "latin_name": row.get("latin_name", ""),
                "category": row.get("category", ""),
                "taxon_group": row.get("taxon_group", ""),
                "protection_level": row.get("protection_level", ""),
                "source_page": row.get("source_page", ""),
                "filename": filename,
                "image_path": str(image_path),
                "current_status": "pending_pdf_review",
                "your_decision": "",
                "reason": "",
            }
        )
    return rows


def write_review_status(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "global_id",
        "species_id",
        "cn_name",
        "latin_name",
        "filename",
        "status",
        "reason",
        "source_page",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "global_id": row["global_id"],
                    "species_id": row["species_id"],
                    "cn_name": row["cn_name"],
                    "latin_name": row["latin_name"],
                    "filename": row["filename"],
                    "status": "pending_pdf_review",
                    "reason": "",
                    "source_page": row["source_page"],
                }
            )


def write_batch_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "global_id",
        "batch",
        "item",
        "cn_name",
        "latin_name",
        "taxon_group",
        "protection_level",
        "source_page",
        "filename",
        "image_path",
        "current_status",
        "your_decision",
        "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{key: row.get(key, "") for key in fieldnames} for row in rows])


def write_index(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["batch", "items", "first_global_id", "last_global_id", "csv", "sheet"])
        writer.writeheader()
        writer.writerows(rows)


def render_sheet(output_path: Path, rows: list[dict[str, str]], args: argparse.Namespace) -> None:
    columns = max(1, args.columns)
    thumb_w = args.thumb_width
    thumb_h = args.thumb_height
    label_h = 82
    title_h = 42
    grid_rows = math.ceil(len(rows) / columns)
    width = columns * thumb_w
    height = title_h + grid_rows * (thumb_h + label_h) + 12

    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(13)
    small_font = load_font(11)
    batch_id = rows[0]["batch"] if rows else output_path.stem
    draw.text((10, 10), f"{batch_id} PDF weak reference review", fill=(0, 0, 0), font=title_font)

    for index, row in enumerate(rows):
        col = index % columns
        grid_row = index // columns
        x = col * thumb_w
        y = title_h + grid_row * (thumb_h + label_h)
        draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h + label_h - 1), outline=(225, 225, 225))
        try:
            with Image.open(row["image_path"]) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((thumb_w - 12, thumb_h - 10))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 5))
        except Exception as exc:  # noqa: BLE001
            draw.rectangle((x + 8, y + 8, x + thumb_w - 8, y + thumb_h - 8), outline=(170, 0, 0), width=2)
            draw.text((x + 12, y + 40), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(150, 0, 0), font=label_font)

        label_y = y + thumb_h + 4
        label_lines = [
            f"#{row['item']} / G{row['global_id']} p{row['source_page']} {row['cn_name']}",
            row["latin_name"],
            f"{row['taxon_group']} {row['protection_level']}",
        ]
        for line_index, line in enumerate(label_lines):
            font = label_font if line_index == 0 else small_font
            for wrapped in wrap_text(line, width=28 if line_index == 0 else 36, max_lines=1):
                draw.text((x + 6, label_y), wrapped, fill=(0, 0, 0), font=font)
                label_y += 17 if line_index == 0 else 14

    sheet.save(output_path, quality=92)


def wrap_text(value: str, width: int, max_lines: int) -> list[str]:
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


def write_readme(path: Path, source_dir: Path, batch_size: int, image_count: int, batch_count: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# PDF 弱参考图复核队列",
                "",
                f"来源目录: `{source_dir}`",
                f"图片数: {image_count}",
                f"批次数: {batch_count}",
                f"每批数量: {batch_size}",
                "",
                "回复时请说明批次，例如:",
                "",
                "```text",
                "batch_01: 3, 7, 12 不行，其他可以",
                "```",
                "",
                "建议状态:",
                "",
                "- `approved`: 主体清晰，物种基本对应，可升级为正式参考图候选",
                "- `reference_only`: 可作弱参考，不建议进正式训练集",
                "- `reject`: 非活体、不清晰、主体太小、裁剪错误或物种明显不对",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
