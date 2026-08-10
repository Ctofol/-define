from __future__ import annotations

import csv
import math
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REVIEW_STATUS = Path("reference_species") / "待复核" / "gbif" / "review_status.csv"
USER_DECISIONS = Path("docs") / "viverrid_user_quality_review" / "user_quality_decisions.csv"
GBIF_ROOT = Path("reference_species") / "待复核" / "gbif"
OUTPUT_DIR = Path("reference_species") / "_supplement_candidates" / "viverrids_quality_pass"
DOCS_DIR = Path("docs") / "viverrid_quality_pass_candidates"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ):
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def training_priority(row: dict[str, str]) -> str:
    country = row.get("country", "")
    license_value = row.get("license", "").lower()
    if "creativecommons.org" not in license_value:
        return "hold_license_check"
    if country == "China":
        return "high_local_source"
    if country in {"Chinese Taipei", "Lao People’s Democratic Republic", "Myanmar", "Viet Nam", "Thailand"}:
        return "medium_regional_supplement"
    return "low_out_of_region"


def load_metadata() -> dict[tuple[str, str], dict[str, str]]:
    metadata: dict[tuple[str, str], dict[str, str]] = {}
    for metadata_csv in GBIF_ROOT.glob("*/metadata.csv"):
        for row in read_csv(metadata_csv):
            key = (row.get("species", ""), row.get("filename", ""))
            if all(key):
                metadata[key] = row
    return metadata


def copy_candidates(rows: list[dict[str, str]]) -> None:
    for row in rows:
        source = Path(row["image_path"])
        target_dir = OUTPUT_DIR / row["species"]
        target_dir.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(source, target_dir / source.name)


def write_manifest(rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "species",
        "filename",
        "scientific_name",
        "training_priority",
        "status",
        "reason",
        "country",
        "locality",
        "license_allowed",
        "license",
        "source_url",
        "image_path",
        "copied_path",
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = OUTPUT_DIR / "manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            copied_path = OUTPUT_DIR / row["species"] / row["filename"]
            writer.writerow({field: row.get(field, "") for field in fieldnames} | {"copied_path": str(copied_path)})


def wrap(value: str, width: int) -> list[str]:
    return textwrap.wrap(value, width=width, break_long_words=False) or [""]


def render_sheet(rows: list[dict[str, str]]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    columns = 4
    thumb_w = 270
    thumb_h = 200
    label_h = 104
    title_h = 74
    grid_rows = math.ceil(len(rows) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, title_h + grid_rows * (thumb_h + label_h) + 10), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(12)
    small_font = load_font(11)
    draw.text((10, 8), "Viverrid quality-pass candidates", fill=(0, 0, 0), font=title_font)
    draw.text((10, 34), "User checked image quality only; species/source verification is the next gate.", fill=(70, 70, 70), font=label_font)

    colors = {
        "high_local_source": (70, 145, 90),
        "medium_regional_supplement": (205, 145, 55),
        "low_out_of_region": (170, 120, 120),
        "hold_license_check": (160, 80, 80),
    }
    for index, row in enumerate(rows, start=1):
        col = (index - 1) % columns
        grid_row = (index - 1) // columns
        x = col * thumb_w
        y = title_h + grid_row * (thumb_h + label_h)
        outline = colors.get(row["training_priority"], (120, 120, 120))
        draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h + label_h - 1), outline=outline, width=2)
        try:
            with Image.open(row["image_path"]) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((thumb_w - 12, thumb_h - 8))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 4))
        except Exception as exc:  # noqa: BLE001
            draw.text((x + 8, y + 30), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0), font=label_font)

        label_y = y + thumb_h + 4
        lines = [
            f"#{index} {row['species']} / {row.get('scientific_name', '')}",
            row["training_priority"],
            f"{row.get('country', '')} {row.get('locality', '')}".strip(),
            row.get("source_url", ""),
        ]
        for line_index, line in enumerate(lines):
            font = label_font if line_index == 0 else small_font
            for wrapped in wrap(line, 34)[:2 if line_index == 3 else 1]:
                draw.text((x + 6, label_y), wrapped, fill=(0, 0, 0), font=font)
                label_y += 16

    sheet.save(DOCS_DIR / "quality_pass_sheet.jpg", quality=92)


def write_report(rows: list[dict[str, str]]) -> None:
    by_species: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for row in rows:
        by_species[row["species"]] = by_species.get(row["species"], 0) + 1
        by_priority[row["training_priority"]] = by_priority.get(row["training_priority"], 0) + 1

    lines = [
        "# 灵猫类质量通过候选",
        "",
        f"候选数量: {len(rows)}",
        "",
        "## 按物种",
        *[f"- {name}: {count}" for name, count in sorted(by_species.items())],
        "",
        "## 按训练优先级",
        *[f"- {name}: {count}" for name, count in sorted(by_priority.items())],
        "",
        "## 使用原则",
        "",
        "- 这些图只完成了画面质量审核，不代表物种已经由人工确认。",
        "- `high_local_source` 可优先进入物种/来源复核。",
        "- `medium_regional_supplement` 适合做外形补充或混淆抑制，进入正式训练前要保留地区偏差标记。",
        "- `hold_license_check` 不进入训练，除非许可证核验通过。",
    ]
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    metadata = load_metadata()
    status_rows = {
        (row["species"], row["filename"]): row
        for row in read_csv(REVIEW_STATUS)
        if row.get("status") == "quality_pass_candidate"
    }
    decision_rows = {
        (row["species"], row["filename"]): row
        for row in read_csv(USER_DECISIONS)
        if row.get("user_quality_decision") == "usable"
    }

    rows: list[dict[str, str]] = []
    for key, status_row in sorted(status_rows.items()):
        decision_row = decision_rows.get(key, {})
        row = metadata.get(key, {}) | status_row | decision_row
        row["training_priority"] = training_priority(row)
        rows.append(row)

    copy_candidates(rows)
    write_manifest(rows)
    render_sheet(rows)
    write_report(rows)

    print(f"exported {len(rows)} quality-pass candidates")
    print(f"manifest={OUTPUT_DIR / 'manifest.csv'}")
    print(f"sheet={DOCS_DIR / 'quality_pass_sheet.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
