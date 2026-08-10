from __future__ import annotations

import argparse
import csv
from pathlib import Path


REVIEW_DIR = Path("docs") / "viverrid_user_quality_review"
REVIEW_STATUS = Path("reference_species") / "待复核" / "gbif" / "review_status.csv"
USER_DECISIONS = REVIEW_DIR / "user_quality_decisions.csv"

DEFAULT_REJECT_REASON = "user_reject_quality"


def parse_rejects(value: str) -> dict[str, str]:
    rejects: dict[str, str] = {}
    if not value.strip():
        return rejects
    for raw_part in value.replace("，", ",").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" in part:
            item, reason = part.split("=", 1)
        elif ":" in part:
            item, reason = part.split(":", 1)
        else:
            item, reason = part, DEFAULT_REJECT_REASON
        item = item.strip().lstrip("#")
        if not item.isdigit():
            raise ValueError(f"invalid item number in --reject: {raw_part!r}")
        rejects[str(int(item))] = reason.strip() or DEFAULT_REJECT_REASON
    return rejects


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)


def update_batch(batch: str, rejects: dict[str, str], approve_rest: bool) -> list[dict[str, str]]:
    batch_csv = REVIEW_DIR / f"{batch}.csv"
    if not batch_csv.exists():
        raise FileNotFoundError(f"missing batch csv: {batch_csv}")

    rows = read_csv(batch_csv)
    known_items = {row["item"] for row in rows}
    unknown = sorted(set(rejects) - known_items, key=int)
    if unknown:
        raise ValueError(f"{batch} has no item(s): {', '.join(unknown)}")

    for row in rows:
        item = row["item"]
        if item in rejects:
            row["user_quality_decision"] = "reject"
            row["user_reason"] = rejects[item]
        elif approve_rest:
            row["user_quality_decision"] = "usable"
            row["user_reason"] = "user_quality_pass"

    write_csv(batch_csv, list(rows[0].keys()), rows)
    return rows


def merge_user_decisions(batch_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    fieldnames = [
        "global_id",
        "batch",
        "item",
        "species",
        "filename",
        "user_quality_decision",
        "user_reason",
        "image_path",
        "source_url",
    ]
    existing: dict[tuple[str, str], dict[str, str]] = {}
    if USER_DECISIONS.exists():
        for row in read_csv(USER_DECISIONS):
            existing[(row.get("species", ""), row.get("filename", ""))] = row

    for row in batch_rows:
        decision = row.get("user_quality_decision", "")
        if not decision:
            continue
        existing[(row["species"], row["filename"])] = {
            "global_id": row.get("global_id", ""),
            "batch": row.get("batch", ""),
            "item": row.get("item", ""),
            "species": row.get("species", ""),
            "filename": row.get("filename", ""),
            "user_quality_decision": decision,
            "user_reason": row.get("user_reason", ""),
            "image_path": row.get("image_path", ""),
            "source_url": row.get("source_url", ""),
        }

    rows = [existing[key] for key in sorted(existing)]
    write_csv(USER_DECISIONS, fieldnames, rows)
    return rows


def update_review_status(decisions: list[dict[str, str]]) -> tuple[int, int]:
    if not REVIEW_STATUS.exists():
        raise FileNotFoundError(f"missing review status csv: {REVIEW_STATUS}")

    status_rows = read_csv(REVIEW_STATUS)
    fieldnames = list(status_rows[0].keys())
    index = {(row.get("species", ""), row.get("filename", "")): row for row in status_rows}

    accepted = 0
    rejected = 0
    for decision in decisions:
        key = (decision["species"], decision["filename"])
        row = index.get(key)
        if row is None:
            continue
        if decision["user_quality_decision"] == "reject":
            row["status"] = "user_reject_quality"
            row["reason"] = decision.get("user_reason", DEFAULT_REJECT_REASON)
            row["suggested_action"] = "exclude from training/reference promotion unless manually rescued"
            rejected += 1
        elif decision["user_quality_decision"] == "usable":
            row["status"] = "quality_pass_candidate"
            row["reason"] = decision.get("user_reason", "user_quality_pass")
            row["suggested_action"] = "next: verify species/source metadata before promotion"
            accepted += 1

    write_csv(REVIEW_STATUS, fieldnames, status_rows)
    return accepted, rejected


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply user image-quality review for viverrid GBIF batches.")
    parser.add_argument("--batch", required=True, help="Batch id, for example batch_01.")
    parser.add_argument("--reject", default="", help="Rejected item numbers, e.g. '3,5=blurry,9=bad_crop'.")
    parser.add_argument(
        "--approve-rest",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Mark all non-rejected items in this batch as usable.",
    )
    args = parser.parse_args()

    rejects = parse_rejects(args.reject)
    batch_rows = update_batch(args.batch, rejects, args.approve_rest)
    decisions = merge_user_decisions(batch_rows)
    accepted, rejected = update_review_status(decisions)

    print(f"updated {args.batch}: rejected={len(rejects)}, approve_rest={args.approve_rest}")
    print(f"user decision rows={len(decisions)}")
    print(f"review_status quality_pass_candidate={accepted}, user_reject_quality={rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
