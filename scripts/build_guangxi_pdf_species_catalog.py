from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT_DIR / "docs/source_pdfs/0719_guangxi_protected_wildlife_pocketbook.pdf"
DEFAULT_OUTPUT = ROOT_DIR / "backend/app/data/pdf_species_catalog.json"
DEFAULT_CSV_OUTPUT = ROOT_DIR / "docs/guangxi_pdf_species_catalog.csv"

ORDER_NAMES = {
    "攀鼩目",
    "翼手目",
    "灵长目",
    "鳞甲目",
    "食肉目",
    "偶蹄目",
    "啮齿目",
    "兔形目",
    "鸡形目",
    "雁形目",
    "䴙䴘目",
    "鸽形目",
    "夜鹰目",
    "鹃形目",
    "鹤形目",
    "鸻形目",
    "鹳形目",
    "鲣鸟目",
    "鹈形目",
    "鹰形目",
    "鸮形目",
    "咬鹃目",
    "犀鸟目",
    "佛法僧目",
    "啄木鸟目",
    "隼形目",
    "鹦形目",
    "雀形目",
    "龟鳖目",
    "有鳞目",
    "无尾目",
    "蚓螈目",
}

SKIP_LINE_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"^\d+$",
        r"^目\s*录$",
        r"图册",
        r"广西国家重点保护陆生野生脊椎动物一",
        r"广西重点保护陆生野生脊椎动物",
        r"罕见种",
        r"根据最新调查",
        r"列入《",
        r"隶属于",
        r"在 \d+ 种",
        r"国家一级",
        r"一、",
        r"二、",
        r"（一）",
        r"（二）",
        r"（三）",
    ]
]


@dataclass
class RawSpecies:
    cn_name: str
    latin_name: str
    category: str
    taxon_group: str
    order: str
    family: str
    genus: str
    protection_level: str
    source_scope: str
    source_page: int


