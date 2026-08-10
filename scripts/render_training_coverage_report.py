from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ANIMAL_TIERS = {"knowledge_first", "high_demo", "candidate", "operational"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render knowledge-base to training-set coverage report.")
    parser.add_argument("--species-file", type=Path, default=Path("backend") / "app" / "data" / "species_knowledge.json")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest.csv")
    parser.add_argument("--output-json", type=Path, default=Path("storage") / "training" / "training_coverage.json")
    parser.add_argument("--output-md", type=Path, default=Path("docs") / "training_coverage_report.md")
    parser.add_argument("--target-total", type=int, default=30)
    parser.add_argument("--target-val", type=int, default=5)
    parser.add_argument("--minimum-total", type=int, default=20)
    return parser.parse_args()


def read_species(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("label")]


def classify_status(total: int, val: int, category: str, minimum_total: int, target_total: int, target_val: int) -> str:
    if category != "animal":
        return "knowledge_only"
    if total == 0:
        return "missing_training_samples"
    if total < minimum_total:
        return "need_more_samples"
    if val < target_val:
        return "need_more_validation"
    if total < target_total:
        return "expand_for_accuracy"
    return "trainable"


def next_action(status: str, category: str) -> str:
    if category == "plant":
        return "首版作为知识库展示；自动识别需另建植物图像数据集。"
    if status == "missing_training_samples":
        return "先收集清晰活体图，达到 20 张后再进入训练。"
    if status == "need_more_samples":
        return "优先补足自然或半自然场景活体图，避免动物园、尸体、痕迹和严重遮挡。"
    if status == "need_more_validation":
        return "增加不同地点、姿态、光照的验证图，避免只记住训练样本。"
    if status == "expand_for_accuracy":
        return "可训练，但建议继续扩到 30 张以上并增加混淆物种对照。"
    if status == "trainable":
        return "可进入下一轮迁移学习；训练后仍需按验证集结果保守上线。"
    return "保留知识卡，暂不进入自动识别承诺。"


def priority_score(item: dict[str, object], status: str) -> tuple[int, str]:
    tier = str(item.get("recognition_tier") or "")
    category = str(item.get("category") or "")
    tier_order = {
        "knowledge_first": 0,
        "high_demo": 1,
        "candidate": 2,
        "operational": 3,
    }
    status_order = {
        "missing_training_samples": 0,
        "need_more_samples": 1,
        "need_more_validation": 2,
        "expand_for_accuracy": 3,
        "trainable": 4,
        "knowledge_only": 5,
    }
    if category != "animal":
        return (9, str(item.get("cn_name") or ""))
    return (tier_order.get(tier, 8) * 10 + status_order.get(status, 9), str(item.get("cn_name") or ""))


def main() -> int:
    args = parse_args()
    species_rows = read_species(args.species_file)
    manifest_rows = read_manifest(args.manifest)

    split_counts: dict[str, Counter[str]] = defaultdict(Counter)
    folder_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in manifest_rows:
        label = row["label"]
        split = row.get("split") or "train"
        split_counts[label][split] += 1
        if row.get("folder_name"):
            folder_counts[label][row["folder_name"]] += 1

    coverage_rows: list[dict[str, object]] = []
    for item in species_rows:
        cn_name = str(item.get("cn_name") or "")
        category = str(item.get("category") or "")
        train = split_counts[cn_name]["train"]
        val = split_counts[cn_name]["val"]
        total = train + val
        status = classify_status(total, val, category, args.minimum_total, args.target_total, args.target_val)
        coverage_rows.append(
            {
                "cn_name": cn_name,
                "latin_name": item.get("latin_name") or "",
                "category": category,
                "recognition_tier": item.get("recognition_tier") or "",
                "protection_level": item.get("protection_level") or "",
                "train_count": train,
                "val_count": val,
                "total_count": total,
                "needed_to_minimum": max(0, args.minimum_total - total) if category == "animal" else 0,
                "needed_to_target": max(0, args.target_total - total) if category == "animal" else 0,
                "needed_val": max(0, args.target_val - val) if category == "animal" else 0,
                "status": status,
                "source_folders": dict(folder_counts.get(cn_name, Counter())),
                "next_action": next_action(status, category),
            }
        )

    coverage_rows.sort(key=lambda row: priority_score(row, str(row["status"])))
    status_counts = Counter(str(row["status"]) for row in coverage_rows)
    category_counts = Counter(str(row["category"]) for row in coverage_rows)
    animal_rows = [row for row in coverage_rows if row["category"] == "animal"]

    report = {
        "species_file": str(args.species_file),
        "manifest": str(args.manifest),
        "thresholds": {
            "minimum_total": args.minimum_total,
            "target_total": args.target_total,
            "target_val": args.target_val,
        },
        "summary": {
            "knowledge_species": len(coverage_rows),
            "animal_species": len(animal_rows),
            "category_counts": dict(category_counts),
            "status_counts": dict(status_counts),
            "trainable_animals": sum(1 for row in animal_rows if row["status"] == "trainable"),
            "covered_animals": sum(1 for row in animal_rows if int(row["total_count"]) > 0),
        },
        "species": coverage_rows,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 训练覆盖与扩类报告",
        "",
        "这份报告用于内部开发，不作为前台展示内容。它把知识库物种和训练清单对齐，帮助决定补样、扩类和下一轮训练顺序。",
        "",
        "## 汇总",
        "",
        f"- 知识库物种：{len(coverage_rows)}",
        f"- 动物物种：{len(animal_rows)}",
        f"- 已有训练样本的动物：{report['summary']['covered_animals']}",
        f"- 达到 trainable 的动物：{report['summary']['trainable_animals']}",
        f"- 最低训练门槛：每个动物 {args.minimum_total} 张，总目标 {args.target_total} 张，验证集目标 {args.target_val} 张",
        "",
        "## 状态统计",
        "",
        "| 状态 | 数量 |",
        "| --- | ---: |",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## 物种覆盖",
            "",
            "| 物种 | 类别 | 拉丁名 | 保护等级 | 等级 | 总数 | 训练 | 验证 | 状态 | 下一步 |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in coverage_rows:
        lines.append(
            f"| {row['cn_name']} | {row['category']} | {row['latin_name']} | {row['protection_level']} | "
            f"{row['recognition_tier']} | {row['total_count']} | {row['train_count']} | {row['val_count']} | "
            f"{row['status']} | {row['next_action']} |"
        )

    lines.extend(
        [
            "",
            "## 补样规则",
            "",
            "- 只把清晰活体、主体可见、自然或半自然场景图片进入训练集。",
            "- 不采用尸体、标本、粪便、洞穴、脚印、动物园笼舍、城市庭院、车窗视角、截图、严重遮挡或主体太小的图片。",
            "- 易混淆物种要成对补样，例如梅花鹿/水鹿、豹猫/家猫、黑熊/大型犬、中华斑羚/中华鬣羚。",
            "- 每次补样后重新生成 manifest、覆盖报告、训练集审核图和验证集评估报告。",
        ]
    )

    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
