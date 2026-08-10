from __future__ import annotations

import csv
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


AUDIT_CSV = Path("docs") / "viverrid_gbif_quality_audit" / "viverrid_gbif_quality_audit.csv"
OUTPUT_DIR = Path("docs") / "viverrid_user_quality_review"


def read_rows() -> list[dict[str, str]]:
    with AUDIT_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    rows.sort(key=lambda row: (row.get("status") != "priority_review", row.get("species", ""), -int(row.get("score", "0")), row.get("filename", "")))
    for index, row in enumerate(rows, start=1):
        row["global_id"] = str(index)
    return rows


def load_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ):
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def wrap_text(value: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(value, width=width, break_long_words=False, replace_whitespace=False)
    return lines[:max_lines] if lines else [""]


def render_sheet(path: Path, rows: list[dict[str, str]], batch_id: str) -> None:
    columns = 4
    thumb_w = 270
    thumb_h = 205
    label_h = 88
    title_h = 58
    grid_rows = math.ceil(len(rows) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, title_h + grid_rows * (thumb_h + label_h) + 12), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(12)
    small_font = load_font(11)
    draw.text((10, 8), f"{batch_id} image quality review", fill=(0, 0, 0), font=title_font)
    draw.text((10, 32), "只判断画面质量：主体清晰/遮挡/模糊/非活体或圈养/截图问题；不需要判断物种是否正确。", fill=(70, 70, 70), font=label_font)

    for index, row in enumerate(rows):
        col = index % columns
        grid_row = index // columns
        x = col * thumb_w
        y = title_h + grid_row * (thumb_h + label_h)
        outline = (135, 175, 145) if row.get("status") == "priority_review" else (220, 165, 105)
        draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h + label_h - 1), outline=outline, width=2)
        try:
            with Image.open(row["image_path"]) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((thumb_w - 12, thumb_h - 10))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 5))
        except Exception as exc:  # noqa: BLE001
            draw.text((x + 8, y + 28), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0), font=label_font)

        label_y = y + thumb_h + 4
        lines = [
            f"#{row['item']} / G{row['global_id']} {row['species']}",
            f"{row['status']} score {row['score']} {row['width']}x{row['height']}",
            row.get("reasons", ""),
        ]
        for line_index, line in enumerate(lines):
            font = label_font if line_index == 0 else small_font
            for wrapped in wrap_text(line, 34, 1):
                draw.text((x + 6, label_y), wrapped, fill=(0, 0, 0), font=font)
                label_y += 16

    sheet.save(path, quality=92)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "global_id",
        "batch",
        "item",
        "species",
        "filename",
        "auto_status",
        "auto_reasons",
        "user_quality_decision",
        "user_reason",
        "image_path",
        "source_url",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "global_id": row["global_id"],
                    "batch": row["batch"],
                    "item": row["item"],
                    "species": row["species"],
                    "filename": row["filename"],
                    "auto_status": row["status"],
                    "auto_reasons": row["reasons"],
                    "user_quality_decision": "",
                    "user_reason": "",
                    "image_path": row["image_path"],
                    "source_url": row["source_url"],
                }
            )


def write_index(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["batch", "items", "first_global_id", "last_global_id", "csv", "sheet"])
        writer.writeheader()
        writer.writerows(rows)


def write_readme(path: Path, total: int, batches: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# 灵猫科/熊狸类候选图质量复核",
                "",
                f"候选图数量: {total}",
                f"批次数: {batches}",
                "",
                "你只需要判断图片质量，不需要判断物种是否正确。",
                "",
                "推荐回复格式：",
                "",
                "```text",
                "batch_01: 1,3,8 可以；2 遮挡；5 模糊；7 非活体/圈养；其他可以",
                "```",
                "",
                "质量标签建议：",
                "",
                "- `usable`: 主体清楚、活体、遮挡少，可进入下一步物种/来源校验",
                "- `occluded`: 遮挡明显",
                "- `blurry`: 模糊或分辨率不足",
                "- `not_live`: 标本、尸体、非活体",
                "- `captive`: 圈养/动物园/笼舍/人工场景明显",
                "- `bad_crop`: 主体太小、截图边框、裁剪不完整",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    rows = read_rows()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    batch_size = 16
    index_rows: list[dict[str, str]] = []
    for batch_number, start in enumerate(range(0, len(rows), batch_size), start=1):
        batch = rows[start : start + batch_size]
        batch_id = f"batch_{batch_number:02d}"
        for item, row in enumerate(batch, start=1):
            row["batch"] = batch_id
            row["item"] = str(item)
        csv_path = OUTPUT_DIR / f"{batch_id}.csv"
        sheet_path = OUTPUT_DIR / f"{batch_id}_sheet.jpg"
        write_csv(csv_path, batch)
        render_sheet(sheet_path, batch, batch_id)
        index_rows.append(
            {
                "batch": batch_id,
                "items": str(len(batch)),
                "first_global_id": batch[0]["global_id"],
                "last_global_id": batch[-1]["global_id"],
                "csv": str(csv_path),
                "sheet": str(sheet_path),
            }
        )
    write_index(OUTPUT_DIR / "index.csv", index_rows)
    write_readme(OUTPUT_DIR / "README.md", len(rows), len(index_rows))
    print(f"rendered {len(index_rows)} quality review batches for {len(rows)} images")
    print(f"output={OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
