from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


DEFAULT_INPUT = Path("storage") / "training" / "species_manifest_v15_reviewed_supplement.csv"
DEFAULT_DECISIONS = [Path("docs") / "confusion_pair_audit" / "cleaning_candidates.csv"]
DEFAULT_OUTPUT = Path("storage") / "training" / "species_manifest_v16_cleaned_confusion.csv"
DEFAULT_REPORT = Path("docs") / "confusion_pair_audit" / "cleaned_manifest_report.md"
EXCLUDE_DECISIONS = {"exclude", "exclude_from_training", "reject", "reference_only"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a training manifest with reviewed confusion samples excluded.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--decisions", type=Path, action="append", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--min-train-per-label", type=int, default=3)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_path(value: str) -> str:
    if not value:
        return ""
    return Path(value.replace("\\", "/")).as_posix().lower()


def row_keys(row: dict[str, str]) -> set[str]:
    keys: set[str] = set()
    for field in ("file_path", "relative_path"):
        value = row.get(field, "")
        normalized = normalize_path(value)
        if not normalized:
            continue
        keys.add(normalized)
        if "/reference_species/" in normalized:
            keys.add(normalized.split("/reference_species/", 1)[1])
        if not normalized.startswith("reference_species/"):
            keys.add(f"reference_species/{normalized}")
    if row.get("sha256"):
        keys.add(f"sha256:{row['sha256'].strip().lower()}")
    return keys


def load_exclusions(decision_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    exclusions: dict[str, dict[str, str]] = {}
    for row in decision_rows:
        decision = row.get("decision", "").strip().lower()
        if decision not in EXCLUDE_DECISIONS:
            continue
        for key in row_keys(row):
            exclusions[key] = row
    return exclusions


def count_by_label(rows: list[dict[str, str]], split: str) -> Counter[str]:
    return Counter(row["label"] for row in rows if row.get("split") == split)


def render_report(
    *,
    input_path: Path,
    decisions_paths: list[Path],
    output_path: Path,
    kept_rows: list[dict[str, str]],
    excluded_rows: list[dict[str, str]],
    unmatched_decisions: list[dict[str, str]],
    min_train_per_label: int,
) -> str:
    train_counts = count_by_label(kept_rows, "train")
    val_counts = count_by_label(kept_rows, "val")
    low_train = [(label, count) for label, count in sorted(train_counts.items()) if count < min_train_per_label]

    lines = [
        "# Confusion Cleaning Manifest Report",
        "",
        f"- Input manifest: `{input_path}`",
        f"- Cleaning decisions: {', '.join(f'`{path}`' for path in decisions_paths)}",
        f"- Output manifest: `{output_path}`",
        f"- Kept rows: {len(kept_rows)}",
        f"- Excluded training rows: {len(excluded_rows)}",
        f"- Unmatched exclusion decisions: {len(unmatched_decisions)}",
        f"- Labels in kept manifest: {len(set(row['label'] for row in kept_rows if row.get('label')))}",
        "",
        "## Excluded Training Samples",
        "",
    ]
    if excluded_rows:
        lines.extend(["| Label | Relative path | Decision note |", "| --- | --- | --- |"])
        for row in excluded_rows:
            decision = row["_cleaning_decision"]
            lines.append(
                f"| {row.get('label', '')} | `{row.get('relative_path') or row.get('file_path', '')}` | {decision.get('decision_note', '')} |"
            )
    else:
        lines.append("No training samples were excluded.")

    lines.extend(["", "## Low Train Count Check", ""])
    if low_train:
        lines.extend(["| Label | Train | Val |", "| --- | ---: | ---: |"])
        for label, count in low_train:
            lines.append(f"| {label} | {count} | {val_counts.get(label, 0)} |")
    else:
        lines.append(f"No label is below {min_train_per_label} training samples.")

    if unmatched_decisions:
        lines.extend(["", "## Unmatched Decisions", "", "| Label | Relative path | Decision |", "| --- | --- | --- |"])
        for row in unmatched_decisions:
            lines.append(f"| {row.get('label', '')} | `{row.get('relative_path') or row.get('file_path', '')}` | {row.get('decision', '')} |")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    decisions_paths = args.decisions or DEFAULT_DECISIONS
    manifest_rows = [row for row in read_csv(args.input) if row.get("file_path") and row.get("label")]
    decision_rows: list[dict[str, str]] = []
    for decisions_path in decisions_paths:
        decision_rows.extend(read_csv(decisions_path))
    exclusions = load_exclusions(decision_rows)

    kept_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    matched_decision_ids: set[int] = set()

    for row in manifest_rows:
        matching_decision = None
        if row.get("split") == "train":
            for key in row_keys(row):
                if key in exclusions:
                    matching_decision = exclusions[key]
                    break
        if matching_decision:
            excluded = dict(row)
            excluded["_cleaning_decision"] = matching_decision
            excluded_rows.append(excluded)
            matched_decision_ids.add(id(matching_decision))
            continue
        kept_rows.append(row)

    unmatched_decisions = [
        row
        for row in decision_rows
        if row.get("decision", "").strip().lower() in EXCLUDE_DECISIONS and id(row) not in matched_decision_ids
    ]

    fieldnames = list(csv.DictReader(args.input.open("r", encoding="utf-8-sig", newline="")).fieldnames or [])
    if not fieldnames:
        fieldnames = ["file_path", "folder_name", "label", "split", "relative_path", "review_status", "sha256"]
    write_csv(args.output, [{field: row.get(field, "") for field in fieldnames} for row in kept_rows], fieldnames)

    report = render_report(
        input_path=args.input,
        decisions_paths=decisions_paths,
        output_path=args.output,
        kept_rows=kept_rows,
        excluded_rows=excluded_rows,
        unmatched_decisions=unmatched_decisions,
        min_train_per_label=args.min_train_per_label,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    summary = {
        "input_rows": len(manifest_rows),
        "kept_rows": len(kept_rows),
        "excluded_training_rows": len(excluded_rows),
        "unmatched_exclusion_decisions": len(unmatched_decisions),
        "output": str(args.output),
        "report": str(args.report),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
