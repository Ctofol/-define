from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a model readiness report from evaluation artifacts.")
    parser.add_argument("--classifier-eval-json", type=Path, default=Path("storage") / "training" / "local_v6_clean_eval.json")
    parser.add_argument(
        "--retrieval-eval-json",
        type=Path,
        default=Path("storage") / "training" / "reference_retrieval_transformers_eval.json",
    )
    parser.add_argument("--coverage-json", type=Path, default=Path("storage") / "training" / "training_coverage.json")
    parser.add_argument("--output-json", type=Path, default=Path("storage") / "training" / "model_readiness.json")
    parser.add_argument("--output-md", type=Path, default=Path("docs") / "model_readiness_report.md")
    parser.add_argument("--min-validation-per-class", type=int, default=3)
    parser.add_argument("--min-classifier-accuracy", type=float, default=0.7)
    parser.add_argument("--min-retrieval-top3", type=float, default=0.8)
    parser.add_argument("--min-ready-class-accuracy", type=float, default=0.6)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    args = parse_args()
    classifier_eval = load_json(args.classifier_eval_json)
    retrieval_eval = load_json(args.retrieval_eval_json)
    coverage = load_json(args.coverage_json)

    coverage_by_label = {
        str(row["cn_name"]): row
        for row in coverage.get("species", [])
        if row.get("category") == "animal"
    }
    classifier_by_label = {str(row["label"]): row for row in classifier_eval.get("per_class", [])}
    retrieval_by_label = {str(row["label"]): row for row in retrieval_eval.get("per_class", [])}

    confusion_by_true: dict[str, Counter[str]] = {}
    for item in classifier_eval.get("confusion_pairs", []):
        true_label = str(item["true_label"])
        predicted = str(item["predicted_label"])
        confusion_by_true.setdefault(true_label, Counter())[predicted] += int(item["count"])

    rows: list[dict[str, object]] = []
    for label, coverage_row in coverage_by_label.items():
        classifier_row = classifier_by_label.get(label, {})
        retrieval_row = retrieval_by_label.get(label, {})
        total_count = int(coverage_row.get("total_count", 0))
        validation_total = int(classifier_row.get("total", 0) or 0)
        classifier_accuracy = float(classifier_row.get("accuracy", 0) or 0)
        retrieval_top3 = float(retrieval_row.get("topk_accuracy", 0) or 0)
        confusion = confusion_by_true.get(label, Counter())
        confusion_summary = " / ".join(f"{name} x{count}" for name, count in confusion.most_common(3)) or "-"

        blockers: list[str] = []
        if validation_total < args.min_validation_per_class:
            blockers.append("validation_too_small")
        if classifier_accuracy < args.min_ready_class_accuracy:
            blockers.append("classifier_weak")
        if retrieval_top3 < args.min_retrieval_top3:
            blockers.append("retrieval_weak")
        if int(coverage_row.get("needed_to_minimum", 0)) > 0:
            blockers.append("needs_more_samples")

        if not blockers:
            status = "ready_for_candidate_display"
        elif "classifier_weak" in blockers or "retrieval_weak" in blockers:
            status = "not_ready"
        else:
            status = "needs_more_data"

        rows.append(
            {
                "label": label,
                "total_count": total_count,
                "validation_total": validation_total,
                "classifier_accuracy": classifier_accuracy,
                "retrieval_top3": retrieval_top3,
                "confusion": confusion_summary,
                "blockers": blockers,
                "status": status,
            }
        )

    rows.sort(key=lambda row: (0 if row["status"] != "ready_for_candidate_display" else 1, row["label"]))

    overall_classifier_accuracy = float(classifier_eval.get("accuracy", 0) or 0)
    overall_retrieval_top3 = float(retrieval_eval.get("topk_accuracy", 0) or 0)
    can_promote = overall_classifier_accuracy >= args.min_classifier_accuracy and overall_retrieval_top3 >= args.min_retrieval_top3

    report = {
        "classifier_eval": str(args.classifier_eval_json),
        "retrieval_eval": str(args.retrieval_eval_json),
        "coverage": str(args.coverage_json),
        "overall": {
            "classifier_accuracy": overall_classifier_accuracy,
            "retrieval_top3": overall_retrieval_top3,
            "can_promote": can_promote,
            "classifier_threshold": args.min_classifier_accuracy,
            "retrieval_threshold": args.min_retrieval_top3,
        },
        "rows": rows,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# 模型发布门槛报告")
    lines.append("")
    lines.append(f"- 分类器评估：`{args.classifier_eval_json}`")
    lines.append(f"- 参考检索评估：`{args.retrieval_eval_json}`")
    lines.append(f"- 覆盖率报告：`{args.coverage_json}`")
    lines.append("")
    lines.append("## 总体判断")
    lines.append("")
    lines.append(f"- 分类器准确率：{format_pct(overall_classifier_accuracy)}")
    lines.append(f"- 参考检索 Top-3：{format_pct(overall_retrieval_top3)}")
    lines.append(f"- 是否建议提升为更强演示口径：{'是' if can_promote else '否'}")
    lines.append("")
    lines.append("## 物种门槛")
    lines.append("")
    lines.append("| 物种 | 样本数 | 验证数 | 分类器准确率 | 检索Top3 | 主要混淆 | 状态 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- | --- |")
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['total_count']} | {row['validation_total']} | {format_pct(float(row['classifier_accuracy']))} | "
            f"{format_pct(float(row['retrieval_top3']))} | {row['confusion']} | {row['status']} |"
        )
    lines.append("")
    lines.append("## 解释")
    lines.append("")
    lines.append("- `not_ready`：分类器或检索仍偏弱，不建议把该类当作稳定识别结果。")
    lines.append("- `needs_more_data`：模型链路可用，但还需要补样或补验证。")
    lines.append("- `ready_for_candidate_display`：可进入较强候选展示，但仍保留复核口径。")

    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    print(f"can_promote={can_promote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
