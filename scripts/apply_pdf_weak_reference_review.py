from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_REVIEW_DIR = Path("docs") / "pdf_weak_reference_review"
VALID_STATUSES = {"approved", "reference_only", "reject", "pending_pdf_review"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply decisions to the PDF weak-reference review status CSV.")
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--batch", required=True, help="Batch id, for example batch_01.")
    parser.add_argument("--approve", default="", help="Comma/space separated item numbers in this batch.")
    parser.add_argument("--reference-only", default="", help="Comma/space separated item numbers in this batch.")
    parser.add_argument("--reject", default="", help="Comma/space separated item numbers in this batch.")
    parser.add_argument("--approve-rest", action="store_true", help="Mark undecided items in this batch as approved.")
    parser.add_argument("--reason", default="", help="Reason to write for explicit decisions.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_path = args.review_dir / f"{args.batch}.csv"
    status_path = args.review_dir / "review_status.csv"
    if not batch_path.exists():
        raise FileNotFoundError(f"batch not found: {batch_path}")
    if not status_path.exists():
        raise FileNotFoundError(f"review status not found: {status_path}")

    batch_rows = read_csv(batch_path)
    status_rows = read_csv(status_path)
    status_by_global_id = {row["global_id"]: row for row in status_rows}

    decisions = build_decisions(args, batch_rows)
    applied = 0
    for batch_row in batch_rows:
        item = int(batch_row["item"])
        status = decisions.get(item)
        if not status:
            continue
        global_id = batch_row["global_id"]
        status_row = status_by_global_id[global_id]
        status_row["status"] = status
        status_row["reason"] = args.reason or default_reason(status)
        applied += 1

    merged_rows = sorted(status_by_global_id.values(), key=lambda row: int(row["global_id"]))
    if not args.dry_run:
        write_csv(status_path, merged_rows, list(merged_rows[0].keys()))
        refresh_batch_status(batch_path, batch_rows, decisions, args.reason)

    summary = status_summary(merged_rows)
    print(f"applied={applied} dry_run={args.dry_run}")
    print(" ".join(f"{status}={count}" for status, count in sorted(summary.items())))
    return 0


def build_decisions(args: argparse.Namespace, batch_rows: list[dict[str, str]]) -> dict[int, str]:
    decisions: dict[int, str] = {}
    for status, raw_items in [
        ("approved", args.approve),
        ("reference_only", getattr(args, "reference_only")),
        ("reject", args.reject),
    ]:
        for item in parse_items(raw_items):
            if item in decisions:
                raise ValueError(f"item {item} has multiple decisions")
            decisions[item] = status

    valid_items = {int(row["item"]) for row in batch_rows}
    unknown = sorted(set(decisions) - valid_items)
    if unknown:
        raise ValueError(f"items not in {args.batch}: {unknown}")

    if args.approve_rest:
        for item in valid_items:
            decisions.setdefault(item, "approved")
    return decisions


def parse_items(raw: str) -> list[int]:
    if not raw.strip():
        return []
    normalized = raw.replace("，", ",").replace("、", ",").replace("；", ",").replace(";", ",")
    items: list[int] = []
    for chunk in normalized.replace(",", " ").split():
        if not chunk:
            continue
        items.append(int(chunk))
    return items


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def refresh_batch_status(batch_path: Path, batch_rows: list[dict[str, str]], decisions: dict[int, str], reason: str) -> None:
    for row in batch_rows:
        item = int(row["item"])
        status = decisions.get(item)
        if status:
            row["current_status"] = status
            row["your_decision"] = status
            row["reason"] = reason or default_reason(status)
    write_csv(batch_path, batch_rows, list(batch_rows[0].keys()))


def default_reason(status: str) -> str:
    return {
        "approved": "visual_review_passed",
        "reference_only": "kept_as_weak_reference",
        "reject": "visual_review_rejected",
        "pending_pdf_review": "",
    }.get(status, "")


def status_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        status = row.get("status", "")
        if status not in VALID_STATUSES:
            status = "unknown"
        summary[status] = summary.get(status, 0) + 1
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
