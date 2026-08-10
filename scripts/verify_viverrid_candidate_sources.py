from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from PIL import Image


MANIFEST = Path("reference_species") / "_supplement_candidates" / "viverrids_quality_pass" / "manifest.csv"
MODEL_EVAL = Path("storage") / "training" / "local_v13_target_refresh_eval.json"
OUTPUT_DIR = Path("docs") / "viverrid_source_verification"

EXPECTED_SCIENTIFIC_NAMES = {
    "大灵猫": "Viverra zibetha",
    "大斑灵猫": "Viverra megaspila",
    "小灵猫": "Viverricula indica",
    "缟灵猫": "Chrotogale owstoni",
    "熊狸": "Arctictis binturong",
    "果子狸": "Paguma larvata",
}

REGIONAL_COUNTRIES = {"China", "Chinese Taipei", "Lao People’s Democratic Republic", "Myanmar", "Thailand", "Viet Nam"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_model_labels() -> set[str]:
    payload = json.loads(MODEL_EVAL.read_text(encoding="utf-8"))
    return {str(row.get("label", "")) for row in payload.get("per_class", []) if row.get("label")}


def image_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def verify_row(row: dict[str, str], model_labels: set[str]) -> dict[str, str]:
    species = row.get("species", "")
    filename = row.get("filename", "")
    scientific_name = row.get("scientific_name", "")
    source_url = row.get("source_url", "")
    license_value = row.get("license", "")
    country = row.get("country", "")
    image_path = Path(row.get("copied_path") or row.get("image_path", ""))

    expected_scientific_name = EXPECTED_SCIENTIFIC_NAMES.get(species, "")
    scientific_name_ok = scientific_name == expected_scientific_name
    gbif_url_ok = source_url.startswith("https://www.gbif.org/occurrence/")
    gbif_id = source_url.rstrip("/").split("/")[-1] if gbif_url_ok else ""
    filename_gbif_ok = bool(gbif_id and gbif_id in filename)
    license_ok = "creativecommons.org" in license_value.lower()
    image_exists = image_path.exists()
    width, height = image_dimensions(image_path) if image_exists else (0, 0)
    size_ok = width >= 480 and height >= 360
    is_model_class = species in model_labels
    is_regional = country in REGIONAL_COUNTRIES

    if not license_ok:
        gate = "hold_license_check"
    elif not (scientific_name_ok and gbif_url_ok and filename_gbif_ok and image_exists and size_ok):
        gate = "hold_source_or_file_check"
    elif is_model_class and country == "China":
        gate = "ready_model_training_local"
    elif is_model_class and is_regional:
        gate = "ready_model_training_regional_supplement"
    elif is_regional:
        gate = "knowledge_and_open_set_candidate"
    else:
        gate = "reference_only_out_of_region"

    return row | {
        "expected_scientific_name": expected_scientific_name,
        "scientific_name_ok": str(scientific_name_ok).lower(),
        "gbif_url_ok": str(gbif_url_ok).lower(),
        "filename_gbif_ok": str(filename_gbif_ok).lower(),
        "license_ok": str(license_ok).lower(),
        "image_exists": str(image_exists).lower(),
        "width": str(width),
        "height": str(height),
        "size_ok": str(size_ok).lower(),
        "current_model_class": str(is_model_class).lower(),
        "regional_source": str(is_regional).lower(),
        "promotion_gate": gate,
    }


def write_report(rows: list[dict[str, str]]) -> None:
    by_gate = Counter(row["promotion_gate"] for row in rows)
    by_species = Counter(row["species"] for row in rows)
    model_ready = [row for row in rows if row["promotion_gate"].startswith("ready_model_training")]
    open_set = [row for row in rows if row["promotion_gate"] == "knowledge_and_open_set_candidate"]

    lines = [
        "# 灵猫类候选来源校验报告",
        "",
        f"候选总数: {len(rows)}",
        "",
        "## 结论",
        "",
        f"- 可进入大灵猫 v14 补训练候选: {len(model_ready)}",
        f"- 进入知识库/开放集干扰候选: {len(open_set)}",
        f"- 暂缓: {len(rows) - len(model_ready) - len(open_set)}",
        "",
        "## 按用途分层",
        *[f"- {gate}: {count}" for gate, count in sorted(by_gate.items())],
        "",
        "## 按物种",
        *[f"- {species}: {count}" for species, count in sorted(by_species.items())],
        "",
        "## 下一步",
        "",
        "1. 将 `ready_model_training_regional_supplement` 作为大灵猫 v14 的补充候选，但保留地区来源标记。",
        "2. 将 `knowledge_and_open_set_candidate` 加入知识库，并作为开放集/相似物种干扰参考，暂不作为当前 12 类正样本。",
        "3. 重新生成训练 manifest 后，只对大灵猫候选做 dry-run 训练评估，确认不会拉低已有 12 类。",
    ]
    (OUTPUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    model_labels = load_model_labels()
    rows = [verify_row(row, model_labels) for row in read_csv(MANIFEST)]
    model_training_rows = [row for row in rows if row["promotion_gate"].startswith("ready_model_training")]
    knowledge_rows = [row for row in rows if row["promotion_gate"] == "knowledge_and_open_set_candidate"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_DIR / "verified_candidates.csv", rows)
    write_csv(OUTPUT_DIR / "model_training_candidates.csv", model_training_rows)
    write_csv(OUTPUT_DIR / "knowledge_open_set_candidates.csv", knowledge_rows)
    write_report(rows)
    print(f"verified {len(rows)} candidates")
    print(f"model_training_candidates={len(model_training_rows)}")
    print(f"knowledge_open_set_candidates={len(knowledge_rows)}")
    print(f"output={OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
