from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from PIL import Image, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a local species image classifier on the validation split.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest.csv")
    parser.add_argument("--model-dir", type=Path, default=Path("models") / "species-classifier-local")
    parser.add_argument("--output-json", type=Path, default=Path("storage") / "training" / "baseline_eval.json")
    parser.add_argument("--output-md", type=Path, default=Path("docs") / "baseline_eval_report.md")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--local-files-only", action="store_true", default=True)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("file_path") and row.get("label")]


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def confidence_bucket(confidence: float) -> str:
    if confidence < 0.2:
        return "[0.0, 0.2)"
    if confidence < 0.4:
        return "[0.2, 0.4)"
    if confidence < 0.6:
        return "[0.4, 0.6)"
    if confidence < 0.8:
        return "[0.6, 0.8)"
    return "[0.8, 1.0]"


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    args = parse_args()

    import torch
    from transformers import AutoImageProcessor, AutoModelForImageClassification

    rows = read_manifest(args.manifest)
    val_rows = [row for row in rows if row.get("split") == "val"]
    if not val_rows:
        raise ValueError(f"manifest has no validation rows: {args.manifest}")

    if not args.model_dir.exists():
        raise FileNotFoundError(f"model dir does not exist: {args.model_dir}")

    processor = AutoImageProcessor.from_pretrained(str(args.model_dir), local_files_only=args.local_files_only)
    model = AutoModelForImageClassification.from_pretrained(str(args.model_dir), local_files_only=args.local_files_only)
    model.eval()

    id2label = {int(k): v for k, v in model.config.id2label.items()} if isinstance(model.config.id2label, dict) else {}
    if not id2label:
        id2label = {index: label for index, label in enumerate(sorted({row["label"] for row in rows}))}

    records: list[dict[str, object]] = []
    class_totals: Counter[str] = Counter()
    class_correct: Counter[str] = Counter()
    confusion: Counter[tuple[str, str]] = Counter()
    confidence_values: list[float] = []
    confidence_buckets: Counter[str] = Counter()
    skipped: list[dict[str, str]] = []

    with torch.no_grad():
        for row in val_rows:
            file_path = Path(row["file_path"])
            label = row["label"]
            class_totals[label] += 1
            try:
                image = load_image(file_path)
            except Exception as exc:
                skipped.append({"file_path": str(file_path), "label": label, "reason": f"{exc.__class__.__name__}: {exc}"})
                continue

            inputs = processor(images=image, return_tensors="pt")
            outputs = model(**inputs)
            probabilities = outputs.logits.softmax(dim=-1)[0]
            confidence, label_id = torch.max(probabilities, dim=0)
            predicted_label = str(id2label.get(int(label_id), int(label_id)))
            confidence_value = float(confidence)
            confidence_values.append(confidence_value)
            confidence_buckets[confidence_bucket(confidence_value)] += 1

            correct = predicted_label == label
            if correct:
                class_correct[label] += 1
            confusion[(label, predicted_label)] += 1

            records.append(
                {
                    "file_path": str(file_path),
                    "label": label,
                    "predicted_label": predicted_label,
                    "confidence": confidence_value,
                    "correct": correct,
                }
            )

    evaluated = len(records)
    correct = sum(1 for row in records if row["correct"])
    accuracy = (correct / evaluated) if evaluated else 0.0

    per_class = []
    for label in sorted(class_totals):
        total = class_totals[label]
        class_accuracy = (class_correct[label] / total) if total else 0.0
        per_class.append(
            {
                "label": label,
                "total": total,
                "correct": class_correct[label],
                "accuracy": class_accuracy,
            }
        )

    confusion_pairs = [
        {
            "true_label": true_label,
            "predicted_label": predicted_label,
            "count": count,
        }
        for (true_label, predicted_label), count in confusion.most_common()
        if true_label != predicted_label
    ]

    low_confidence_or_wrong = [
        row
        for row in records
        if (not row["correct"]) or float(row["confidence"]) < 0.4
    ]
    low_confidence_or_wrong.sort(key=lambda row: (row["correct"], float(row["confidence"])))

    report = {
        "manifest": str(args.manifest),
        "model_dir": str(args.model_dir),
        "total_validation_rows": len(val_rows),
        "evaluated_rows": evaluated,
        "skipped_rows": len(skipped),
        "correct": correct,
        "accuracy": accuracy,
        "confidence": {
            "mean": mean(confidence_values) if confidence_values else 0.0,
            "median": median(confidence_values) if confidence_values else 0.0,
            "min": min(confidence_values) if confidence_values else 0.0,
            "max": max(confidence_values) if confidence_values else 0.0,
            "buckets": dict(confidence_buckets),
        },
        "per_class": per_class,
        "confusion_pairs": confusion_pairs,
        "records": records,
        "low_confidence_or_wrong": low_confidence_or_wrong[:30],
        "skipped": skipped[:30],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Model Evaluation Report")
    lines.append("")
    lines.append("- This is a chain-verification model, not the final recognition model.")
    lines.append(f"- Manifest: `{args.manifest}`")
    lines.append(f"- Model: `{args.model_dir}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Validation rows: {len(val_rows)}")
    lines.append(f"- Evaluated rows: {evaluated}")
    lines.append(f"- Skipped rows: {len(skipped)}")
    lines.append(f"- Correct: {correct}")
    lines.append(f"- Accuracy: {format_pct(accuracy)}")
    lines.append(f"- Mean confidence: {format_pct(report['confidence']['mean'])}")
    lines.append(f"- Median confidence: {format_pct(report['confidence']['median'])}")
    lines.append("")
    lines.append("## Confidence Buckets")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("| --- | ---: |")
    for bucket in ["[0.0, 0.2)", "[0.2, 0.4)", "[0.4, 0.6)", "[0.6, 0.8)", "[0.8, 1.0]"]:
        lines.append(f"| {bucket} | {confidence_buckets.get(bucket, 0)} |")
    lines.append("")
    lines.append("## Per Class")
    lines.append("")
    lines.append("| Label | Total | Correct | Accuracy |")
    lines.append("| --- | ---: | ---: | ---: |")
    for item in per_class:
        lines.append(f"| {item['label']} | {item['total']} | {item['correct']} | {format_pct(item['accuracy'])} |")
    lines.append("")
    lines.append("## Confusion Pairs")
    lines.append("")
    if confusion_pairs:
        lines.append("| True | Predicted | Count |")
        lines.append("| --- | --- | ---: |")
        for item in confusion_pairs[:20]:
            lines.append(f"| {item['true_label']} | {item['predicted_label']} | {item['count']} |")
    else:
        lines.append("No confusion pairs in the validation subset.")
    lines.append("")
    lines.append("## Low Confidence Or Wrong")
    lines.append("")
    if low_confidence_or_wrong:
        lines.append("| Label | Predicted | Confidence | Correct | File |")
        lines.append("| --- | --- | ---: | --- | --- |")
        for item in low_confidence_or_wrong[:20]:
            file_name = Path(str(item["file_path"])).name
            lines.append(
                f"| {item['label']} | {item['predicted_label']} | {format_pct(float(item['confidence']))} | "
                f"{'yes' if item['correct'] else 'no'} | `{file_name}` |"
            )
    else:
        lines.append("No low-confidence or wrong predictions.")
    lines.append("")
    lines.append("## Skipped")
    lines.append("")
    if skipped:
        lines.append("| Label | File | Reason |")
        lines.append("| --- | --- | --- |")
        for item in skipped[:20]:
            file_name = Path(str(item["file_path"])).name
            lines.append(f"| {item['label']} | `{file_name}` | {item['reason']} |")
    else:
        lines.append("No skipped rows.")

    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    print(f"accuracy={accuracy:.4f} evaluated={evaluated} skipped={len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
