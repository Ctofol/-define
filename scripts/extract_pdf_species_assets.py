from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, ImageFont


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
DEFAULT_SPECIES_KNOWLEDGE = Path("backend") / "app" / "data" / "species_knowledge.json"


@dataclass
class ExtractedImage:
    filename: str
    page: int
    image_index: int
    width: int | None
    height: int | None
    page_text_excerpt: str
    species_hint: str
    note: str


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        from pypdf import PdfReader
    except ImportError:
        print(
            "Missing dependency: pypdf. Install backend requirements first, for example: "
            "pip install -r backend/requirements.txt",
            file=sys.stderr,
        )
        return 2

    output_dir = (args.output_dir or Path("reference_species") / "待复核" / pdf_path.stem).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(pdf_path))
    species_terms = load_species_terms(args.species_terms)
    rows: list[ExtractedImage] = []
    saved_count = 0

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = safe_page_text(page)
        species_hint = match_species_hint(page_text, species_terms)
        images = getattr(page, "images", [])
        for image_index, image_file in enumerate(images, start=1):
            raw_name = getattr(image_file, "name", "") or f"image_{image_index}"
            suffix = Path(raw_name).suffix.lower()
            if suffix not in IMAGE_SUFFIXES:
                suffix = ".jpg"

            file_name = f"{pdf_path.stem}_p{page_number:03d}_{image_index:02d}{suffix}"
            destination = output_dir / file_name
            destination.write_bytes(image_file.data)

            width, height, note = inspect_image(destination, args.min_width, args.min_height)
            if note == "too_small" and not args.keep_small:
                destination.unlink(missing_ok=True)
                continue

            rows.append(
                ExtractedImage(
                    filename=file_name,
                    page=page_number,
                    image_index=image_index,
                    width=width,
                    height=height,
                    page_text_excerpt=excerpt(page_text),
                    species_hint=species_hint,
                    note=note,
                )
            )
            saved_count += 1

    write_metadata(output_dir / "metadata.csv", rows, pdf_path)
    write_contact_sheets(output_dir / "contact_sheets", rows, output_dir)
    write_readme(output_dir / "README.md", pdf_path, saved_count)
    print(f"Extracted {saved_count} images to {output_dir}")
    print(f"Metadata: {output_dir / 'metadata.csv'}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract embedded images from a species atlas PDF into reference_species/待复核 for manual review."
    )
    parser.add_argument("pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory. Defaults to reference_species/待复核/<pdf-stem>.")
    parser.add_argument("--species-terms", type=Path, default=None, help="Optional newline-separated species names or species_knowledge.json used for page text hints.")
    parser.add_argument("--min-width", type=int, default=240, help="Skip images narrower than this unless --keep-small is set.")
    parser.add_argument("--min-height", type=int, default=180, help="Skip images shorter than this unless --keep-small is set.")
    parser.add_argument("--keep-small", action="store_true", help="Keep small icons/logos too, marking them in metadata.")
    return parser.parse_args()


def load_species_terms(path: Path | None) -> list[str]:
    if path and path.exists():
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                terms = [str(item.get("cn_name", "")).strip() for item in data if isinstance(item, dict)]
                terms = [term for term in terms if term]
                if terms:
                    return terms
            except Exception:
                pass
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if DEFAULT_SPECIES_KNOWLEDGE.exists():
        try:
            data = json.loads(DEFAULT_SPECIES_KNOWLEDGE.read_text(encoding="utf-8"))
            terms = [str(item.get("cn_name", "")).strip() for item in data if isinstance(item, dict)]
            terms = [term for term in terms if term]
            if terms:
                return terms
        except Exception:
            pass
    defaults = [
        "猕猴",
        "豹猫",
        "赤狐",
        "野猪",
        "梅花鹿",
        "水鹿",
        "中华斑羚",
        "黑熊",
        "亚洲黑熊",
        "黄喉貂",
        "大灵猫",
        "白头叶猴",
        "中华穿山甲",
    ]
    return defaults


