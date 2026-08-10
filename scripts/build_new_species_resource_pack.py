from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import SpeciesEntry  # noqa: E402
from app.services.species_catalog_service import SpeciesCatalogService  # noqa: E402


SOURCE_SCOPE = "GBIF Backbone Taxonomy；广西常见物种新增资源包（基础资料，导入前请管理员复核）"


def gbif_url(latin_name: str) -> str:
    return f"https://www.gbif.org/species/search?q={quote(latin_name)}"


def record(
    species_id: str,
    cn_name: str,
    latin_name: str,
    category: str,
    taxon_group: str,
    order: str,
    family: str,
    genus: str,
    habits: str,
    diet: str,
    features: list[str],
    habitat: str,
    monitoring_value: str,
    review_tips: str,
    *,
    life_form: str = "",
    phenology: str = "",
    distribution: str = "广西及华南适生区域，具体县域记录需结合调查资料复核。",
) -> dict[str, object]:
    return {
        "species_id": species_id,
        "cn_name": cn_name,
        "latin_name": latin_name,
        "category": category,
        "taxon_group": taxon_group,
        "order": order,
        "family": family,
        "genus": genus,
        "protection_level": "一般物种（保护等级请按最新名录复核）",
        "source_scope": SOURCE_SCOPE,
        "source_page": None,
        "recognition_tier": "candidate",
        "habits": habits,
        "diet": diet,
        "features": features,
        "habitat": habitat,
        "monitoring_value": monitoring_value,
        "similar_species": [],
        "review_tips": review_tips,
        "tags": [taxon_group, family, "新增候选", "待复核"],
        "life_form": life_form,
        "phenology": phenology,
        "distribution": distribution,
        "source_urls": [gbif_url(latin_name)],
        "image_url": None,
        "image_source_url": None,
        "image_author": "",
        "image_license": "",
        "image_basis_of_record": "",
        "rejected_image_sources": [],
    }


