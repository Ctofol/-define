from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat


DEFAULT_PAIRS = [
    ("梅花鹿", "水鹿"),
    ("野猪", "黑熊"),
    ("猕猴", "白头叶猴"),
    ("中华斑羚", "水鹿"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render audit sheets for high-risk confusion pairs.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest_v15_reviewed_supplement.csv")
    parser.add_argument("--eval-json", type=Path, default=Path("storage") / "training" / "hybrid_recognition_v14_classifier_v15_retrieval_eval.json")
    parser.add_argument("--output-dir", type=Path, default=Path("docs") / "confusion_pair_audit")
    parser.add_argument("--thumb-width", type=int, default=220)
    parser.add_argument("--thumb-height", type=int, default=168)
    parser.add_argument("--columns", type=int, default=4)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("file_path") and row.get("label")]


def load_eval_records(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    records: dict[str, dict[str, object]] = {}
    for row in report.get("records", []):
        file_name = Path(str(row.get("file_path", ""))).name
        if file_name:
            records[file_name] = row
    return records


def load_font(size: int) -> ImageFont.ImageFont:
    for path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simsun.ttc")]:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def image_quality(path: Path) -> tuple[dict[str, float], list[str]]:
    flags: list[str] = []
    try:
        with Image.open(path) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
            width, height = image.size
            gray = image.convert("L")
            brightness = ImageStat.Stat(gray).mean[0]
            edge_mean = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
            min_side = min(width, height)
    except Exception:
        return {"width": 0, "height": 0, "brightness": 0, "edge_mean": 0, "min_side": 0}, ["image_error"]

    if min_side < 260:
        flags.append("small_image")
    if brightness < 35:
        flags.append("very_dark")
    if brightness > 230:
        flags.append("overexposed")
    if edge_mean < 4:
        flags.append("low_detail")
    return {
        "width": float(width),
        "height": float(height),
        "brightness": round(float(brightness), 2),
        "edge_mean": round(float(edge_mean), 2),
        "min_side": float(min_side),
    }, flags


def source_flags(row: dict[str, str]) -> list[str]:
    text = " ".join([row.get("file_path", ""), row.get("folder_name", ""), row.get("relative_path", ""), row.get("review_status", "")]).lower()
    flags: list[str] = []
    if "gbif" in text:
        flags.append("gbif")
    if "pdf" in text or "口袋书" in text:
        flags.append("pdf")
    if "supplement" in text or "_supplement_candidates" in text:
        flags.append("supplement")
    if row.get("split") == "val":
        flags.append("validation")
    return flags


def audit_rows(rows: list[dict[str, str]], eval_records: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    audited: list[dict[str, object]] = []
    for row in rows:
        path = Path(row["file_path"])
        metrics, flags = image_quality(path)
        flags.extend(source_flags(row))
        eval_row = eval_records.get(path.name)
        predicted = ""
        if eval_row:
            predicted = str(eval_row.get("strategies", {}).get("hybrid_tuned_override", eval_row.get("classifier_label", "")))
            if predicted and predicted != row["label"]:
                flags.append("hybrid_error")
            if eval_row.get("classifier_label") and eval_row.get("classifier_label") != row["label"]:
                flags.append("classifier_error")
        risk_score = sum(
            {
                "hybrid_error": 4,
                "classifier_error": 3,
                "low_detail": 2,
                "small_image": 2,
                "very_dark": 1,
                "overexposed": 1,
                "supplement": 1,
            }.get(flag, 0)
            for flag in flags
        )
        audited.append(
            {
                **row,
                **metrics,
                "predicted": predicted,
                "flags": "|".join(dict.fromkeys(flags)),
                "risk_score": risk_score,
            }
        )
    return sorted(audited, key=lambda item: (-int(item["risk_score"]), str(item["label"]), str(item["file_path"])))


def render_sheet(pair_name: str, rows: list[dict[str, object]], output_path: Path, args: argparse.Namespace) -> None:
    columns = max(1, args.columns)
    thumb_w = args.thumb_width
    thumb_h = args.thumb_height
    label_h = 112
    title_h = 54
    pad = 12
    grid_rows = (len(rows) + columns - 1) // columns
    width = columns * (thumb_w + pad) + pad
    height = max(title_h + grid_rows * (thumb_h + label_h + pad) + pad, title_h + pad)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(13)
    draw.text((pad, 14), f"{pair_name} confusion audit ({len(rows)} images)", fill=(20, 20, 20), font=title_font)

    for index, row in enumerate(rows):
        path = Path(str(row["file_path"]))
        col = index % columns
        grid_row = index // columns
        x = pad + col * (thumb_w + pad)
        y = title_h + grid_row * (thumb_h + label_h + pad)
        try:
            with Image.open(path) as raw:
                image = ImageOps.exif_transpose(raw).convert("RGB")
                image.thumbnail((thumb_w, thumb_h))
                background = Image.new("RGB", (thumb_w, thumb_h), (243, 247, 244))
                background.paste(image, ((thumb_w - image.width) // 2, (thumb_h - image.height) // 2))
                sheet.paste(background, (x, y))
        except Exception as exc:
            draw.rectangle((x, y, x + thumb_w, y + thumb_h), fill=(245, 230, 230), outline=(160, 0, 0))
            draw.text((x + 8, y + 20), f"IMAGE ERROR: {exc.__class__.__name__}", fill=(160, 0, 0), font=label_font)

        risk = int(row["risk_score"])
        outline = (185, 60, 40) if risk >= 4 else (190, 145, 55) if risk >= 2 else (90, 120, 92)
        draw.rectangle((x, y, x + thumb_w, y + thumb_h), outline=outline, width=3)
        lines = [
            f"#{index + 1} {path.name[:28]}",
            f"{row['label']} / {row.get('split', '')} / risk {risk}",
            f"pred: {row.get('predicted') or '-'}",
            f"{int(float(row['width']))}x{int(float(row['height']))} b{row['brightness']} e{row['edge_mean']}",
            str(row.get("flags", "-"))[:36],
        ]
        for line_index, text in enumerate(lines):
            draw.text((x + 4, y + thumb_h + 6 + line_index * 20), text, fill=(20, 20, 20), font=label_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "label",
        "split",
        "file_path",
        "relative_path",
        "review_status",
        "predicted",
        "risk_score",
        "flags",
        "width",
        "height",
        "brightness",
        "edge_mean",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_summary(path: Path, pair_rows: dict[str, list[dict[str, object]]]) -> None:
    lines = ["# 混淆对样本审计", ""]
    for pair_name, rows in pair_rows.items():
        by_label: dict[str, int] = defaultdict(int)
        flagged = 0
        high_risk = 0
        for row in rows:
            by_label[str(row["label"])] += 1
            if row.get("flags"):
                flagged += 1
            if int(row["risk_score"]) >= 4:
                high_risk += 1
        lines.extend(
            [
                f"## {pair_name}",
                "",
                f"- 图片数：{len(rows)}",
                f"- 高风险：{high_risk}",
                f"- 有标记：{flagged}",
                f"- 类别分布：{', '.join(f'{label} {count}' for label, count in sorted(by_label.items()))}",
                f"- 联系表：`docs/confusion_pair_audit/{pair_name}.jpg`",
                f"- 明细表：`docs/confusion_pair_audit/{pair_name}.csv`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    rows = read_manifest(args.manifest)
    eval_records = load_eval_records(args.eval_json)
    pair_rows: dict[str, list[dict[str, object]]] = {}

    for left, right in DEFAULT_PAIRS:
        pair_name = f"{left}_vs_{right}"
        labels = {left, right}
        selected = [row for row in rows if row["label"] in labels]
        audited = audit_rows(selected, eval_records)
        pair_rows[pair_name] = audited
        write_csv(args.output_dir / f"{pair_name}.csv", audited)
        render_sheet(pair_name, audited, args.output_dir / f"{pair_name}.jpg", args)

    write_summary(args.output_dir / "summary.md", pair_rows)
    print(f"wrote confusion audit to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
