from __future__ import annotations

import csv
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat


SOURCE_DIR = Path("reference_species") / "pdf_guangxi_species_images_v2"
OUTPUT_DIR = Path("docs") / "pdf_weak_reference_quality_audit"
QUALITY_FLAGS_PATH = SOURCE_DIR / "quality_flags.csv"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class AuditItem:
    filename: str
    cn_name: str
    latin_name: str
    source_page: str
    image_path: Path
    width: int
    height: int
    score: int
    reasons: list[str]


def is_near_white(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red >= 246 and green >= 246 and blue >= 246


def is_pdf_rule_color(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red >= 145 and 55 <= green <= 190 and blue <= 130 and red >= green + 20


def audit_image(path: Path, row: dict[str, str]) -> AuditItem | None:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        pixels = image.load()

        total = width * height
        white_ratio = sum(1 for y in range(height) for x in range(width) if is_near_white(pixels[x, y])) / total
        top_rows = min(12, height)
        top_residue = 0.0
        if top_rows:
            top_residue = sum(
                1
                for y in range(top_rows)
                for x in range(width)
                if is_near_white(pixels[x, y]) or is_pdf_rule_color(pixels[x, y])
            ) / (width * top_rows)
        edge_sample = build_edge_sample(image)
        edge_white = sum(1 for pixel in edge_sample if is_near_white(pixel)) / max(1, len(edge_sample))
        detail = max(ImageStat.Stat(image.convert("L")).stddev)

    reasons: list[str] = []
    score = 0
    aspect = width / max(1, height)
    if width < 130 or height < 120:
        score += 3
        reasons.append("too_small")
    if aspect < 0.55 or aspect > 2.4:
        score += 2
        reasons.append("odd_aspect")
    if white_ratio > 0.22:
        score += 3
        reasons.append("large_white_area")
    if edge_white > 0.35:
        score += 2
        reasons.append("white_edge")
    if top_residue > 0.38:
        score += 2
        reasons.append("top_residue")
    if detail < 22:
        score += 1
        reasons.append("low_detail")

    if score < 2:
        return None
    return AuditItem(
        filename=row["filename"],
        cn_name=row.get("cn_name", ""),
        latin_name=row.get("latin_name", ""),
        source_page=row.get("source_page", ""),
        image_path=path,
        width=width,
        height=height,
        score=score,
        reasons=reasons,
    )


def build_edge_sample(image: Image.Image) -> list[tuple[int, int, int]]:
    width, height = image.size
    pixels = image.load()
    margin_x = max(1, min(10, width // 12))
    margin_y = max(1, min(10, height // 12))
    sample: list[tuple[int, int, int]] = []
    for y in range(height):
        for x in range(margin_x):
            sample.append(pixels[x, y])
            sample.append(pixels[width - 1 - x, y])
    for x in range(width):
        for y in range(margin_y):
            sample.append(pixels[x, y])
            sample.append(pixels[x, height - 1 - y])
    return sample


def read_metadata() -> list[dict[str, str]]:
    metadata_path = SOURCE_DIR / "metadata.csv"
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def render_sheet(path: Path, items: list[AuditItem]) -> None:
    columns = 5
    thumb_w = 230
    thumb_h = 172
    label_h = 92
    title_h = 46
    rows = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, title_h + rows * (thumb_h + label_h) + 12), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(13)
    small_font = load_font(11)
    draw.text((10, 12), f"PDF weak reference quality audit: {len(items)} suspicious images", fill=(0, 0, 0), font=title_font)

    for index, item in enumerate(items):
        col = index % columns
        row = index // columns
        x = col * thumb_w
        y = title_h + row * (thumb_h + label_h)
        draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h + label_h - 1), outline=(220, 220, 220))
        with Image.open(item.image_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((thumb_w - 12, thumb_h - 10))
            sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 5))

        label_y = y + thumb_h + 5
        lines = [
            f"#{index + 1} score {item.score} p{item.source_page} {item.cn_name}",
            item.latin_name,
            f"{item.width}x{item.height} {'/'.join(item.reasons)}",
        ]
        for line_index, line in enumerate(lines):
            font = label_font if line_index == 0 else small_font
            for wrapped in wrap_text(line, 30 if line_index == 0 else 38, 1):
                draw.text((x + 6, label_y), wrapped, fill=(0, 0, 0), font=font)
                label_y += 18 if line_index == 0 else 15

    sheet.save(path, quality=92)


def write_csv(path: Path, items: list[AuditItem]) -> None:
    fieldnames = ["rank", "score", "reasons", "cn_name", "latin_name", "source_page", "width", "height", "filename", "image_path"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for rank, item in enumerate(items, start=1):
            writer.writerow(
                {
                    "rank": rank,
                    "score": item.score,
                    "reasons": ";".join(item.reasons),
                    "cn_name": item.cn_name,
                    "latin_name": item.latin_name,
                    "source_page": item.source_page,
                    "width": item.width,
                    "height": item.height,
                    "filename": item.filename,
                    "image_path": str(item.image_path),
                }
            )


def write_quality_flags(path: Path, rows: list[dict[str, str]], suspicious_items: list[AuditItem]) -> None:
    indexed = {item.filename: item for item in suspicious_items}
    fieldnames = ["filename", "cn_name", "latin_name", "quality_status", "score", "reasons", "note"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = indexed.get(row["filename"])
            if item:
                writer.writerow(
                    {
                        "filename": row["filename"],
                        "cn_name": row.get("cn_name", ""),
                        "latin_name": row.get("latin_name", ""),
                        "quality_status": "needs_review",
                        "score": item.score,
                        "reasons": ";".join(item.reasons),
                        "note": "自动质检发现截图边缘、文字残留、白边或裁剪质量问题，前台图鉴暂不展示。",
                    }
                )
            else:
                writer.writerow(
                    {
                        "filename": row["filename"],
                        "cn_name": row.get("cn_name", ""),
                        "latin_name": row.get("latin_name", ""),
                        "quality_status": "display",
                        "score": 0,
                        "reasons": "",
                        "note": "",
                    }
                )


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


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_metadata()
    items: list[AuditItem] = []
    for row in rows:
        path = SOURCE_DIR / "crops" / row["filename"]
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            item = audit_image(path, row)
            if item:
                items.append(item)

    items.sort(key=lambda item: (-item.score, item.cn_name, item.filename))
    write_csv(OUTPUT_DIR / "suspicious_images.csv", items)
    write_quality_flags(QUALITY_FLAGS_PATH, rows, items)
    render_sheet(OUTPUT_DIR / "suspicious_images_sheet.jpg", items[:80])
    print(f"suspicious={len(items)}")
    print(f"csv={OUTPUT_DIR / 'suspicious_images.csv'}")
    print(f"flags={QUALITY_FLAGS_PATH}")
    print(f"sheet={OUTPUT_DIR / 'suspicious_images_sheet.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
