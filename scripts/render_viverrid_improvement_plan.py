from __future__ import annotations

import csv
import json
from pathlib import Path


TARGET_SPECIES = ["大灵猫", "大斑灵猫", "小灵猫", "缟灵猫", "熊狸", "果子狸"]
REFERENCE_ROOT = Path("reference_species")
GBIF_REVIEW_ROOT = REFERENCE_ROOT / "待复核" / "gbif"
SUPPLEMENT_ROOT = REFERENCE_ROOT / "_supplement_candidates"
PDF_METADATA = REFERENCE_ROOT / "pdf_guangxi_species_images_v2" / "metadata.csv"
PDF_FLAGS = REFERENCE_ROOT / "pdf_guangxi_species_images_v2" / "quality_flags.csv"
MODEL_CONFIG = Path("models") / "species-classifier-local-v13-target-refresh" / "config.json"
OUTPUT = Path("docs") / "viverrid_v14_improvement_plan.md"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def count_images(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return len([path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES])


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def model_labels() -> set[str]:
    if not MODEL_CONFIG.exists():
        return set()
    payload = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    return set((payload.get("id2label") or {}).values())


def pdf_status_by_species() -> dict[str, str]:
    flags = {row.get("filename", ""): row.get("quality_status", "display") for row in read_csv(PDF_FLAGS)}
    status: dict[str, str] = {}
    for row in read_csv(PDF_METADATA):
        cn_name = row.get("cn_name", "")
        if cn_name in TARGET_SPECIES:
            status[cn_name] = flags.get(row.get("filename", ""), "display")
    return status


def main() -> int:
    labels = model_labels()
    pdf_status = pdf_status_by_species()
    rows = []
    for species in TARGET_SPECIES:
        rows.append(
            {
                "species": species,
                "in_v13": "yes" if species in labels else "no",
                "formal_images": count_images(REFERENCE_ROOT / species),
                "gbif_review_images": count_images(GBIF_REVIEW_ROOT / species),
                "hard_cases": count_images(SUPPLEMENT_ROOT / species),
                "pdf_gallery_status": pdf_status.get(species, "missing"),
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 灵猫科与熊狸类 v14 增强计划",
        "",
        "目标：降低大灵猫、熊狸、果子狸、小灵猫、大斑灵猫、缟灵猫之间的混淆，并减少黑色毛发局部图误推为黑熊。",
        "",
        "| 物种 | v13输出类 | 正式样本 | GBIF待复核 | 困难错例 | 图鉴状态 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['species']} | {row['in_v13']} | {row['formal_images']} | {row['gbif_review_images']} | {row['hard_cases']} | {row['pdf_gallery_status']} |"
        )

    lines.extend(
        [
            "",
            "## 当前判断",
            "",
            "- v13 目前只有“大灵猫”在正式输出类中，其余同组物种主要停留在图鉴/待复核层。",
            "- 最新人工确认的大灵猫局部图已进入困难错例池，不直接作为高质量正样本。",
            "- 新下载的 GBIF 图片仍在待复核池，需筛掉圈养、标本、主体过小、遮挡严重和物种不确定图片。",
            "",
            "## 建议推进",
            "",
            "1. 先人工或半自动复核 GBIF 候选图，保留每类 8-20 张正式候选。",
            "2. 若熊狸、果子狸、小灵猫、大斑灵猫、缟灵猫样本不足，继续按物种补图。",
            "3. v14 训练时加入同组负样本和困难错例，重点压低“黑熊”对局部黑色毛发的误触发。",
            "4. 前台识别范围明确标注：知识库覆盖图鉴物种，自动识别仅对已训练类稳定输出。",
        ]
    )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