ROWS = [
    record("callosciurus_erythraeus", "赤腹松鼠", "Callosciurus erythraeus", "animal", "兽类", "啮齿目", "松鼠科", "丽松鼠属", "昼行性，善于在树冠和林缘活动。", "以果实、种子、嫩芽为主。", ["腹部常呈红褐色", "尾蓬松且较长", "背部灰褐至橄榄褐色"], "常绿阔叶林、次生林、果园和城市绿地。", "适合监测林缘小型兽类群落和栖息地变化。", "重点核对腹部颜色、尾形及拍摄地点。"),
    record("tamiops_swinhoei", "珀氏长吻松鼠", "Tamiops swinhoei", "animal", "兽类", "啮齿目", "松鼠科", "长吻松鼠属", "昼行性，常沿树干快速攀爬。", "取食种子、果实、嫩芽及少量昆虫。", ["背部具有纵向浅色条纹", "体型小巧", "吻部较尖"], "山地森林、竹林和林缘灌丛。", "可反映森林垂直结构和小型兽类活动变化。", "避免与花鼠及其他具有背纹的小型松鼠混淆。"),
    record("micromys_minutus", "巢鼠", "Micromys minutus", "animal", "兽类", "啮齿目", "鼠科", "巢鼠属", "多在高草和芦苇间攀爬并营造球形巢。", "以种子、谷物和小型昆虫为食。", ["体型很小", "尾具缠绕和攀附能力", "常活动于高草茎秆间"], "湿地边缘、草丛、农田和芦苇地。", "适合指示湿地边缘植被完整性。", "需结合体型比例、尾部姿态和生境复核。"),
    record("copsychus_saularis", "鹊鸲", "Copsychus saularis", "bird", "鸟类", "雀形目", "鹟科", "鹊鸲属", "常单独或成对活动，鸣声多变，喜在开阔处停栖。", "以昆虫和其他小型无脊椎动物为主。", ["黑白对比明显", "尾较长且常上翘", "翼部具有醒目白斑"], "村落、园林、林缘和低海拔次生林。", "可用于常见鸟类多样性和城乡生境变化监测。", "雌雄羽色深浅不同，应结合翼斑和尾形确认。"),
    record("spilopelia_chinensis", "珠颈斑鸠", "Spilopelia chinensis", "bird", "鸟类", "鸽形目", "鸠鸽科", "珠颈斑鸠属", "多在地面觅食，也常停栖于电线和乔木。", "以草籽、谷物和植物果实为主。", ["颈侧具有黑底白点斑块", "体羽灰褐色", "尾较长且末端具白色"], "农田、村落、公园、林缘和城市绿地。", "适合记录城乡常见鸟类分布和季节变化。", "重点查看颈侧珠状斑和尾部白端。"),
    record("passer_montanus", "树麻雀", "Passer montanus", "bird", "鸟类", "雀形目", "雀科", "麻雀属", "群居性强，常在人类聚居地附近活动。", "以种子和谷物为主，繁殖期也取食昆虫。", ["栗色头顶", "白色面颊带黑色耳斑", "喉部具有黑斑"], "村庄、城镇、农田、园林和建筑周边。", "可作为城乡鸟类群落和人类活动强度的基础监测对象。", "与其他麻雀类区分时重点看面颊黑斑。"),
    record("ficus_microcarpa", "小叶榕", "Ficus microcarpa", "plant", "植物", "蔷薇目", "桑科", "榕属", "常绿乔木，根系发达，老树可形成气生根。", "", ["叶片革质且全缘", "隐头花序形成榕果", "树冠宽广，常见气生根"], "低海拔常绿林、村落、公园和道路绿化带。", "可用于古树、城市绿化和榕树生态关系监测。", "需与高山榕等近似榕属植物比较叶形和榕果。", life_form="常绿乔木", phenology="花果期随地区和气候变化，可多次结果。"),
    record("broussonetia_papyrifera", "构树", "Broussonetia papyrifera", "plant", "植物", "蔷薇目", "桑科", "构属", "落叶乔木，生长快，耐贫瘠和干扰。", "", ["叶形变化大，可全缘或分裂", "叶面粗糙", "聚合果成熟时橙红色"], "林缘、荒地、路旁、村落及受干扰生境。", "可作为生境干扰、植被恢复和乡土植物分布的记录对象。", "幼叶变异大，应结合树皮、叶面质感和果实确认。", life_form="落叶乔木", phenology="春季开花，夏秋季果实成熟。"),
    record("liquidambar_formosana", "枫香树", "Liquidambar formosana", "plant", "植物", "虎耳草目", "枫香科", "枫香树属", "落叶乔木，秋冬季叶色常转红或黄。", "", ["叶片通常三裂", "果序球形且具刺状结构", "树干通直"], "山地常绿落叶阔叶混交林、林缘和道路两侧。", "适合监测季相变化、森林更新和乡土乔木分布。", "注意与枫树类区分，枫香叶互生且果序球形。", life_form="落叶乔木", phenology="春季开花，秋冬季果熟并变色。"),
    record("schima_superba", "木荷", "Schima superba", "plant", "植物", "杜鹃花目", "山茶科", "木荷属", "常绿乔木，耐瘠薄，常为亚热带森林优势或伴生树种。", "", ["叶片革质有细锯齿", "花白色且雄蕊多数", "蒴果近球形"], "常绿阔叶林、山坡林地和防火林带。", "可用于森林恢复、群落演替和防火林带调查。", "需结合叶缘锯齿、花和蒴果与山茶科近似种区分。", life_form="常绿乔木", phenology="夏季开花，秋冬季果实成熟。"),
    record("cyclobalanopsis_glauca", "青冈", "Cyclobalanopsis glauca", "plant", "植物", "壳斗目", "壳斗科", "青冈属", "常绿乔木，是亚热带常绿阔叶林常见组成树种。", "", ["叶背常呈灰白色", "叶缘中上部具锯齿", "壳斗具同心环状纹"], "丘陵和山地常绿阔叶林。", "适合监测常绿阔叶林结构、更新和栖息地质量。", "鉴定应重点查看叶背颜色和壳斗环纹。", life_form="常绿乔木", phenology="春季开花，秋季至翌年果实成熟。"),
    record("melia_azedarach", "苦楝", "Melia azedarach", "plant", "植物", "无患子目", "楝科", "楝属", "落叶乔木，适应性较强，常见于村落和道路周边。", "", ["二至三回羽状复叶", "花淡紫色", "核果成熟后呈黄色并可宿存"], "村落、路旁、河谷、林缘和低海拔疏林。", "可用于乡土树种、道路绿化和物候变化监测。", "注意果实有毒，不应根据可食性描述；鉴定结合复叶和黄色核果。", life_form="落叶乔木", phenology="春季开花，秋冬季果实成熟并常宿存。"),
]


def main() -> None:
    current = SpeciesCatalogService().list_species()
    current_ids = {item.species_id for item in current}
    current_names = {item.cn_name for item in current}
    current_latin = {item.latin_name.casefold() for item in current if item.latin_name}

    entries = [SpeciesEntry.model_validate(row) for row in ROWS]
    conflicts = [
        item.species_id
        for item in entries
        if item.species_id in current_ids
        or item.cn_name in current_names
        or (item.latin_name and item.latin_name.casefold() in current_latin)
    ]
    if conflicts:
        raise SystemExit(f"existing catalog conflicts: {', '.join(conflicts)}")
    if len({item.species_id for item in entries}) != len(entries):
        raise SystemExit("duplicate species_id in new resource pack")

    output = ROOT / "exports" / "new_species_resources_12.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"species": [item.model_dump(mode="json") for item in entries]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(f"created {output} with {len(entries)} new species; catalog size after import: {len(current) + len(entries)}")


if __name__ == "__main__":
    main()