def safe_page_text(page) -> str:
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def match_species_hint(page_text: str, species_terms: list[str]) -> str:
    matches: list[tuple[int, str]] = []
    for term in species_terms:
        if not term:
            continue
        position = page_text.find(term)
        if position >= 0:
            matches.append((position, term))
    if not matches:
        return "待复核"
    ordered_terms = [term for _, term in sorted(matches)]
    return ";".join(dict.fromkeys(ordered_terms))


def excerpt(text: str, max_chars: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:max_chars]


def inspect_image(path: Path, min_width: int, min_height: int) -> tuple[int | None, int | None, str]:
    try:
        with Image.open(path) as image:
            width, height = image.size
            image.verify()
    except Exception:
        return None, None, "unverified_image"

    if width < min_width or height < min_height:
        return width, height, "too_small"
    return width, height, "pending_manual_review"


def write_metadata(metadata_path: Path, rows: list[ExtractedImage], source_pdf: Path) -> None:
    with metadata_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "filename",
                "source_pdf",
                "page",
                "image_index",
                "width",
                "height",
                "species_hint",
                "review_status",
                "page_text_excerpt",
                "note",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.filename,
                    str(source_pdf),
                    row.page,
                    row.image_index,
                    row.width or "",
                    row.height or "",
                    row.species_hint,
                    "pending",
                    row.page_text_excerpt,
                    row.note,
                ]
            )


def write_readme(readme_path: Path, source_pdf: Path, saved_count: int) -> None:
    readme_path.write_text(
        "\n".join(
            [
                "# PDF 待复核图片",
                "",
                f"来源 PDF：`{source_pdf}`",
                f"提取图片数：{saved_count}",
                "",
                "这些图片尚未进入正式样本库。请人工确认物种、授权、画面质量后，再复制到对应 `reference_species/<物种>/` 目录。",
                "",
                "建议复核顺序：",
                "1. 删除图标、地图、局部痕迹、严重模糊或主体过小图片。",
                "2. 确认 `species_hint` 是否正确。",
                "3. 将可用图片重命名为 `物种_来源_序号.ext`。",
                "4. 更新正式目录里的 `metadata.csv`。",
            ]
        ),
        encoding="utf-8",
    )


def write_contact_sheets(sheet_dir: Path, rows: list[ExtractedImage], image_dir: Path) -> None:
    if not rows:
        return
    sheet_dir.mkdir(parents=True, exist_ok=True)
    thumb_w, thumb_h = 180, 150
    cols = 6
    per_sheet = cols * 8
    font = ImageFont.load_default()
    for sheet_index, start in enumerate(range(0, len(rows), per_sheet), start=1):
        chunk = rows[start : start + per_sheet]
        sheet_rows = (len(chunk) + cols - 1) // cols
        canvas = Image.new("RGB", (cols * thumb_w, sheet_rows * thumb_h), "white")
        draw = ImageDraw.Draw(canvas)
        for idx, row in enumerate(chunk):
            col = idx % cols
            row_index = idx // cols
            x0 = col * thumb_w
            y0 = row_index * thumb_h
            img_path = image_dir / row.filename
            try:
                with Image.open(img_path) as src:
                    thumb = ImageOps.fit(src.convert("RGB"), (thumb_w - 8, thumb_h - 28), method=Image.Resampling.LANCZOS)
            except Exception:
                thumb = Image.new("RGB", (thumb_w - 8, thumb_h - 28), "#dddddd")
            canvas.paste(thumb, (x0 + 4, y0 + 4))
            label = f"p{row.page:03d}-{row.image_index:02d} {row.width or ''}x{row.height or ''} {row.species_hint}"
            draw.text((x0 + 4, y0 + thumb_h - 20), label[:34], fill="black", font=font)
        canvas.save(sheet_dir / f"contact_sheet_{sheet_index:02d}.png")


if __name__ == "__main__":
    raise SystemExit(main())
