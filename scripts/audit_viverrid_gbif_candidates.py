from __future__ import annotations

import csv
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat


TARGET_SPECIES = ["大灵猫", "大斑灵猫", "小灵猫", "缟灵猫", "熊狸", "果子狸"]
REVIEW_ROOT = Path("reference_species") / "待复核" / "gbif"
OUTPUT_DIR = Path("docs") / "viverrid_gbif_quality_audit"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
BAD_METADATA_KEYWORDS = {
    "cage",
    "caged",
    "captive",
    "dead",
    "enclosure",
    "museum",
    "roadkill",
    "specimen",
    "taxidermy",
    "zoo",
    "动物园",
    "标本",
    "圈养",
}


@dataclass
class CandidateAudit:
    species: str
    filename: str
    path: Path
    width: int
    height: int
    detail: float
    score: int
    status: str
    reasons: list[str]
    source_url: str
    license: str
    country: str
    locality: str


def read_metadata(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {row.get("filename", ""): row for row in csv.DictReader(file) if row.get("filename")}


def is_near_blank(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return (red >= 246 and green >= 246 and blue >= 246) or (red <= 8 and green <= 8 and blue <= 8)


def edge_blank_ratio(image: Image.Image) -> float:
    width, height = image.size
    pixels = image.load()
    margin_x = max(1, min(16, width // 12))
    margin_y = max(1, min(16, height // 12))
    sample: list[tuple[int, int, int]] = []
    for y in range(height):
        for x in range(margin_x):
            sample.append(pixels[x, y])
            sample.append(pixels[width - 1 - x, y])
    for x in range(width):
        for y in range(margin_y):
            sample.append(pixels[x, y])
            sample.append(pixels[x, height - 1 - y])
    return sum(1 for pixel in sample if is_near_blank(pixel)) / max(1, len(sample))


def metadata_text(row: dict[str, str]) -> str:
    return " ".join(
        row.get(key, "")
        for key in ["basis_of_record", "media_title", "media_description", "locality", "note"]
    ).lower()


def audit_image(species: str, path: Path, metadata: dict[str, str]) -> CandidateAudit:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        detail = max(ImageStat.Stat(image.convert("L")).stddev)
        blank_edge = edge_blank_ratio(image)

    reasons: list[str] = []
    score = 0
    aspect = width / max(1, height)

    if width >= 800 and height >= 500:
        score += 2
    elif width >= 500 and height >= 350:
        score += 1
    else:
        score -= 3
        reasons.append("small_image")

    if 0.55 <= aspect <= 2.1:
        score += 1
    else:
        score -= 2
        reasons.append("odd_aspect")

    if detail >= 34:
        score += 1
    elif detail < 18:
        score -= 2
        reasons.append("low_detail")

    if blank_edge > 0.3:
        score -= 1
        reasons.append("large_blank_edge")

    text = metadata_text(metadata)
    matched_bad_keywords = [keyword for keyword in BAD_METADATA_KEYWORDS if keyword in text]
    if matched_bad_keywords:
        score -= 4
        reasons.append(f"metadata:{'/'.join(sorted(matched_bad_keywords)[:3])}")

    basis = metadata.get("basis_of_record", "").upper()
    if basis and basis not in {"HUMAN_OBSERVATION", "MACHINE_OBSERVATION", "OCCURRENCE"}:
        score -= 2
        reasons.append(f"basis:{basis}")

    if score >= 3:
        status = "priority_review"
    elif score >= 1:
        status = "review_needed"
    else:
        status = "deprioritize"

    return CandidateAudit(
        species=species,
        filename=path.name,
        path=path,
        width=width,
        height=height,
        detail=round(detail, 1),
        score=score,
        status=status,
        reasons=reasons or ["quality_ok"],
        source_url=metadata.get("source_url", ""),
        license=metadata.get("license", ""),
        country=metadata.get("country", ""),
        locality=metadata.get("locality", ""),
    )


def collect_audits() -> list[CandidateAudit]:
    audits: list[CandidateAudit] = []
    for species in TARGET_SPECIES:
        folder = REVIEW_ROOT / species
        if not folder.is_dir():
            continue
        metadata = read_metadata(folder / "metadata.csv")
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                audits.append(audit_image(species, path, metadata.get(path.name, {})))
    audits.sort(key=lambda item: (item.status != "priority_review", item.species, -item.score, item.filename))
    return audits


def write_csv(path: Path, audits: list[CandidateAudit]) -> None:
    fieldnames = [
        "species",
        "filename",
        "status",
        "score",
        "reasons",
        "width",
        "height",
        "detail",
        "country",
        "locality",
        "license",
        "source_url",
        "image_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in audits:
            writer.writerow(
                {
                    "species": item.species,
                    "filename": item.filename,
                    "status": item.status,
                    "score": item.score,
                    "reasons": ";".join(item.reasons),
                    "width": item.width,
                    "height": item.height,
                    "detail": item.detail,
                    "country": item.country,
                    "locality": item.locality,
                    "license": item.license,
                    "source_url": item.source_url,
                    "image_path": str(item.path),
                }
            )


def render_sheet(path: Path, audits: list[CandidateAudit]) -> None:
    columns = 4
    thumb_w = 270
    thumb_h = 200
    label_h = 94
    title_h = 44
    rows = math.ceil(len(audits) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, title_h + rows * (thumb_h + label_h) + 12), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(12)
    draw.text((10, 10), f"Viverrid GBIF quality audit: {len(audits)} candidates", fill=(0, 0, 0), font=title_font)

    for index, item in enumerate(audits):
        col = index % columns
        row = index // columns
        x = col * thumb_w
        y = title_h + row * (thumb_h + label_h)
        outline = (130, 170, 145) if item.status == "priority_review" else (220, 170, 120) if item.status == "review_needed" else (180, 80, 80)
        draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h + label_h - 1), outline=outline, width=2)
        try:
            with Image.open(item.path) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((thumb_w - 12, thumb_h - 10))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 5))
        except Exception as exc:  # noqa: BLE001
            draw.text((x + 8, y + 30), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0), font=label_font)

        lines = [
            f"#{index + 1} {item.species} {item.status} score {item.score}",
            item.filename,
            f"{item.width}x{item.height} detail {item.detail}",
            "/".join(item.reasons),
        ]
        label_y = y + thumb_h + 4
        for line in lines:
            for wrapped in wrap_text(line, 36, 1):
                draw.text((x + 6, label_y), wrapped, fill=(0, 0, 0), font=label_font)
                label_y += 15

    sheet.save(path, quality=92)


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
    audits = collect_audits()
    write_csv(OUTPUT_DIR / "viverrid_gbif_quality_audit.csv", audits)
    render_sheet(OUTPUT_DIR / "viverrid_gbif_quality_sheet.jpg", audits)
    counts: dict[str, int] = {}
    for item in audits:
        counts[item.status] = counts.get(item.status, 0) + 1
    print(f"audited={len(audits)} {counts}")
    print(f"csv={OUTPUT_DIR / 'viverrid_gbif_quality_audit.csv'}")
    print(f"sheet={OUTPUT_DIR / 'viverrid_gbif_quality_sheet.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
