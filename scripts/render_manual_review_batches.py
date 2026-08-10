from __future__ import annotations

import argparse
import csv
from pathlib import Path


PRIORITY_STATUS = {
    "review_pass_candidate": 0,
    "unreviewed": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render small manual review batches from the GBIF review queue.")
    parser.add_argument("--queue", type=Path, default=Path("docs") / "gbif_review_queue.csv")
    parser.add_argument("--review-root", type=Path, default=Path("reference_species") / "待复核" / "gbif")
    parser.add_argument("--output-dir", type=Path, default=Path("docs") / "manual_review_batches")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--statuses", nargs="*", default=["review_pass_candidate", "unreviewed"])
    return parser.parse_args()


def read_queue(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def row_sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    return (
        PRIORITY_STATUS.get(row["status"], 9),
        row["species"],
        row["filename"],
    )


def main() -> int:
    args = parse_args()
    wanted_statuses = set(args.statuses)
    rows = [row for row in read_queue(args.queue) if row.get("status") in wanted_statuses]
    rows.sort(key=row_sort_key)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in args.output_dir.glob("batch_*"):
        if stale_path.is_file() and stale_path.suffix.lower() in {".csv", ".md", ".jpg"}:
            stale_path.unlink()

    index_rows: list[dict[str, str]] = []
    for batch_index, start in enumerate(range(0, len(rows), args.batch_size), 1):
        batch_rows = rows[start : start + args.batch_size]
        batch_id = f"batch_{batch_index:02d}"
        csv_path = args.output_dir / f"{batch_id}.csv"
        md_path = args.output_dir / f"{batch_id}.md"

        output_rows: list[dict[str, str]] = []
        for item_index, row in enumerate(batch_rows, 1):
            image_path = (args.review_root / row["species"] / row["filename"]).resolve()
            output_rows.append(
                {
                    "item": str(item_index),
                    "species": row["species"],
                    "filename": row["filename"],
                    "current_status": row["status"],
                    "your_decision": "",
                    "reason": "",
                    "suggested_action": row.get("suggested_action", ""),
                    "country": row.get("country", ""),
                    "license_allowed": row.get("license_allowed", ""),
                    "image_path": str(image_path),
                    "source_url": row.get("source_url", ""),
                    "contact_sheet": row.get("contact_sheet", ""),
                }
            )

        fieldnames = [
            "item",
            "species",
            "filename",
            "current_status",
            "your_decision",
            "reason",
            "suggested_action",
            "country",
            "license_allowed",
            "image_path",
            "source_url",
            "contact_sheet",
        ]
        write_csv(csv_path, output_rows, fieldnames)

        lines = [
            f"# 人工审核批次 {batch_index:02d}",
            "",
            "请按图片质量和物种可靠性给出决定：`approved`、`reference_only` 或 `reject`。",
            "",
            "审核要点：清晰活体、主体较完整、自然或半自然场景、物种无明显争议、授权可用，才可 `approved`。",
            "",
            f"- CSV：`{csv_path.as_posix()}`",
            "",
            "| # | 物种 | 当前状态 | 国家/地区 | 建议动作 | 图片 |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
        for row in output_rows:
            image_link = row["image_path"].replace("\\", "/")
            lines.append(
                f"| {row['item']} | {row['species']} | {row['current_status']} | {row['country']} | "
                f"{row['suggested_action']} | `{image_link}` |"
            )

        lines.extend(
            [
                "",
                "## 回复格式",
                "",
                "你可以直接按下面格式回复，我会帮你写入 `review_status.csv`：",
                "",
                "```text",
                f"{batch_id}",
                "1 approved",
                "2 reject 主体太小/遮挡",
                "3 reference_only 场景偏人工",
                "```",
            ]
        )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        index_rows.append(
            {
                "batch": batch_id,
                "items": str(len(batch_rows)),
                "csv": str(csv_path),
                "markdown": str(md_path),
                "first_status": batch_rows[0]["status"] if batch_rows else "",
            }
        )

    write_csv(args.output_dir / "index.csv", index_rows, ["batch", "items", "csv", "markdown", "first_status"])
    print(f"wrote {len(index_rows)} batches to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
