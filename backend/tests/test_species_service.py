from app.services.species_service import SpeciesService


def test_species_service_loads_initial_scope():
    service = SpeciesService()
    species = service.list_species()

    assert len(species) == 15
    assert service.get_species("macaque").cn_name == "猕猴"
    assert service.get_species("white_headed_langur").protection_level == "国家一级保护野生动物"
    assert all(item.habits and item.diet for item in species)


def test_species_service_filters_by_recognition_tier():
    service = SpeciesService()
    high_demo_species = service.list_species(recognition_tier="high_demo")

    assert {item.species_id for item in high_demo_species} >= {
        "macaque",
        "leopard_cat",
        "red_fox",
        "wild_boar",
        "sika_deer",
    }


def test_priority_species_taxonomy_stays_on_checked_names():
    service = SpeciesService()

    checked_names = {
        "macaque": ("猕猴", "Macaca mulatta", "灵长目", "猴科", "国家二级保护野生动物"),
        "leopard_cat": ("豹猫", "Prionailurus bengalensis", "食肉目", "猫科", "国家二级保护野生动物"),
        "red_fox": ("赤狐", "Vulpes vulpes", "食肉目", "犬科", "广西及周边监测关注物种"),
        "sika_deer": ("梅花鹿", "Cervus nippon", "偶蹄目", "鹿科", "国家一级保护野生动物"),
        "sambar_deer": ("水鹿", "Rusa unicolor", "偶蹄目", "鹿科", "国家二级保护野生动物"),
        "chinese_goral": ("中华斑羚", "Naemorhedus griseus", "偶蹄目", "牛科", "国家二级保护野生动物"),
        "asiatic_black_bear": ("黑熊", "Ursus thibetanus", "食肉目", "熊科", "国家二级保护野生动物"),
        "yellow_throated_marten": ("黄喉貂", "Martes flavigula", "食肉目", "鼬科", "国家二级保护野生动物"),
        "large_indian_civet": ("大灵猫", "Viverra zibetha", "食肉目", "灵猫科", "国家一级保护野生动物"),
        "white_headed_langur": ("白头叶猴", "Trachypithecus leucocephalus", "灵长目", "猴科", "国家一级保护野生动物"),
        "chinese_pangolin": ("中华穿山甲", "Manis pentadactyla", "鳞甲目", "鲮鲤科", "国家一级保护野生动物"),
    }

    for species_id, expected in checked_names.items():
        species = service.get_species(species_id)
        assert species is not None
        assert (
            species.cn_name,
            species.latin_name,
            species.order,
            species.family,
            species.protection_level,
        ) == expected


def test_protected_animals_have_review_fields():
    service = SpeciesService()
    protected_animals = [
        item
        for item in service.list_species(category="animal")
        if item.protection_level.startswith("国家")
    ]

    assert protected_animals
    assert all(item.latin_name for item in protected_animals)
    assert all(item.source_scope for item in protected_animals)
    assert all(item.source_page for item in protected_animals if item.protection_level.startswith("国家"))
    assert all(item.features and item.habitat and item.review_tips for item in protected_animals)
