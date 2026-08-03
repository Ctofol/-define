import json

from app.schemas import SpeciesCandidate
from app.services.species_catalog_service import SpeciesCatalogService
from app.services.species_service import SpeciesService


def test_species_catalog_enriches_local_and_external_candidates(tmp_path):
    data_path = tmp_path / "species.json"
    data_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "test_deer",
                    "cn_name": "Test Deer",
                    "latin_name": "Cervus testus",
                    "category": "animal",
                    "taxon_group": "mammal",
                    "order": "Artiodactyla",
                    "family": "Cervidae",
                    "genus": "Cervus",
                    "protection_level": "national class II",
                    "source_scope": "local checklist",
                    "source_page": 1,
                    "recognition_tier": "candidate",
                    "habits": "forest edge",
                    "diet": "plants",
                    "features": ["spots"],
                    "habitat": "forest",
                    "monitoring_value": "monitoring",
                    "similar_species": [],
                    "review_tips": "check antlers and body pattern",
                    "tags": ["mammal"],
                }
            ]
        ),
        encoding="utf-8",
    )

    service = SpeciesCatalogService(SpeciesService(data_path))
    local, external = service.enrich_candidates(
        [
            SpeciesCandidate(label="Test Deer", confidence=0.8, source="test"),
            SpeciesCandidate(label="External Bird", confidence=0.7, source="test"),
        ]
    )

    assert local.species_id == "test_deer"
    assert local.region_status == "local_checklist"
    assert local.priority == "candidate"
    assert external.region_status == "out_of_catalog"
    assert "not_in_local_checklist" in external.review_flags


def test_species_catalog_review_reasons_prioritize_risky_candidates(tmp_path):
    data_path = tmp_path / "species.json"
    data_path.write_text("[]", encoding="utf-8")
    service = SpeciesCatalogService(SpeciesService(data_path))
    candidates = service.enrich_candidates([SpeciesCandidate(label="External Bird", confidence=0.55, source="test")])

    reasons = service.review_reasons(candidates, evidence_state="weak", review_status="needs_review", top_gap=1.0)

    assert "weak_reference_evidence" in reasons
    assert "not_in_local_checklist" in reasons


def test_species_catalog_does_not_flag_low_confidence_protected_candidate(tmp_path):
    data_path = tmp_path / "species.json"
    data_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "black_bear",
                    "cn_name": "黑熊",
                    "latin_name": "Ursus thibetanus",
                    "category": "animal",
                    "taxon_group": "兽类",
                    "order": "食肉目",
                    "family": "熊科",
                    "genus": "熊属",
                    "protection_level": "国家二级保护野生动物",
                    "source_scope": "local checklist",
                    "source_page": None,
                    "recognition_tier": "candidate",
                    "habits": "",
                    "diet": "",
                    "features": [],
                    "habitat": "",
                    "monitoring_value": "",
                    "similar_species": [],
                    "review_tips": "",
                    "tags": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    service = SpeciesCatalogService(SpeciesService(data_path))
    candidates = service.enrich_candidates([SpeciesCandidate(label="黑熊", confidence=0.42, source="test")])

    reasons = service.review_reasons(candidates, evidence_state="weak", review_status="low_confidence", top_gap=1.0)

    assert "low_confidence" in reasons
    assert "protected_species_candidate" not in reasons


def test_species_catalog_prefers_exact_species_name_over_similar_species(tmp_path):
    data_path = tmp_path / "species.json"
    data_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "cat",
                    "cn_name": "Cat",
                    "latin_name": "Felis catus",
                    "category": "animal",
                    "taxon_group": "mammal",
                    "order": "Carnivora",
                    "family": "Felidae",
                    "genus": "Felis",
                    "protection_level": "common",
                    "source_scope": "local checklist",
                    "source_page": None,
                    "recognition_tier": "candidate",
                    "habits": "active",
                    "diet": "meat",
                    "features": ["small cat"],
                    "habitat": "near people",
                    "monitoring_value": "comparison",
                    "similar_species": ["Civet"],
                    "review_tips": "check tail",
                    "tags": ["mammal"],
                },
                {
                    "species_id": "civet",
                    "cn_name": "Civet",
                    "latin_name": "Viverra testus",
                    "category": "animal",
                    "taxon_group": "mammal",
                    "order": "Carnivora",
                    "family": "Viverridae",
                    "genus": "Viverra",
                    "protection_level": "protected",
                    "source_scope": "local checklist",
                    "source_page": None,
                    "recognition_tier": "candidate",
                    "habits": "night",
                    "diet": "mixed",
                    "features": ["ringed tail"],
                    "habitat": "forest",
                    "monitoring_value": "priority",
                    "similar_species": [],
                    "review_tips": "check stripes",
                    "tags": ["mammal"],
                },
            ]
        ),
        encoding="utf-8",
    )

    service = SpeciesCatalogService(SpeciesService(data_path))
    candidate = service.enrich_candidate(SpeciesCandidate(label="Civet", confidence=0.8, source="test"))

    assert candidate.species_id == "civet"


