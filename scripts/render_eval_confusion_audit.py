from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from render_confusion_pair_audit import audit_rows, render_sheet, write_csv, write_summary


DEFAULT_EVAL_JSONS = [
    Path("storage") / "training" / "local_v14_manual_eval.json",
    Path("storage") / "training" / "hybrid_recognition_v16_cleaned_confusion_eval.json",
    Path("storage") / "training" / "local_v18_cleaned_confusion_eval.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render audit sheets from evaluation confusion pairs.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest_v16_cleaned_confusion.csv")
    parser.add_argument("--eval-json", type=Path, action="append", default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("docs") / "confusion_pair_audit_round2")
    parser.add_argument("--max-pairs", type=int, default=8)
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--thumb-width", type=int, default=220)
    parser.add_argument("--thumb-height", type=int, default=168)
    parser.add_argument("--columns", type=int, default=4)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("file_path") and row.get("label")]


def predicted_label(record: dict[str, object]) -> str:
    predicted = record.get("predicted_label")
    if predicted:
        return str(predicted)
    strategies = record.get("strategies")
    if isinstance(strategies, dict) and strategies.get("hybrid_tuned_override"):
        return str(strategies["hybrid_tuned_override"])
    if record.get("classifier_label"):
        return str(record["classifier_label"])
    return ""


def load_eval(path: Path) -> tuple[Counter[tuple[str, str]], dict[str, dict[str, object]]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    pairs: Counter[tuple[str, str]] = Counter()
    records_by_name: dict[str, dict[str, object]] = {}
    for record in report.get("records", []):
        label = str(record.get("label", ""))
        predicted = predicted_label(record)
        file_name = Path(str(record.get("file_path", ""))).name
        if file_name:
            records_by_name[file_name] = {
                **record,
                "classifier_label": predicted,
                "strategies": {"hybrid_tuned_override": predicted},
            }
        if label and predicted and label != predicted:
            pairs[tuple(sorted((label, predicted)))] += 1
    return pairs, records_by_name


def safe_pair_name(left: str, right: str) -> str:
    return f"{left}_vs_{right}".replace("/", "_").replace("\\", "_")


def main() -> int:
    args = parse_args()
    eval_paths = args.eval_json or DEFAULT_EVAL_JSONS
    rows = read_manifest(args.manifest)

    pair_counts: Counter[tuple[str, str]] = Counter()
    eval_records: dict[str, dict[str, object]] = {}
    for path in eval_paths:
        if not path.exists():
            continue
        pairs, records = load_eval(path)
        pair_counts.update(pairs)
        eval_records.update(records)

    selected_pairs = [
        pair
        for pair, count in pair_counts.most_common(args.max_pairs)
        if count >= args.min_count
    ]
    pair_rows: dict[str, list[dict[str, object]]] = {}
    for left, right in selected_pairs:
        pair_name = safe_pair_name(left, right)
        labels = {left, right}
        selected_rows = [row for row in rows if row["label"] in labels]
        audited = audit_rows(selected_rows, eval_records)
        pair_rows[pair_name] = audited
        write_csv(args.output_dir / f"{pair_name}.csv", audited)
        render_sheet(pair_name, audited, args.output_dir / f"{pair_name}.jpg", args)

    write_summary(args.output_dir / "summary.md", pair_rows)
    print(f"selected_pairs={len(selected_pairs)}")
    for pair in selected_pairs:
        print(f"{pair[0]} vs {pair[1]}: {pair_counts[pair]}")
    print(f"output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
