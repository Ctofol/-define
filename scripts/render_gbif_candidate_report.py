from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a markdown report for GBIF candidate images.")
    parser.add_argument("--root", type=Path, default=Path("reference_species") / "待复核" / "gbif")
    parser.add_argument("--output", type=Path, default=Path("docs") / "gbif_candidate_report.md")
    return parser.parse_args()


def read_metadata(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_review_status(path: Path) -> dict[str, Counter[str]]:
    if not path.exists():
        return {}
    status_by_species: dict[str, Counter[str]] = defaultdict(Counter)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            species = row.get("species", "")
            status = row.get("status", "unreviewed")
            if species:
                status_by_species[species][status] += 1
    return status_by_species


def read_review_reasons(path: Path) -> dict[str, Counter[str]]:
    if not path.exists():
        return {}
    reasons_by_species: dict[str, Counter[str]] = defaultdict(Counter)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            species = row.get("species", "")
            reason = row.get("reason", "")
            if species and reason:
                reasons_by_species[species][reason] += 1
    return reasons_by_species


def main() -> int:
    args = parse_args()
    folders = sorted([path for path in args.root.iterdir() if path.is_dir()]) if args.root.exists() else []
    review_status = read_review_status(args.root / "review_status.csv")
    review_reasons = read_review_reasons(args.root / "review_status.csv")

    lines = [
        "# GBIF 候选图片报告",
        "",
        "这些图片位于待复核区，不会自动进入正式训练集。复核通过后再复制到对应正式物种目录。",
        "",
        "| 物种 | 图片数 | 已复核状态 | 授权风险 | 元数据行 | 国家/地区 | 授权 |",
        "| --- | ---: | --- | --- | ---: | --- | --- |",
    ]

    for folder in folders:
        images = [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
        metadata = read_metadata(folder / "metadata.csv")
        countries = Counter(row.get("country", "") or "unknown" for row in metadata)
        licenses = Counter(row.get("license", "") or "unknown" for row in metadata)
        statuses = review_status.get(folder.name, Counter())
        reasons = review_reasons.get(folder.name, Counter())
        country_summary = "；".join(f"{name} x{count}" for name, count in countries.most_common(4))
        license_summary = "；".join(f"{name} x{count}" for name, count in licenses.most_common(4))
        status_summary = "；".join(f"{name} x{count}" for name, count in statuses.most_common()) or "unreviewed"
        license_risk = f"license_not_allowed x{reasons['license_not_allowed']}" if reasons.get("license_not_allowed") else "-"
        lines.append(
            f"| {folder.name} | {len(images)} | {status_summary} | {license_risk} | "
            f"{len(metadata)} | {country_summary} | {license_summary} |"
        )

    lines.extend(
        [
            "",
            "## 复核规则",
            "",
            "- 主体清晰、物种无明显争议，再进入正式训练目录。",
            "- 没有清楚活体主体的图一律不入训；洞穴、足迹、粪便、尸体、标本、圈养和城市庭院图只可作参考或拒绝。",
            "- `CC BY-NC` 图片只作为内部训练/复核候选，不作为公开商业素材。",
            "- 同一作者、同一地点、同一角度的重复图要控制数量，避免模型学到拍摄背景。",
            "- 与广西及周边场景差异过大的动物园、圈养或摆拍图，应降级为参考，不优先训练。",
        ]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote GBIF candidate report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
