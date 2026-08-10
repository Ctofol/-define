from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from download_gbif_reference_images import is_allowed_media_license


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
STATUS_PRIORITY = {
    "unreviewed": 0,
    "review_pass_candidate": 1,
    "reference_only": 2,
    "reject": 3,
    "approved": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a GBIF candidate review queue.")
    parser.add_argument("--root", type=Path, default=Path("reference_species") / "待复核" / "gbif")
    parser.add_argument("--contact-sheet-dir", type=Path, default=Path("docs") / "gbif_review_contact_sheets")
    parser.add_argument("--output-csv", type=Path, default=Path("docs") / "gbif_review_queue.csv")
    parser.add_argument("--output-md", type=Path, default=Path("docs") / "gbif_review_queue.md")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def metadata_by_filename(folder: Path) -> dict[str, dict[str, str]]:
    return {row.get("filename", ""): row for row in read_csv(folder / "metadata.csv") if row.get("filename")}


def review_status_by_key(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows = read_csv(root / "review_status.csv")
    return {
        (row.get("species", ""), row.get("filename", "")): row
        for row in rows
        if row.get("species") and row.get("filename")
    }


def suggested_action(status: str, license_allowed: bool) -> str:
    if not license_allowed:
        return "reject: license_not_allowed"
    if status == "approved":
        return "already approved; ready for promotion"
    if status == "review_pass_candidate":
        return "second review; promote only if live subject and scene are acceptable"
    if status == "reference_only":
        return "keep as reference; do not train"
    if status == "reject":
        return "keep rejected"
    return "manual review needed"


def status_sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    status = row.get("status", "unreviewed")
    return (STATUS_PRIORITY.get(status, 9), row.get("species", ""), row.get("filename", ""))


def main() -> int:
    args = parse_args()
    status_rows = review_status_by_key(args.root)
    queue_rows: list[dict[str, str]] = []

    folders = sorted([path for path in args.root.iterdir() if path.is_dir()]) if args.root.exists() else []
    for folder in folders:
        metadata_rows = metadata_by_filename(folder)
        images = [path for path in sorted(folder.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
        for image in images:
            metadata = metadata_rows.get(image.name, {})
            review = status_rows.get((folder.name, image.name), {})
            status = review.get("status") or "unreviewed"
            reason = review.get("reason") or ""
            license_value = metadata.get("license", "")
            license_allowed = is_allowed_media_license(license_value)
            queue_rows.append(
                {
                    "species": folder.name,
                    "filename": image.name,
                    "status": status,
                    "reason": reason,
                    "suggested_action": suggested_action(status, license_allowed),
                    "license_allowed": "yes" if license_allowed else "no",
                    "license": license_value,
                    "country": metadata.get("country", ""),
                    "locality": metadata.get("locality", ""),
                    "source_url": metadata.get("source_url", ""),
                    "contact_sheet": str((args.contact_sheet_dir / f"{folder.name}.jpg").as_posix()),
                }
            )

    queue_rows.sort(key=status_sort_key)
    fieldnames = [
        "species",
        "filename",
        "status",
        "reason",
        "suggested_action",
        "license_allowed",
        "license",
        "country",
        "locality",
        "source_url",
        "contact_sheet",
    ]
    write_csv(args.output_csv, queue_rows, fieldnames)

    status_counts = Counter(row["status"] for row in queue_rows)
    unreviewed_by_species: dict[str, int] = defaultdict(int)
    for row in queue_rows:
        if row["status"] == "unreviewed":
            unreviewed_by_species[row["species"]] += 1

    lines = [
        "# GBIF 候选图复核队列",
        "",
        "这份文件用于内部审核候选图，不作为前台页面。复核时优先看 `unreviewed`，再对 `review_pass_candidate` 做二次确认。",
        "",
        "## 汇总",
        "",
        f"- 候选图片总数：{len(queue_rows)}",
        f"- 未复核：{status_counts.get('unreviewed', 0)}",
        f"- 候选通过待二审：{status_counts.get('review_pass_candidate', 0)}",
        f"- 仅参考：{status_counts.get('reference_only', 0)}",
        f"- 已拒绝：{status_counts.get('reject', 0)}",
        f"- 已批准入训：{status_counts.get('approved', 0)}",
        "",
        "## 未复核优先级",
        "",
        "| 物种 | 未复核数量 | 联系表 |",
        "| --- | ---: | --- |",
    ]
    for species, count in sorted(unreviewed_by_species.items(), key=lambda item: (-item[1], item[0])):
        contact_sheet = (args.contact_sheet_dir / f"{species}.jpg").as_posix()
        lines.append(f"| {species} | {count} | `{contact_sheet}` |")

    lines.extend(
        [
            "",
            "## 审核标准",
            "",
            "- `approved`：清晰活体、主体较完整、自然或半自然场景、物种无明显争议、授权可用。",
            "- `reference_only`：能辅助认知，但不适合训练，例如主体较远、遮挡明显、场景偏人工、姿态异常。",
            "- `reject`：尸体、痕迹、洞穴、粪便、标本、动物园/笼舍、车窗/道路主导、截图、严重模糊、授权不合格。",
            "- `review_pass_candidate`：第一轮觉得可能可用，但仍需要二次确认后才能改成 `approved`。",
            "",
            "## 队列文件",
            "",
            f"- CSV：`{args.output_csv.as_posix()}`",
            "- 如果要更新复核状态，请写入 `reference_species/待复核/gbif/review_status.csv`，再重新生成本报告。",
        ]
    )

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output_csv}")
    print(f"wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
