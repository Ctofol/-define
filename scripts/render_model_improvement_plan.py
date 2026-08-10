from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a next-step improvement plan from coverage and eval reports.")
    parser.add_argument("--coverage-json", type=Path, default=Path("storage") / "training" / "training_coverage.json")
    parser.add_argument("--eval-json", type=Path, default=Path("storage") / "training" / "local_v3_eval.json")
    parser.add_argument("--output", type=Path, default=Path("docs") / "model_improvement_plan.md")
    parser.add_argument("--model-name", default=None)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    coverage = load_json(args.coverage_json)
    evaluation = load_json(args.eval_json)
    model_name = args.model_name or str(evaluation.get("model", "") or args.eval_json.stem)

    coverage_by_label = {
        str(row["cn_name"]): row
        for row in coverage.get("species", [])
        if row.get("category") == "animal"
    }
    per_class = {str(row["label"]): row for row in evaluation.get("per_class", [])}
    confusion_by_true: dict[str, Counter[str]] = {}
    for item in evaluation.get("confusion_pairs", []):
        true_label = str(item["true_label"])
        predicted = str(item["predicted_label"])
        confusion_by_true.setdefault(true_label, Counter())[predicted] += int(item["count"])

    rows = []
    for label, coverage_row in coverage_by_label.items():
        eval_row = per_class.get(label, {})
        total_count = int(coverage_row.get("total_count", 0))
        eval_total = int(eval_row.get("total", 0) or 0)
        eval_accuracy = float(eval_row.get("accuracy", 0) or 0)
        needed_min = int(coverage_row.get("needed_to_minimum", 0))
        confusion = confusion_by_true.get(label, Counter())
        confusion_summary = "；".join(f"{name} x{count}" for name, count in confusion.most_common(3)) or "-"

        priority = 0
        if eval_total and eval_accuracy == 0:
            priority += 50
        elif eval_accuracy < 0.5:
            priority += 30
        if needed_min > 0:
            priority += min(20, needed_min)
        if confusion:
            priority += 10

        rows.append(
            {
                "label": label,
                "total_count": total_count,
                "needed_min": needed_min,
                "eval_total": eval_total,
                "eval_accuracy": eval_accuracy,
                "confusion": confusion_summary,
                "priority": priority,
            }
        )

    rows.sort(key=lambda row: (-row["priority"], row["label"]))

    lines = [
        "# 模型改进计划",
        "",
        f"本报告由训练覆盖和 {model_name} 验证结果生成，用于决定下一轮补样和训练方向。",
        "",
        f"## {model_name} 总结",
        "",
        f"- 验证准确率：{float(evaluation.get('accuracy', 0)) * 100:.1f}%",
        f"- 验证样本：{evaluation.get('evaluated_rows', 0)}",
        f"- 平均置信度：{float(evaluation.get('confidence', {}).get('mean', 0)) * 100:.1f}%",
        "",
        "## 补样优先级",
        "",
        "| 物种 | 当前样本 | 距 20 张 | 验证样本 | 验证准确率 | 主要误判 | 优先分 |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['total_count']} | {row['needed_min']} | {row['eval_total']} | "
            f"{row['eval_accuracy'] * 100:.1f}% | {row['confusion']} | {row['priority']} |"
        )

    lines.extend(
        [
            "",
            "## 下一轮动作",
            "",
            "- 先补验证准确率为 0 或严重混淆的类，而不是平均撒样本。",
            "- 水鹿/梅花鹿要成对补样，特别是水鹿清晰侧面、雌雄和不同背景。",
            "- 中华斑羚需要更多近景、侧面、山地环境样本，避免继续被误到大灵猫。",
            "- 猕猴、黄喉貂、赤狐、野猪继续补自然场景活体图，减少人工环境和远景。",
            "- 每次补样后重新生成 manifest、评估报告和错误联系表。",
        ]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
