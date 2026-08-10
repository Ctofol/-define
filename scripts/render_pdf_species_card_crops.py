from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PDF = Path("docs/source_pdfs/0719_guangxi_protected_wildlife_pocketbook.pdf")
DEFAULT_CATALOG = Path("backend/app/data/pdf_species_catalog.json")
DEFAULT_OUTPUT_DIR = Path("reference_species/pdf_guangxi_species_cards")


@dataclass
class SpeciesCard:
    species_id: str
    cn_name: str
    latin_name: str
    category: str
    taxon_group: str
    protection_level: str
    source_page: int
    crop_path: Path
    bbox_pdf: tuple[float, float, float, float]
    bbox_px: tuple[int, int, int, int]
    match_status: str
    crop_mode: str


def main() -> int:
    args = parse_args()
    ensure_bundled_site_packages()
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    catalog = load_catalog(args.catalog)
    if not catalog:
        raise SystemExit(f"No catalog entries loaded from {args.catalog}")
    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    crop_dir = args.output_dir / "crops"
    sheet_dir = args.output_dir / "contact_sheets"
    crop_dir.mkdir(parents=True, exist_ok=True)
    sheet_dir.mkdir(parents=True, exist_ok=True)

    render_cache: dict[int, Image.Image] = {}
    page_sizes = get_page_sizes(args.pdf)
    latin_boxes = locate_latin_boxes(args.pdf, catalog)
    page_image_boxes = locate_page_image_boxes(args.pdf)

    cards: list[SpeciesCard] = []
    for item in catalog:
        page_number = int(item["source_page"])
        page_image = render_cache.get(page_number)
        if page_image is None:
            page_image = render_page(args.pdf, page_number, args.dpi)
            render_cache[page_number] = page_image

        page_width, page_height = page_sizes[page_number]
        latin_box = latin_boxes.get(item["latin_name"])
        embedded_image_box = (
            select_embedded_image_box(latin_box, page_image_boxes.get(page_number, []))
            if args.crop_mode == "image" and latin_box
            else None
        )
        if embedded_image_box:
            match_status = "embedded_image_matched"
            bbox_pdf = embedded_image_box
        else:
            match_status = "latin_text_matched" if latin_box else "page_grid_fallback"
            bbox_pdf = crop_bbox_for_item(item, latin_box, page_width, page_height, args.crop_mode)
        bbox_px = pdf_bbox_to_pixels(bbox_pdf, page_width, page_height, page_image.size)
        crop = page_image.crop(bbox_px)

        crop_name = f"p{page_number:03d}_{safe_filename(item['species_id'])}_{safe_filename(item['cn_name'])}.jpg"
        crop_path = crop_dir / crop_name
        crop.save(crop_path, quality=92)
        cards.append(
            SpeciesCard(
                species_id=item["species_id"],
                cn_name=item["cn_name"],
                latin_name=item["latin_name"],
                category=item["category"],
                taxon_group=item["taxon_group"],
                protection_level=item["protection_level"],
                source_page=page_number,
                crop_path=crop_path,
                bbox_pdf=bbox_pdf,
                bbox_px=bbox_px,
                match_status=match_status,
                crop_mode=args.crop_mode,
            )
        )

    write_metadata(args.output_dir / "metadata.csv", cards, args.pdf)
    write_manifest(args.output_dir / "weak_reference_manifest.csv", cards)
    write_contact_sheets(sheet_dir, cards, Image, ImageDraw, ImageFont, ImageOps)
    write_readme(args.output_dir / "README.md", args.pdf, args.catalog, cards)
    print(f"Rendered {len(cards)} species {args.crop_mode} crops to {crop_dir}")
    print(f"Metadata: {args.output_dir / 'metadata.csv'}")
    print(f"Weak reference manifest: {args.output_dir / 'weak_reference_manifest.csv'}")
    print(f"Contact sheets: {sheet_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render species card crops from the Guangxi protected wildlife PDF.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--crop-mode", choices=["card", "image"], default="card")
    return parser.parse_args()


def ensure_bundled_site_packages() -> None:
    bundled_site_packages = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "python"
        / "Lib"
        / "site-packages"
    )
    if bundled_site_packages.exists() and str(bundled_site_packages) not in sys.path:
        sys.path.append(str(bundled_site_packages))


