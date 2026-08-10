from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a markdown readiness report from a training audit json.")
    parser.add_argument("--audit", type=Path, default=Path("storage") / "training" / "species_manifest_audit.json")
    parser.add_argument("--output", type=Path, default=Path("docs") / "training_readiness_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = json.loads(args.audit.read_text(encoding="utf-8"))
    classes = sorted(
        report.get("classes", []),
        key=lambda item: (
            0 if item.get("status") == "need_more_samples" else 1 if item.get("status") == "need_more_validation" else 2,
            int(item.get("total", 0)),
            str(item.get("label", "")),
        ),
    )

    lines: list[str] = []
    lines.append("# 训练集补样优先级报告")
    lines.append("")
    lines.append(f"- 清单总行数：{report.get('total_rows', 0)}")
    lines.append(f"- 物种数量：{report.get('label_count', 0)}")
    lines.append("")
    lines.append("## 优先补样")
    lines.append("")
    lines.append("| 物种 | 当前总数 | 训练 | 验证 | 还差总数 | 还差验证 | 状态 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for item in classes:
        lines.append(
            f"| {item.get('label', '')} | {item.get('total', 0)} | {item.get('train_count', 0)} | {item.get('val_count', 0)} | "
            f"{item.get('needed_total', 0)} | {item.get('needed_val', 0)} | {item.get('status', '')} |"
        )

    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- `need_more_samples`：总样本未到可训练门槛。")
    lines.append("- `need_more_validation`：训练样本够用，但验证样本不足。")
    lines.append("- `has_small_images`：存在尺寸过小或低质量图片。")
    lines.append("- `ready`：当前样本量已可进入基础迁移学习。")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote readiness report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
