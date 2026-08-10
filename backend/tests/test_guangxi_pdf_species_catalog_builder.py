from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.build_guangxi_pdf_species_catalog import DEFAULT_PDF, extract_species, to_species_entry


def test_guangxi_pdf_species_catalog_extracts_all_protected_species():
    rows = extract_species(DEFAULT_PDF)
    entries = [to_species_entry(row, index) for index, row in enumerate(rows, start=1)]

    assert len(entries) == 414
    assert Counter((item["source_scope"], item["category"]) for item in entries) == {
        ("广西国家重点保护陆生野生动物名录（2021年版）", "animal"): 37,
        ("广西国家重点保护陆生野生动物名录（2021年版）", "bird"): 197,
        ("广西国家重点保护陆生野生动物名录（2021年版）", "reptile_amphibian"): 28,
        ("广西重点保护野生动物名录（2023年版）", "animal"): 20,
        ("广西重点保护野生动物名录（2023年版）", "bird"): 78,
        ("广西重点保护野生动物名录（2023年版）", "reptile_amphibian"): 54,
    }


def test_guangxi_pdf_species_catalog_handles_split_name_and_taxon_lines():
    rows = extract_species(DEFAULT_PDF)
    by_latin = {row.latin_name: row for row in rows}

    assert by_latin["Harpactes oreskios"].cn_name == "橙胸咬鹃"
    assert by_latin["Psittacula eupatria"].cn_name == "亚历山大鹦鹉"
    assert by_latin["Boiga guangxiensis"].cn_name == "广西林蛇"
    assert by_latin["Leptobrachium guangxiense"].cn_name == "广西拟髭蟾"