def load_catalog(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return [item for item in data if item.get("latin_name") and item.get("source_page")]


def get_page_sizes(pdf_path: Path) -> dict[int, tuple[float, float]]:
    import pdfplumber

    sizes: dict[int, tuple[float, float]] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            sizes[index] = (float(page.width), float(page.height))
    return sizes


def locate_latin_boxes(pdf_path: Path, catalog: list[dict[str, object]]) -> dict[str, tuple[float, float, float, float]]:
    import pdfplumber

    by_page: dict[int, list[dict[str, object]]] = {}
    for item in catalog:
        by_page.setdefault(int(item["source_page"]), []).append(item)

    boxes: dict[str, tuple[float, float, float, float]] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, entries in by_page.items():
            words = pdf.pages[page_number - 1].extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
            for item in entries:
                latin = str(item["latin_name"])
                latin_tokens = latin.split()
                match = find_latin_word_box(words, latin_tokens)
                if match:
                    boxes[latin] = match
    return boxes


def locate_page_image_boxes(pdf_path: Path) -> dict[int, list[tuple[float, float, float, float]]]:
    import pdfplumber

    boxes: dict[int, list[tuple[float, float, float, float]]] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            candidates: list[tuple[float, float, float, float]] = []
            for image in page.images:
                left = float(image["x0"])
                right = float(image["x1"])
                top = float(image["top"])
                bottom = float(image["bottom"])
                width = right - left
                height = bottom - top
                # Exclude page headers, page-number decorations and rules.
                if width < 55.0 or height < 50.0:
                    continue
                if width > float(page.width) * 0.9:
                    continue
                candidates.append((left, top, right, bottom))
            boxes[page_number] = candidates
    return boxes


def select_embedded_image_box(
    latin_box: tuple[float, float, float, float],
    image_boxes: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float] | None:
    latin_left, latin_top, latin_right, _ = latin_box
    latin_center = (latin_left + latin_right) / 2
    ranked: list[tuple[float, tuple[float, float, float, float]]] = []
    for image_box in image_boxes:
        left, _, right, bottom = image_box
        vertical_gap = latin_top - bottom
        if vertical_gap < -4.0 or vertical_gap > 90.0:
            continue
        image_center = (left + right) / 2
        center_gap = abs(image_center - latin_center)
        image_width = right - left
        if center_gap > max(65.0, image_width * 0.7):
            continue
        score = vertical_gap * 1.4 + center_gap
        ranked.append((score, image_box))
    return min(ranked, key=lambda item: item[0])[1] if ranked else None


def find_latin_word_box(words: list[dict[str, object]], latin_tokens: list[str]) -> tuple[float, float, float, float] | None:
    if not latin_tokens:
        return None
    normalized_tokens = [normalize_latin_token(token) for token in latin_tokens]
    word_tokens = [normalize_latin_token(str(word["text"])) for word in words]
    for index, token in enumerate(word_tokens):
        if token != normalized_tokens[0]:
            continue
        end = index + len(normalized_tokens)
        if word_tokens[index:end] != normalized_tokens:
            continue
        matched_words = words[index:end]
        return (
            min(float(word["x0"]) for word in matched_words),
            min(float(word["top"]) for word in matched_words),
            max(float(word["x1"]) for word in matched_words),
            max(float(word["bottom"]) for word in matched_words),
        )
    return None


def normalize_latin_token(value: str) -> str:
    return re.sub(r"[^A-Za-z-]", "", value).lower()


def crop_bbox_for_item(
    item: dict[str, object],
    latin_box: tuple[float, float, float, float] | None,
    page_width: float,
    page_height: float,
    crop_mode: str,
) -> tuple[float, float, float, float]:
    entries_on_page = int(item.get("_entries_on_page", 0) or 0)
    if latin_box:
        x0, top, x1, bottom = latin_box
        center_x = (x0 + x1) / 2
        col_left, col_right = column_bounds(center_x, page_width)
        if crop_mode == "image":
            # Keep the full photo frame above the Latin-name line.  The former
            # 102pt offset started inside taller portrait photos and could cut
            # off heads (for example Haliaeetus leucogaster).
            crop_top = max(55.0, top - 125.0)
            crop_bottom = min(page_height - 18.0, max(crop_top + 60.0, top - 20.0))
        else:
            crop_top = max(55.0, top - 112.0)
            crop_bottom = min(page_height - 18.0, bottom + 12.0)
        return (col_left, crop_top, col_right, crop_bottom)

    page_index = int(item.get("_page_index", 0))
    col = page_index % 3
    row = page_index // 3
    col_left, col_right = column_bounds((col + 0.5) * page_width / 3, page_width)
    row_top = 70.0 + row * 120.0
    return (col_left, row_top, col_right, min(page_height - 18.0, row_top + 126.0 + entries_on_page * 0))


def column_bounds(center_x: float, page_width: float) -> tuple[float, float]:
    third = page_width / 3
    col = min(2, max(0, int(center_x / third)))
    bounds = [
        (22.0, 146.0),
        (146.0, 270.0),
        (270.0, 396.0),
    ]
    left, right = bounds[col]
    return max(0.0, left), min(page_width, right)


def pdf_bbox_to_pixels(
    bbox: tuple[float, float, float, float],
    page_width: float,
    page_height: float,
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x0, top, x1, bottom = bbox
    image_width, image_height = image_size
    sx = image_width / page_width
    sy = image_height / page_height
    return (
        max(0, int(round(x0 * sx))),
        max(0, int(round(top * sy))),
        min(image_width, int(round(x1 * sx))),
        min(image_height, int(round(bottom * sy))),
    )


def render_page(pdf_path: Path, page_number: int, dpi: int):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[page_number - 1]
    scale = dpi / 72
    bitmap = page.render(scale=scale)
    return bitmap.to_pil().convert("RGB")


def safe_filename(value: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_")
    return safe or "unknown"


def write_metadata(path: Path, cards: list[SpeciesCard], source_pdf: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "filename",
                "species_id",
                "cn_name",
                "latin_name",
                "category",
                "taxon_group",
                "protection_level",
                "source_pdf",
                "source_page",
                "match_status",
                "crop_mode",
                "bbox_pdf",
                "bbox_px",
                "review_status",
                "note",
            ]
        )
        for card in cards:
            writer.writerow(
                [
                    card.crop_path.name,
                    card.species_id,
                    card.cn_name,
                    card.latin_name,
                    card.category,
                    card.taxon_group,
                    card.protection_level,
                    str(source_pdf),
                    card.source_page,
                    card.match_status,
                    card.crop_mode,
                    " ".join(f"{value:.2f}" for value in card.bbox_pdf),
                    " ".join(str(value) for value in card.bbox_px),
                    "pending",
                    "PDF page-rendered species card crop; verify image quality and species before training use.",
                ]
            )


def write_manifest(path: Path, cards: list[SpeciesCard]) -> None:
    fieldnames = ["file_path", "folder_name", "label", "split", "relative_path", "review_status", "sha256"]
    root = path.parent
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for card in cards:
            writer.writerow(
                {
                    "file_path": str(card.crop_path.resolve()),
                    "folder_name": "pdf_guangxi_species_images",
                    "label": card.cn_name,
                    "split": "reference",
                    "relative_path": card.crop_path.relative_to(root).as_posix(),
                    "review_status": "pending_pdf_review",
                    "sha256": file_sha256(card.crop_path),
                }
            )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_contact_sheets(sheet_dir: Path, cards: list[SpeciesCard], Image, ImageDraw, ImageFont, ImageOps) -> None:
    thumb_w, thumb_h = 210, 190
    cols = 5
    per_sheet = cols * 6
    font = ImageFont.load_default()
    for sheet_index, start in enumerate(range(0, len(cards), per_sheet), start=1):
        chunk = cards[start : start + per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        canvas = Image.new("RGB", (cols * thumb_w, rows * thumb_h), "white")
        draw = ImageDraw.Draw(canvas)
        for idx, card in enumerate(chunk):
            col = idx % cols
            row = idx // cols
            x0 = col * thumb_w
            y0 = row * thumb_h
            with Image.open(card.crop_path) as src:
                thumb = ImageOps.contain(src.convert("RGB"), (thumb_w - 10, thumb_h - 42))
            canvas.paste(thumb, (x0 + 5, y0 + 5))
            label = f"{start + idx + 1:03d} p{card.source_page:03d} {card.cn_name}"
            draw.text((x0 + 5, y0 + thumb_h - 32), label[:28], fill="black", font=font)
            draw.text((x0 + 5, y0 + thumb_h - 18), card.latin_name[:30], fill="black", font=font)
        canvas.save(sheet_dir / f"contact_sheet_{sheet_index:02d}.jpg", quality=92)


def write_readme(path: Path, pdf_path: Path, catalog_path: Path, cards: list[SpeciesCard]) -> None:
    matched = sum(1 for card in cards if card.match_status == "latin_text_matched")
    path.write_text(
        "\n".join(
            [
                "# 广西保护野生动物 PDF 物种卡片裁剪",
                "",
                f"来源 PDF: `{pdf_path}`",
                f"来源目录: `{catalog_path}`",
                f"物种卡片数: {len(cards)}",
                f"拉丁学名定位成功: {matched}",
                "",
                "这些裁剪图来自页面渲染，包含图像主体和下方物种文字，适合先做快速复核或构建弱监督参考图库。",
                "进入正式训练集前，仍需确认主体清晰、物种对应正确、且使用授权符合项目要求。",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