def test_species_catalog_merges_pdf_catalog_when_configured(tmp_path):
    data_path = tmp_path / "species.json"
    data_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "curated_macaque",
                    "cn_name": "猕猴",
                    "latin_name": "Macaca mulatta",
                    "category": "animal",
                    "taxon_group": "兽类",
                    "order": "灵长目",
                    "family": "猴科",
                    "genus": "猕猴属",
                    "protection_level": "curated",
                    "source_scope": "manual review",
                    "source_page": None,
                    "recognition_tier": "high_demo",
                    "habits": "",
                    "diet": "",
                    "features": [],
                    "habitat": "",
                    "monitoring_value": "",
                    "similar_species": [],
                    "review_tips": "curated entry",
                    "tags": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    pdf_path = tmp_path / "pdf_species.json"
    pdf_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "macaca_mulatta",
                    "cn_name": "猕猴",
                    "latin_name": "Macaca mulatta",
                    "category": "animal",
                    "taxon_group": "兽类",
                    "order": "灵长目",
                    "family": "猴科",
                    "genus": "猕猴属",
                    "protection_level": "国家二级保护野生动物",
                    "source_scope": "广西国家重点保护陆生野生动物名录（2021年版）",
                    "source_page": 4,
                    "recognition_tier": "candidate",
                    "habits": "",
                    "diet": "",
                    "features": [],
                    "habitat": "",
                    "monitoring_value": "",
                    "similar_species": [],
                    "review_tips": "pdf entry",
                    "tags": [],
                },
                {
                    "species_id": "boiga_guangxiensis",
                    "cn_name": "广西林蛇",
                    "latin_name": "Boiga guangxiensis",
                    "category": "reptile_amphibian",
                    "taxon_group": "爬行与两栖类",
                    "order": "有鳞目",
                    "family": "游蛇科",
                    "genus": "林蛇属",
                    "protection_level": "广西重点保护野生动物",
                    "source_scope": "广西重点保护野生动物名录（2023年版）",
                    "source_page": 45,
                    "recognition_tier": "candidate",
                    "habits": "",
                    "diet": "",
                    "features": [],
                    "habitat": "",
                    "monitoring_value": "",
                    "similar_species": [],
                    "review_tips": "pdf entry",
                    "tags": [],
                },
            ]
        ),
        encoding="utf-8",
    )

    service = SpeciesCatalogService(SpeciesService(data_path), pdf_catalog_path=pdf_path)

    assert len(service.list_species()) == 2
    assert service.list_species(category="reptile_amphibian")[0].species_id == "boiga_guangxiensis"
    assert service.list_species(recognition_tier="high_demo")[0].species_id == "curated_macaque"
    assert service.get_species("boiga_guangxiensis").species_id == "boiga_guangxiensis"
    assert service.match("猕猴").species_id == "curated_macaque"
    assert service.match("Boiga guangxiensis").cn_name == "广西林蛇"


def test_default_catalog_loads_complete_plant_knowledge_entries():
    service = SpeciesCatalogService()
    plants = service.list_species(category="plant")

    assert len(plants) == 36
    assert service.get_species("cathaya_argyrophylla").cn_name == "银杉"
    assert service.match("Camellia petelotii").cn_name == "金花茶"
    assert all(item.recognition_tier == "knowledge_only" for item in plants)
    assert all(item.life_form and item.phenology and item.distribution for item in plants)
    assert all(item.features and item.habitat and item.review_tips for item in plants)
    assert all(item.source_urls for item in plants)
    assert all(not item.image_url or (item.image_source_url and item.image_license) for item in plants)


def test_default_catalog_reports_plant_readiness():
    status = SpeciesCatalogService().status()

    assert status["plant_catalog_detail"] == "36 plants / knowledge ready"