def main() -> int:
    args = parse_args()
    rows = extract_species(args.pdf)
    if not rows:
        raise SystemExit(f"No species extracted from {args.pdf}")

    entries = [to_species_entry(row, index) for index, row in enumerate(rows, start=1)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    args.csv_output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.csv_output, entries)

    national_count = sum(1 for item in entries if item["source_scope"].startswith("广西国家"))
    local_count = len(entries) - national_count
    print(f"Wrote {len(entries)} species to {args.output}")
    print(f"National protected: {national_count}; Guangxi protected: {local_count}")
    print(f"CSV: {args.csv_output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a species catalog from the Guangxi protected wildlife pocketbook PDF.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    return parser.parse_args()


def extract_species(pdf_path: Path) -> list[RawSpecies]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError:
        import sys

        bundled_site_packages = (
            Path.home()
            / ".cache"
            / "codex-runtimes"
            / "codex-primary-runtime"
            / "dependencies"
            / "python"
            / "Lib"
            / "site-packages"
        )
        if bundled_site_packages.exists():
            sys.path.append(str(bundled_site_packages))
        from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    rows: list[RawSpecies] = []
    seen: set[tuple[str, str, str]] = set()

    current_category = ""
    current_taxon_group = ""
    current_order = ""
    current_scope = ""

    pending_name = ""
    pending_taxon = ""
    pending_page = 0
    pending_category = ""
    pending_taxon_group = ""
    pending_order = ""
    pending_scope = ""

    for page_number, page in enumerate(reader.pages, start=1):
        if page_number <= 3:
            continue
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = normalize_line(raw_line)
            if not line:
                continue

            if "广西国家重点保护陆生野生脊椎动物" in line or (page_number <= 33 and "广西国家" in line):
                current_scope = "广西国家重点保护陆生野生动物名录（2021年版）"
            elif "广西重点保护陆生野生脊椎动物" in line or page_number >= 34:
                current_scope = "广西重点保护野生动物名录（2023年版）"
            elif page_number <= 33 and not current_scope:
                current_scope = "广西国家重点保护陆生野生动物名录（2021年版）"
            elif page_number >= 34 and not current_scope:
                current_scope = "广西重点保护野生动物名录（2023年版）"

            next_category = category_from_line(line)
            if next_category:
                current_category = next_category
                current_taxon_group = taxon_group_for_category(next_category)
                continue

            if is_order_line(line):
                current_order = pick_last_order(line)
                continue

            if should_skip_line(line):
                continue

            if pending_name:
                if is_latin_line(line):
                    latin_name, explicit_level = parse_latin_line(line)
                    family, genus = split_taxon(pending_taxon)
                    protection_level = explicit_level or default_protection_level(pending_scope)
                    key = (pending_name, latin_name, pending_scope)
                    if key not in seen:
                        rows.append(
                            RawSpecies(
                                cn_name=pending_name,
                                latin_name=latin_name,
                                category=pending_category,
                                taxon_group=pending_taxon_group,
                                order=pending_order,
                                family=family,
                                genus=genus,
                                protection_level=protection_level,
                                source_scope=pending_scope,
                                source_page=pending_page,
                            )
                        )
                        seen.add(key)
                    pending_name = ""
                    pending_taxon = ""
                    continue
                if is_taxon_only_line(line):
                    pending_taxon += line
                    continue

            parsed = parse_species_line(line)
            if parsed:
                pending_name, pending_taxon = parsed
                pending_page = page_number
                pending_category = current_category or category_from_page(page_number)
                pending_taxon_group = current_taxon_group or taxon_group_for_category(pending_category)
                pending_order = current_order
                pending_scope = current_scope or ("广西国家重点保护陆生野生动物名录（2021年版）" if page_number <= 33 else "广西重点保护野生动物名录（2023年版）")
                continue

            name_only = parse_species_name_only_line(line)
            if name_only:
                pending_name = name_only
                pending_taxon = ""
                pending_page = page_number
                pending_category = current_category or category_from_page(page_number)
                pending_taxon_group = current_taxon_group or taxon_group_for_category(pending_category)
                pending_order = current_order
                pending_scope = current_scope or ("广西国家重点保护陆生野生动物名录（2021年版）" if page_number <= 33 else "广西重点保护野生动物名录（2023年版）")

    return rows


def normalize_line(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    value = value.replace("（ ", "（").replace(" ）", "）")
    return value


def category_from_line(line: str) -> str:
    compact = line.replace(" ", "")
    if compact.startswith("兽类（"):
        return "animal"
    if compact.startswith("鸟类（"):
        return "bird"
    if compact.startswith("爬行和两栖类（") or compact.startswith("爬行与两栖类（"):
        return "reptile_amphibian"
    return ""


def category_from_page(page_number: int) -> str:
    if 4 <= page_number <= 7 or 34 <= page_number <= 36:
        return "animal"
    if 8 <= page_number <= 29 or 37 <= page_number <= 44:
        return "bird"
    return "reptile_amphibian"


def taxon_group_for_category(category: str) -> str:
    return {
        "animal": "兽类",
        "bird": "鸟类",
        "reptile_amphibian": "爬行与两栖类",
    }.get(category, "")


def is_order_line(line: str) -> bool:
    compact = line.replace(" ", "")
    if "科" in compact or "属" in compact or "、" in compact or "。" in compact or "，" in compact:
        return False
    if compact in ORDER_NAMES:
        return True
    matches = [order for order in ORDER_NAMES if order in compact]
    return bool(matches) and "".join(matches) == compact and len(matches) <= 2


def pick_last_order(line: str) -> str:
    compact = line.replace(" ", "")
    matches = [order for order in ORDER_NAMES if order in compact]
    return matches[-1] if matches else ""


def should_skip_line(line: str) -> bool:
    return any(pattern.search(line) for pattern in SKIP_LINE_PATTERNS)


def is_latin_line(line: str) -> bool:
    body = strip_parentheses(line)
    return bool(re.search(r"[A-Z][a-z]+ [a-z-]+", body))


def strip_parentheses(line: str) -> str:
    return line.strip().strip("（）()").strip()


def parse_latin_line(line: str) -> tuple[str, str]:
    body = strip_parentheses(line)
    explicit_level = ""
    if body.endswith("一级"):
        explicit_level = "国家一级保护野生动物"
        body = body[: -len("一级")].strip()
    elif body.endswith("二级"):
        explicit_level = "国家二级保护野生动物"
        body = body[: -len("二级")].strip()
    body = re.sub(r"\s+", " ", body).strip()
    return body, explicit_level


def default_protection_level(scope: str) -> str:
    if scope.startswith("广西重点"):
        return "广西重点保护野生动物"
    return "国家重点保护野生动物"


def parse_species_line(line: str) -> tuple[str, str] | None:
    if "科" not in line:
        return None
    match = re.match(r"^(?P<name>.+?)\s+(?P<taxon>[^ ]*科.*)$", line)
    if not match:
        return None
    name = clean_species_name(match.group("name"))
    taxon = match.group("taxon").replace(" ", "")
    if not name or len(name) > 16 or "名录" in name:
        return None
    return name, taxon


def parse_species_name_only_line(line: str) -> str | None:
    compact = line.replace(" ", "")
    if not compact or is_latin_line(compact):
        return None
    if any(token in compact for token in ["科", "属", "目", "种", "广西国家", "图册", "名录"]):
        return None
    name = clean_species_name(compact)
    if not name or len(name) > 16:
        return None
    return name


def is_taxon_only_line(line: str) -> bool:
    compact = line.replace(" ", "")
    if not compact or "目" in compact or is_latin_line(compact):
        return False
    if "科" in compact and compact.endswith("属"):
        return True
    return compact.endswith("属") and "科" not in compact and len(compact) <= 12


def clean_species_name(name: str) -> str:
    name = re.sub(r"[（(][^）)]*[雌雄左右][^）)]*[）)]", "", name)
    return name.replace(" ", "").strip()


def split_taxon(taxon: str) -> tuple[str, str]:
    taxon = taxon.replace(" ", "")
    if "科" not in taxon:
        return taxon, ""
    family, rest = taxon.split("科", 1)
    family = family + "科"
    genus = rest if rest.endswith("属") else rest
    return family, genus


def to_species_entry(row: RawSpecies, index: int) -> dict[str, object]:
    return {
        "species_id": species_id(row, index),
        "cn_name": row.cn_name,
        "latin_name": row.latin_name,
        "category": row.category,
        "taxon_group": row.taxon_group,
        "order": row.order,
        "family": row.family,
        "genus": row.genus,
        "protection_level": row.protection_level,
        "source_scope": row.source_scope,
        "source_page": row.source_page,
        "recognition_tier": "candidate",
        "habits": "",
        "diet": "",
        "features": [],
        "habitat": "",
        "monitoring_value": "",
        "similar_species": [],
        "review_tips": "来自广西重点保护野生动物口袋书名录，系统识别结果仍需结合原图、区域分布和人工复核确认。",
        "tags": [tag for tag in [row.taxon_group, row.order, row.protection_level] if tag],
    }


def species_id(row: RawSpecies, index: int) -> str:
    if row.latin_name:
        candidate = re.sub(r"[^a-z0-9]+", "_", row.latin_name.lower()).strip("_")
        if candidate:
            return candidate
    return f"pdf_0719_{index:04d}"


def write_csv(path: Path, entries: list[dict[str, object]]) -> None:
    fieldnames = [
        "species_id",
        "cn_name",
        "latin_name",
        "category",
        "taxon_group",
        "order",
        "family",
        "genus",
        "protection_level",
        "source_scope",
        "source_page",
        "recognition_tier",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in entries:
            writer.writerow({field: item.get(field, "") for field in fieldnames})


if __name__ == "__main__":
    raise SystemExit(main())
