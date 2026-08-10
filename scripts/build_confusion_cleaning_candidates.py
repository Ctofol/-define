from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_INPUT_DIR = Path("docs") / "confusion_pair_audit"
DEFAULT_OUTPUT = Path("docs") / "confusion_pair_audit" / "cleaning_candidates.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a first-pass cleaning queue from confusion-pair audit CSVs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-risk", type=int, default=2)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def suggested_action(row: dict[str, str]) -> tuple[str, str]:
    flags = set(filter(None, row.get("flags", "").split("|")))
    if "image_error" in flags:
        return "exclude", "image_error"
    if row.get("split") == "val":
        return "keep_for_eval", "validation_error_or_hardcase"
    if "low_detail" in flags and ("gbif" in flags or "supplement" in flags):
        return "review_exclude", "low_detail_training_sample"
    if "small_image" in flags:
        return "review_exclude", "small_training_sample"
    if "very_dark" in flags:
        return "review_exclude", "very_dark_training_sample"
    if "supplement" in flags:
        return "manual_check", "supplement_training_sample"
    return "manual_check", "confusion_pair_training_sample"


def main() -> int:
    args = parse_args()
    candidates: dict[str, dict[str, str]] = {}
    for audit_csv in sorted(args.input_dir.glob("*_vs_*.csv")):
        pair = audit_csv.stem
        for row in read_rows(audit_csv):
            risk = int(float(row.get("risk_score") or 0))
            if row.get("split") != "train":
                continue
            action, reason = suggested_action(row)
            if risk < args.min_risk:
                continue
            key = row["file_path"]
            existing = candidates.get(key)
            if existing and int(existing["risk_score"]) >= risk:
                existing["pairs"] = "|".join(sorted(set(existing["pairs"].split("|")) | {pair}))
                continue
            candidates[key] = {
                "pairs": pair,
                "label": row.get("label", ""),
                "split": row.get("split", ""),
                "file_path": row.get("file_path", ""),
                "relative_path": row.get("relative_path", ""),
                "risk_score": str(risk),
                "flags": row.get("flags", ""),
                "suggested_action": action,
                "reason": reason,
                "decision": "",
                "decision_note": "",
            }

    fieldnames = [
        "pairs",
        "label",
        "split",
        "file_path",
        "relative_path",
        "risk_score",
        "flags",
        "suggested_action",
        "reason",
        "decision",
        "decision_note",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(candidates.values(), key=lambda row: (-int(row["risk_score"]), row["label"], row["file_path"])))

    print(f"wrote {len(candidates)} cleaning candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
