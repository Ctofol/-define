from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "backend"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate hybrid classifier + retrieval decision strategies.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest_v15_reviewed_supplement.csv")
    parser.add_argument("--model-dir", type=Path, default=Path("models") / "species-classifier-local-v14-manual")
    parser.add_argument("--output-json", type=Path, default=Path("storage") / "training" / "hybrid_recognition_eval.json")
    parser.add_argument("--output-md", type=Path, default=Path("docs") / "hybrid_recognition_eval_report.md")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--retrieval-manifest", type=Path, default=Path("storage") / "training" / "species_manifest_v15_reviewed_supplement.csv")
    parser.add_argument("--local-files-only", action="store_true", default=True)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("file_path") and row.get("label")]


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    args = parse_args()

    import torch
    from transformers import AutoImageProcessor, AutoModelForImageClassification

    from app.services.reference_retrieval_service import ReferenceRetrievalService

    rows = read_manifest(args.manifest)
    eval_rows = [row for row in rows if row.get("split") == "val"]
    if not eval_rows:
        raise ValueError(f"no validation rows in {args.manifest}")

    processor = AutoImageProcessor.from_pretrained(str(args.model_dir), local_files_only=args.local_files_only)
    model = AutoModelForImageClassification.from_pretrained(str(args.model_dir), local_files_only=args.local_files_only)
    model.eval()
    id2label = {int(k): v for k, v in model.config.id2label.items()} if isinstance(model.config.id2label, dict) else {}

    retrieval = ReferenceRetrievalService(manifest_path=args.retrieval_manifest, embedding_model_path=args.model_dir)

    records: list[dict[str, object]] = []
    strategy_counts = Counter()
    strategy_correct = Counter()
    per_class = Counter()
    rescued_by_retrieval = Counter()

    with torch.no_grad():
        for row in eval_rows:
            label = row["label"]
            per_class[label] += 1
            image_path = Path(row["file_path"])
            image = load_image(image_path)

            inputs = processor(images=image, return_tensors="pt")
            outputs = model(**inputs)
            probabilities = outputs.logits.softmax(dim=-1)[0]
            confidence, label_id = torch.max(probabilities, dim=0)
            classifier_label = str(id2label.get(int(label_id), int(label_id)))
            classifier_confidence = float(confidence)

            candidates = retrieval.retrieve(image, limit=args.top_k, exclude_paths={image_path})
            retrieval_labels = [candidate.label for candidate in candidates]
            retrieval_top1 = retrieval_labels[0] if retrieval_labels else ""
            retrieval_top1_confidence = candidates[0].confidence if candidates else 0.0

            strategies = {
                "classifier": classifier_label,
                "retrieval_top1": retrieval_top1,
                "hybrid_current_override": retrieval_top1 if classifier_confidence < 0.45 and retrieval_top1_confidence >= 0.4 else classifier_label,
                "hybrid_tuned_override": retrieval_top1 if classifier_confidence < 0.65 and retrieval_top1_confidence >= 0.35 else classifier_label,
                "oracle_retrieval_top1_rescue": retrieval_top1 if retrieval_top1 and classifier_label != label and retrieval_top1 == label else classifier_label,
                "oracle_top3_contains_true": retrieval_top1 if label in retrieval_labels and classifier_confidence < 0.55 else classifier_label,
            }

            if classifier_label != label and label in retrieval_labels:
                rescued_by_retrieval[label] += 1

            for name, predicted in strategies.items():
                strategy_counts[name] += 1
                if predicted == label:
                    strategy_correct[name] += 1

            records.append(
                {
                    "file_path": str(image_path),
                    "label": label,
                    "classifier_label": classifier_label,
                    "classifier_confidence": classifier_confidence,
                    "retrieval_top1": retrieval_top1,
                    "retrieval_top1_confidence": retrieval_top1_confidence,
                    "retrieval_topk_labels": retrieval_labels,
                    "strategies": strategies,
                }
            )

    report = {
        "manifest": str(args.manifest),
        "model_dir": str(args.model_dir),
        "retrieval_manifest": str(args.retrieval_manifest),
        "evaluated_rows": len(records),
        "strategies": {
            name: {
                "correct": strategy_correct[name],
                "accuracy": strategy_correct[name] / strategy_counts[name] if strategy_counts[name] else 0.0,
            }
            for name in sorted(strategy_counts)
        },
        "rescued_by_retrieval": dict(rescued_by_retrieval),
        "records": records,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Hybrid Recognition Evaluation",
        "",
        f"- Manifest: `{args.manifest}`",
        f"- Model: `{args.model_dir}`",
        f"- Retrieval manifest: `{args.retrieval_manifest}`",
        f"- Evaluated rows: {len(records)}",
        "",
        "## Strategies",
        "",
        "| Strategy | Correct | Accuracy |",
        "| --- | ---: | ---: |",
    ]
    for name in sorted(report["strategies"]):
        item = report["strategies"][name]
        lines.append(f"| {name} | {item['correct']} | {format_pct(item['accuracy'])} |")

    lines.extend(["", "## Retrieval Rescues", ""])
    if rescued_by_retrieval:
        lines.append("| Label | Count |")
        lines.append("| --- | ---: |")
        for label, count in sorted(rescued_by_retrieval.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"| {label} | {count} |")
    else:
        lines.append("No rescue cases.")

    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    for name, item in report["strategies"].items():
        print(f"{name}={item['accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
