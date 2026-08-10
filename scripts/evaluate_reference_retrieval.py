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

from app.services.reference_retrieval_service import ReferenceRetrievalService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate reference image retrieval on a manifest split.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest.csv")
    parser.add_argument("--split", default="val")
    parser.add_argument("--output-json", type=Path, default=Path("storage") / "training" / "reference_retrieval_eval.json")
    parser.add_argument("--output-md", type=Path, default=Path("docs") / "reference_retrieval_eval_report.md")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--backend", default="histogram", choices=["histogram", "transformers"])
    parser.add_argument("--embedding-model-path", type=Path, default=None)
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
    rows = read_manifest(args.manifest)
    eval_rows = [row for row in rows if row.get("split") == args.split]
    if not eval_rows:
        raise ValueError(f"no rows found for split={args.split}")

    service = ReferenceRetrievalService(
        manifest_path=args.manifest,
        backend=args.backend,
        embedding_model_path=args.embedding_model_path,
    )
    records: list[dict[str, object]] = []
    per_class_total: Counter[str] = Counter()
    per_class_top1: Counter[str] = Counter()
    per_class_topk: Counter[str] = Counter()

    for row in eval_rows:
        label = row["label"]
        per_class_total[label] += 1
        image_path = Path(row["file_path"])
        image = load_image(image_path)
        candidates = service.retrieve(image, limit=args.top_k, exclude_paths={image_path})
        labels = [candidate.label for candidate in candidates]
        top1 = bool(labels and labels[0] == label)
        topk = label in labels
        if top1:
            per_class_top1[label] += 1
        if topk:
            per_class_topk[label] += 1
        records.append(
            {
                "file_path": str(image_path),
                "label": label,
                "top1_label": labels[0] if labels else "",
                "top1_confidence": candidates[0].confidence if candidates else 0.0,
                "top_k_labels": labels,
                "top1_correct": top1,
                "topk_correct": topk,
            }
        )

    total = len(records)
    top1_correct = sum(1 for row in records if row["top1_correct"])
    topk_correct = sum(1 for row in records if row["topk_correct"])
    per_class = []
    for label in sorted(per_class_total):
        count = per_class_total[label]
        per_class.append(
            {
                "label": label,
                "total": count,
                "top1_correct": per_class_top1[label],
                "topk_correct": per_class_topk[label],
                "top1_accuracy": per_class_top1[label] / count if count else 0.0,
                "topk_accuracy": per_class_topk[label] / count if count else 0.0,
            }
        )

    report = {
        "manifest": str(args.manifest),
        "split": args.split,
        "top_k": args.top_k,
        "backend": args.backend,
        "embedding_model_path": str(args.embedding_model_path) if args.embedding_model_path else "",
        "evaluated_rows": total,
        "top1_correct": top1_correct,
        "topk_correct": topk_correct,
        "top1_accuracy": top1_correct / total if total else 0.0,
        "topk_accuracy": topk_correct / total if total else 0.0,
        "per_class": per_class,
        "records": records,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Reference Retrieval Evaluation",
        "",
        "- This evaluates weak reference-image retrieval, not final species recognition.",
        f"- Manifest: `{args.manifest}`",
        f"- Split: `{args.split}`",
        f"- Backend: `{args.backend}`",
        f"- Evaluated rows: {total}",
        f"- Top-1 accuracy: {format_pct(report['top1_accuracy'])}",
        f"- Top-{args.top_k} accuracy: {format_pct(report['topk_accuracy'])}",
        "",
        "## Per Class",
        "",
        "| Label | Total | Top-1 | Top-k | Top-1 Accuracy | Top-k Accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in per_class:
        lines.append(
            f"| {item['label']} | {item['total']} | {item['top1_correct']} | {item['topk_correct']} | "
            f"{format_pct(item['top1_accuracy'])} | {format_pct(item['topk_accuracy'])} |"
        )

    wrong = [row for row in records if not row["top1_correct"]]
    lines.extend(["", "## Top-1 Errors", ""])
    if wrong:
        lines.append("| Label | Top-1 | Confidence | File |")
        lines.append("| --- | --- | ---: | --- |")
        for row in wrong[:30]:
            lines.append(
                f"| {row['label']} | {row['top1_label']} | {format_pct(float(row['top1_confidence']))} | "
                f"`{Path(str(row['file_path'])).name}` |"
            )
    else:
        lines.append("No Top-1 errors.")

    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    print(f"top1={report['top1_accuracy']:.4f} top{args.top_k}={report['topk_accuracy']:.4f} rows={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
