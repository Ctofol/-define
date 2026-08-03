from app.services.reference_sample_service import ReferenceSampleService


def test_reference_sample_service_lists_core_species():
    service = ReferenceSampleService()
    payload = service.list_species()

    folders = {item.folder_name for item in payload.species}
    assert {"中华斑羚", "中华穿山甲", "大灵猫", "梅花鹿", "猕猴", "白头叶猴", "豹猫", "赤狐", "野猪", "黑熊"}.issubset(folders)


def test_reference_sample_service_counts_samples():
    service = ReferenceSampleService()

    assert service.get_species("水鹿").image_count >= 10
    assert service.get_species("黄喉貂").image_count >= 10
    assert service.get_species("大灵猫").image_count >= 10
    assert service.get_species("黑熊").image_count >= 10
    assert service.get_species("中华穿山甲").image_count >= 8


def test_reference_sample_service_keeps_core_species_separate_from_operational_folders():
    service = ReferenceSampleService()
    payload = service.list_species()
    folders = {item.folder_name for item in payload.species}

    protected_species = {"中华斑羚", "中华穿山甲", "亚洲黑熊", "大灵猫", "梅花鹿", "水鹿", "猕猴", "白头叶猴", "豹猫", "赤狐", "黄喉貂"}
    operational_folders = {"empty", "human", "vehicle"}

    assert protected_species.issubset(folders)
    assert operational_folders.issubset(folders)
    assert protected_species.isdisjoint(operational_folders)


def test_reference_sample_service_reads_legacy_gbif_rows(tmp_path):
    folder = tmp_path / "豹猫"
    folder.mkdir()
    (folder / "豹猫_未知_001.jpg").write_bytes(b"placeholder")
    (folder / "metadata.csv").write_text(
        "\n".join(
            [
                "filename,species,source,author,license,location,note",
                "豹猫_未知_001.jpg,豹猫,Prionailurus bengalensis,GBIF/iNaturalist,observer,http://creativecommons.org/licenses/by/4.0/,https://www.gbif.org/occurrence/1,1,China,Guangxi,unknown,legacy row",
            ]
        ),
        encoding="utf-8",
    )

    service = ReferenceSampleService(root_path=tmp_path)
    entry = service.get_species("豹猫")

    assert entry is not None
    assert entry.samples[0].source == "GBIF/iNaturalist"
    assert entry.samples[0].author == "observer"
    assert entry.samples[0].license == "http://creativecommons.org/licenses/by/4.0/"


def test_reference_sample_service_ignores_pdf_working_asset_folders(tmp_path):
    species_folder = tmp_path / "蜂猴"
    species_folder.mkdir()
    (species_folder / "蜂猴_001.jpg").write_bytes(b"placeholder")

    pdf_work_folder = tmp_path / "pdf_guangxi_species_images_v2"
    pdf_work_folder.mkdir()
    (pdf_work_folder / "metadata.csv").write_text("filename,cn_name\nsample.jpg,蜂猴\n", encoding="utf-8")

    service = ReferenceSampleService(root_path=tmp_path)
    payload = service.list_species()
    folders = {item.folder_name for item in payload.species}

    assert "蜂猴" in folders
    assert "pdf_guangxi_species_images_v2" not in folders
    assert service.get_species("pdf_guangxi_species_images_v2") is None


def test_reference_sample_service_lists_pdf_weak_reference_samples(tmp_path):
    pdf_work_folder = tmp_path / "pdf_guangxi_species_images_v2"
    crops_folder = pdf_work_folder / "crops"
    crops_folder.mkdir(parents=True)
    (crops_folder / "sample.jpg").write_bytes(b"placeholder")
    (pdf_work_folder / "metadata.csv").write_text(
        "\n".join(
            [
                "filename,species_id,cn_name,latin_name,category,taxon_group,protection_level",
                "sample.jpg,nycticebus_bengalensis,蜂猴,Nycticebus bengalensis,animal,兽类,国家一级保护野生动物",
            ]
        ),
        encoding="utf-8",
    )

    service = ReferenceSampleService(root_path=tmp_path)
    payload = service.list_pdf_weak_reference_species()

    assert len(payload.species) == 1
    entry = payload.species[0]
    assert entry.folder_name == "蜂猴"
    assert entry.image_count == 1
    assert entry.cover_url.startswith("/media/reference-species/pdf_guangxi_species_images_v2/crops/sample.jpg?v=")
    assert entry.samples[0].source == "广西重点保护野生动物口袋书"
    assert entry.samples[0].license == "reference_only"


def test_reference_sample_service_hides_pdf_quality_review_items(tmp_path):
    pdf_work_folder = tmp_path / "pdf_guangxi_species_images_v2"
    crops_folder = pdf_work_folder / "crops"
    crops_folder.mkdir(parents=True)
    (crops_folder / "good.jpg").write_bytes(b"placeholder")
    (crops_folder / "bad.jpg").write_bytes(b"placeholder")
    (pdf_work_folder / "metadata.csv").write_text(
        "\n".join(
            [
                "filename,species_id,cn_name,latin_name,category,taxon_group,protection_level",
                "good.jpg,good_species,好图,Good species,animal,兽类,广西重点保护野生动物",
                "bad.jpg,bad_species,截图问题图,Bad species,animal,兽类,广西重点保护野生动物",
            ]
        ),
        encoding="utf-8",
    )
    (pdf_work_folder / "quality_flags.csv").write_text(
        "\n".join(
            [
                "filename,cn_name,latin_name,quality_status,score,reasons,note",
                "good.jpg,好图,Good species,display,0,,",
                "bad.jpg,截图问题图,Bad species,needs_review,5,top_residue,hide from gallery",
            ]
        ),
        encoding="utf-8",
    )

    service = ReferenceSampleService(root_path=tmp_path)
    payload = service.list_pdf_weak_reference_species()

    assert [entry.folder_name for entry in payload.species] == ["好图"]
def test_reference_sample_service_lists_knowledge_open_set_samples(tmp_path):
    image_folder = tmp_path / "_supplement_candidates" / "viverrids_quality_pass" / "果子狸"
    image_folder.mkdir(parents=True)
    image_path = image_folder / "果子狸_GBIF_1.jpg"
    image_path.write_bytes(b"placeholder")
    candidates_path = tmp_path / "knowledge_open_set_candidates.csv"
    candidates_path.write_text(
        "\n".join(
            [
                "species,filename,scientific_name,source,author,license,copied_path",
                f"果子狸,果子狸_GBIF_1.jpg,Paguma larvata,GBIF,observer,http://creativecommons.org/licenses/by/4.0/,{image_path}",
            ]
        ),
        encoding="utf-8",
    )

    service = ReferenceSampleService(root_path=tmp_path, open_set_candidates_path=candidates_path)
    payload = service.list_knowledge_open_set_species()

    assert len(payload.species) == 1
    entry = payload.species[0]
    assert entry.folder_name == "果子狸"
    assert entry.image_count == 1
    assert entry.samples[0].subspecies == "Paguma larvata"
    assert entry.samples[0].source == "GBIF"
    assert entry.cover_url.startswith("/media/reference-species/_supplement_candidates/viverrids_quality_pass/")
