from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CATALOG_PATH = Path("backend/app/data/pdf_species_catalog.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill habitat, habits, diet and recognition features for catalog entries.")
    parser.add_argument("--force", action="store_true", help="Regenerate profile fields even when they already exist.")
    args = parser.parse_args()

    species = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    updated = 0
    for item in species:
        before = snapshot(item)
        enrich_profile(item, force=args.force)
        if snapshot(item) != before:
            updated += 1
    CATALOG_PATH.write_text(json.dumps(species, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = [
        item
        for item in species
        if not item.get("habitat") or not item.get("habits") or not item.get("diet") or not item.get("features")
    ]
    print(f"updated={updated} missing_profile={len(missing)} catalog={CATALOG_PATH}")


def snapshot(item: dict[str, Any]) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        str(item.get("habitat") or ""),
        str(item.get("habits") or ""),
        str(item.get("diet") or ""),
        tuple(item.get("features") or []),
    )


def enrich_profile(item: dict[str, Any], force: bool = False) -> None:
    profile = profile_for(item)
    if force or not item.get("habitat"):
        item["habitat"] = profile["habitat"]
    if force or not item.get("habits"):
        item["habits"] = profile["habits"]
    if force or not item.get("diet"):
        item["diet"] = profile["diet"]
    if force or not item.get("features"):
        item["features"] = profile["features"]
    if force or not item.get("review_tips"):
        item["review_tips"] = profile["review_tips"]


def profile_for(item: dict[str, Any]) -> dict[str, Any]:
    category = value(item, "category")
    taxon_group = value(item, "taxon_group")
    order = value(item, "order")
    family = value(item, "family")
    genus = value(item, "genus")
    name = value(item, "cn_name")

    if category == "bird" or taxon_group == "鸟类":
        return bird_profile(name, order, family, genus)
    if category in {"reptile_amphibian", "reptile", "amphibian"} or "两栖" in taxon_group or "爬行" in taxon_group:
        return reptile_amphibian_profile(name, order, family, genus)
    if category in {"animal", "mammal"} or taxon_group in {"兽类", "哺乳动物"}:
        return mammal_profile(name, order, family, genus)
    return generic_profile(name, taxon_group, order, family, genus)


def bird_profile(name: str, order: str, family: str, genus: str) -> dict[str, Any]:
    if order == "鸡形目" or any(key in family for key in ["雉", "鸡"]):
        habitat = "山地森林、竹林、灌丛、草坡和林下地表环境，常在隐蔽处活动。"
        habits = "多在地面行走、觅食和短距离飞起，警觉性较高，常利用植被遮蔽。"
        diet = "杂食性，取食种子、果实、嫩叶、昆虫和其他小型无脊椎动物。"
        features = ["观察体型、尾羽长度和头颈部色彩", "注意雄雌羽色差异和体侧斑纹", "结合林下地面活动、短距离飞行和叫声复核"]
    elif order in {"鹰形目", "隼形目"} or any(key in family for key in ["鹰", "隼", "鹗"]):
        habitat = "森林边缘、山地、河谷、农田上空或开阔地带，常利用高处盘旋和停栖。"
        habits = "多单独活动，善于滑翔、盘旋和俯冲捕食，活动范围较大。"
        diet = "以小型鸟类、鼠类、爬行动物、两栖动物或昆虫等动物性食物为主。"
        features = ["观察翼形、尾形、体型比例和飞行姿态", "注意头部、腹面、翼下和尾部斑纹", "结合猛禽停栖、盘旋或捕食行为复核"]
    elif order == "鸮形目" or "鸮" in family:
        habitat = "森林、林缘、农田边缘、村落附近或山地环境，常依赖树洞、岩隙或隐蔽处停栖。"
        habits = "多夜行或晨昏活动，白天常隐蔽停栖，叫声和眼部反光有辅助识别价值。"
        diet = "以鼠类、小鸟、昆虫、蛙类和其他小型动物为食。"
        features = ["观察面盘、眼色、耳羽和头部轮廓", "注意体羽斑纹、站姿和夜间活动时间", "结合叫声、停栖位置和体型大小复核"]
    elif order in {"雁形目", "鹈形目", "鸻形目", "鹤形目", "鹳形目"} or any(key in family for key in ["鸭", "鸬鹚", "鹭", "鹤", "鸥", "鹬", "鹮", "鹳", "军舰鸟"]):
        habitat = "湖泊、河流、水库、湿地、滩涂或近海水域，常在开阔水面和岸边活动。"
        habits = "多在水边觅食、停歇或集群活动，迁徙季节和越冬期更容易被监测到。"
        diet = "以鱼类、水生无脊椎动物、软体动物、水草或植物种子等水域资源为食。"
        features = ["观察嘴形、颈长、体色和翼形", "注意飞行姿态、停栖位置和是否成群", "结合湿地或水域环境与相似水鸟对照"]
    elif order == "雀形目":
        habitat = "森林、林缘、灌丛、竹林、农田边缘或村落绿化环境，常在枝叶间活动。"
        habits = "多在树冠、灌丛或林缘觅食，常见鸣叫、跳跃、停栖和小群活动。"
        diet = "以昆虫、果实、花蜜、种子或嫩芽等为食，不同季节食性会变化。"
        features = ["观察体型大小、嘴形、冠羽和尾长", "注意头部、翼斑、腹色和鸣叫特征", "结合停栖高度、活动层位和同科相似鸟类对照"]
    else:
        habitat = "森林、灌丛、湿地、山地或农田边缘等自然或半自然环境。"
        habits = "多在适宜栖息地内觅食、停栖、繁殖或迁移，活动时间随物种和季节变化。"
        diet = "取食昆虫、果实、种子、小型动物或水域食物，需结合具体类群判断。"
        features = ["观察体型、体色、嘴形、翼形和尾形", "注意头部、腹面、翅斑和尾羽纹理", "结合栖息环境、行为和相似鸟类进行复核"]
    return profile(habitat, habits, diet, features, name)


def mammal_profile(name: str, order: str, family: str, genus: str) -> dict[str, Any]:
    if order == "灵长目" or any(key in family for key in ["猴", "长臂猿", "懒猴"]):
        habitat = "常绿阔叶林、季雨林、石山森林、沟谷林或林缘地带，依赖连续林冠和隐蔽生境。"
        habits = "多树栖或半树栖，常成群或小群活动，活动节律因物种而异。"
        diet = "以果实、嫩叶、花、种子为主，也会取食昆虫和其他小型动物。"
        features = ["观察面部颜色、尾长、体型和四肢比例", "注意群体数量、攀爬姿态和活动层位", "结合林冠环境、叫声和连续画面复核"]
    elif order == "食肉目" or any(key in family for key in ["犬", "猫", "熊", "鼬", "灵猫"]):
        habitat = "森林、灌丛、林缘、溪谷、山地坡地或农田边缘，常沿兽道和隐蔽路线活动。"
        habits = "多夜行或晨昏活动，行动隐蔽，常单独经过相机位。"
        diet = "以小型兽类、鸟类、爬行动物、昆虫、果实或腐肉等为食，不同类群差异较大。"
        features = ["观察体型、吻部、耳形、尾长和步态", "注意体色、斑纹、尾环或背线等稳定特征", "结合夜间活动、兽道位置和连续帧复核"]
    elif order in {"偶蹄目", "鲸偶蹄目"} or any(key in family for key in ["鹿", "牛", "猪", "麂"]):
        habitat = "森林、灌丛、草地、山地坡地和水源附近，常出现在林缘或兽道。"
        habits = "多晨昏活动，警觉性较高，常单独、小群或家族群经过相机位。"
        diet = "以嫩叶、嫩枝、草本植物、果实、根茎或农作物为食。"
        features = ["观察体型、蹄形、头部轮廓和尾部姿态", "注意角、獠牙、体侧斑纹或背线", "结合群体结构、行走姿态和栖息环境复核"]
    elif order in {"啮齿目", "兔形目"} or any(key in family for key in ["鼠", "兔", "松鼠", "豪猪"]):
        habitat = "森林下层、灌丛、草坡、农田边缘、洞穴或倒木附近。"
        habits = "多夜行或晨昏活动，体型较小，常快速穿行或在地面觅食。"
        diet = "以种子、果实、嫩叶、根茎、树皮或少量昆虫等为食。"
        features = ["观察体型、耳长、尾长和背腹颜色", "注意跳跃、奔跑、攀爬或钻洞行为", "结合尺度参照和连续帧避免与幼体混淆"]
    else:
        habitat = "森林、灌丛、草地、山地、溪谷或农田边缘等自然和半自然生境。"
        habits = "多在隐蔽环境中觅食、移动或停留，活动时间需结合相机记录判断。"
        diet = "食性随类群变化，可包括植物、果实、昆虫、小型动物或杂食性资源。"
        features = ["观察体型、头部轮廓、耳形、尾长和步态", "注意体色、斑纹、背线和四肢比例", "结合活动时间、栖息环境和连续画面复核"]
    return profile(habitat, habits, diet, features, name)


def reptile_amphibian_profile(name: str, order: str, family: str, genus: str) -> dict[str, Any]:
    if order == "无尾目" or any(key in family for key in ["蛙", "蟾", "树蛙", "姬蛙"]):
        habitat = "山地溪流、林下湿地、稻田、池塘、沟渠或落叶层等潮湿环境，繁殖期常靠近水体。"
        habits = "多在夜间、雨后或高湿环境活动，常以鸣叫、跳跃和隐蔽停栖被发现。"
        diet = "以昆虫、蜘蛛、蚯蚓和其他小型无脊椎动物为食。"
        features = ["观察体型、背部颜色、疣粒或皮肤褶皱", "注意鼓膜、吻端、指趾吸盘和蹼的形态", "结合鸣声、水体类型和发现位置复核"]
    elif order == "有鳞目" or any(key in family for key in ["蛇", "蜥", "壁虎", "石龙子"]):
        habitat = "森林、灌丛、草坡、石缝、溪边、农田边缘或村落周边等温暖隐蔽环境。"
        habits = "多在白天晒背或夜间觅食，遇干扰常快速逃逸、静伏或进入缝隙。"
        diet = "以昆虫、蛙类、蜥蜴、小型鸟兽、卵或其他小型动物为食，具体取决于类群。"
        features = ["观察体长、头形、鳞片质感和体色斑纹", "注意尾长、四肢有无、背线和腹面颜色", "结合活动环境和连续画面区分近似种"]
    elif order in {"龟鳖目", "龟鳖目"} or any(key in family for key in ["龟", "鳖"]):
        habitat = "河流、溪沟、池塘、水库、湿地或岸边缓流环境，常在水陆交界活动。"
        habits = "多在水中觅食，也会在岸边晒背、产卵或隐蔽停留。"
        diet = "杂食性，取食水生植物、鱼虾、螺蚌、昆虫、腐殖质或小型动物。"
        features = ["观察背甲形状、腹甲颜色和头颈斑纹", "注意趾蹼、吻端形态和甲壳边缘", "结合水域类型、晒背姿态和尺度复核"]
    else:
        habitat = "林下、溪流、湿地、草坡、石缝或农田边缘等温暖潮湿或隐蔽环境。"
        habits = "活动受温度、湿度和季节影响明显，常在雨后、夜间或隐蔽处出现。"
        diet = "以昆虫、小型无脊椎动物或小型脊椎动物为主，部分种类杂食。"
        features = ["观察体型、体色、皮肤或鳞片质感", "注意头部、四肢、尾部和背腹斑纹", "结合微生境、活动时间和相似种进行复核"]
    return profile(habitat, habits, diet, features, name)


def generic_profile(name: str, taxon_group: str, order: str, family: str, genus: str) -> dict[str, Any]:
    habitat = "常见于本类群适宜的自然或半自然生境，具体环境需结合调查地点复核。"
    habits = "活动时间、行为方式和栖息层位随物种和季节变化，建议结合连续观测记录判断。"
    diet = "食性资料需结合类群和地区资料进一步核对。"
    features = ["观察体型、体色和稳定斑纹", "注意头部、四肢、尾部或附属结构", "结合生境、行为和相似物种对照复核"]
    return profile(habitat, habits, diet, features, name)


def profile(habitat: str, habits: str, diet: str, features: list[str], name: str) -> dict[str, Any]:
    return {
        "habitat": habitat,
        "habits": habits,
        "diet": diet,
        "features": features,
        "review_tips": f"复核{name}时优先查看原图清晰度、拍摄地点、活动环境和相似物种差异。",
    }


def value(item: dict[str, Any], key: str) -> str:
    return str(item.get(key) or "").strip()


if __name__ == "__main__":
    main()
