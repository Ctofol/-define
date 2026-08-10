from __future__ import annotations

import argparse
import csv
import json
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from PIL import Image


GBIF_API = "https://api.gbif.org/v1"
DEFAULT_LICENSES = {"CC0_1_0", "CC_BY_4_0", "CC_BY_NC_4_0"}
DEFAULT_COUNTRIES = {"CN", "HK", "TW", "VN", "LA", "MM", "TH"}
DEFAULT_SKIP_KEYWORDS = {
    "cage",
    "caged",
    "captive",
    "carcass",
    "dead",
    "enclosure",
    "footprint",
    "museum",
    "roadkill",
    "scat",
    "skull",
    "specimen",
    "taxidermy",
    "track",
    "tracks",
    "zoo",
    "动物园",
    "标本",
    "尸体",
    "笼",
    "笼舍",
    "粪便",
    "圈养",
    "足迹",
    "路杀",
    "骨骼",
}
EXCLUDED_BASIS_OF_RECORD = {
    "FOSSIL_SPECIMEN",
    "MATERIAL_SAMPLE",
    "MATERIAL_CITATION",
    "PRESERVED_SPECIMEN",
}
ALLOWED_MEDIA_LICENSE_MARKERS = {
    "creativecommons.org/licenses/by/4.0",
    "creativecommons.org/licenses/by-nc/4.0",
    "creativecommons.org/publicdomain/zero/1.0",
    "cc0_1_0",
    "cc_by_4_0",
    "cc_by_nc_4_0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download GBIF reference images into the review pool.")
    parser.add_argument("--species-file", type=Path, default=Path("backend") / "app" / "data" / "species_knowledge.json")
    parser.add_argument("--output-root", type=Path, default=Path("reference_species") / "待复核" / "gbif")
    parser.add_argument("--species", nargs="*", default=None, help="Optional subset of Chinese species names.")
    parser.add_argument("--max-per-species", type=int, default=5)
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.4)
    parser.add_argument("--min-width", type=int, default=400)
    parser.add_argument("--min-height", type=int, default=300)
    parser.add_argument("--licenses", nargs="*", default=sorted(DEFAULT_LICENSES))
    parser.add_argument("--countries", nargs="*", default=sorted(DEFAULT_COUNTRIES), help="GBIF country codes to prioritize.")
    parser.add_argument("--skip-keywords", nargs="*", default=sorted(DEFAULT_SKIP_KEYWORDS))
    parser.add_argument("--no-keyword-filter", action="store_true")
    return parser.parse_args()


def load_species(species_file: Path, requested_names: set[str] | None) -> list[dict[str, str]]:
    raw = json.loads(species_file.read_text(encoding="utf-8"))
    rows = [item for item in raw if item.get("category") == "animal" and item.get("latin_name") and item.get("cn_name")]
    if requested_names is None:
        return rows
    return [item for item in rows if item["cn_name"] in requested_names]


def http_json(url: str, timeout: int, retries: int = 3, sleep_seconds: float = 0.5) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "CodexGBIFDownloader/1.0"})
    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            last_exc = exc
            if attempt + 1 < max(1, retries):
                time.sleep(sleep_seconds * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def http_bytes(url: str, timeout: int, retries: int = 3, sleep_seconds: float = 0.5) -> bytes:
    request = Request(url, headers={"User-Agent": "CodexGBIFDownloader/1.0"})
    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_exc = exc
            if attempt + 1 < max(1, retries):
                time.sleep(sleep_seconds * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def gbif_species_match(latin_name: str, timeout: int, retries: int) -> dict[str, object] | None:
    query = urlencode({"name": latin_name})
    payload = http_json(f"{GBIF_API}/species/match?{query}", timeout, retries=retries)
    if payload.get("matchType") == "NONE":
        return None
    return payload


def gbif_occurrence_media(taxon_key: int, offset: int, limit: int, licenses: list[str], countries: list[str], timeout: int, retries: int) -> dict[str, object]:
    params = [
        ("taxon_key", str(taxon_key)),
        ("media_type", "StillImage"),
        ("limit", str(limit)),
        ("offset", str(offset)),
    ]
    params.extend(("license", license_name) for license_name in licenses)
    params.extend(("country", country_code) for country_code in countries)
    query = urlencode(params)
    return http_json(f"{GBIF_API}/occurrence/search?{query}", timeout, retries=retries)


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value).strip("._")
    return cleaned or "image"


def extract_image_url(media_item: dict[str, object]) -> str | None:
    for key in ("identifier", "references", "image", "image_url"):
        value = media_item.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None


def is_allowed_media_license(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().lower()
    return any(marker in normalized for marker in ALLOWED_MEDIA_LICENSE_MARKERS)


def searchable_metadata_text(item: dict[str, object], media_item: dict[str, object] | None = None) -> str:
    fields = [
        item.get("basisOfRecord"),
        item.get("occurrenceRemarks"),
        item.get("organismRemarks"),
        item.get("fieldNotes"),
        item.get("samplingProtocol"),
        item.get("dynamicProperties"),
        item.get("habitat"),
        item.get("locality"),
        item.get("establishmentMeans"),
    ]
    if media_item:
        fields.extend(
            [
                media_item.get("title"),
                media_item.get("description"),
                media_item.get("format"),
                media_item.get("type"),
            ]
        )
    return " ".join(str(value) for value in fields if value).lower()


def is_excluded_by_occurrence_metadata(item: dict[str, object], media_item: dict[str, object] | None, skip_keywords: list[str]) -> bool:
    basis = str(item.get("basisOfRecord") or "").upper()
    if basis in EXCLUDED_BASIS_OF_RECORD:
        return True
    text = searchable_metadata_text(item, media_item)
    return any(keyword.lower() in text for keyword in skip_keywords if keyword.strip())


def verify_image(data: bytes, min_width: int, min_height: int) -> bool:
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
    return width >= min_width and height >= min_height


def download_species(species: dict[str, str], args: argparse.Namespace) -> int:
    cn_name = species["cn_name"]
    latin_name = species["latin_name"]
    try:
        taxon = gbif_species_match(latin_name, args.timeout, args.retries)
    except Exception as exc:  # noqa: BLE001
        print(f"[skip] {cn_name}: GBIF species match error: {exc.__class__.__name__}: {exc}")
        return 0
    if not taxon or not taxon.get("usageKey"):
        print(f"[skip] {cn_name}: GBIF species match failed")
        return 0

    species_dir = args.output_root / cn_name
    species_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = species_dir / "metadata.csv"
    existing = set()
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            existing = {row.get("filename", "") for row in reader if row.get("filename")}
            existing_gbif_ids = {row.get("gbif_id", "") for row in reader if row.get("gbif_id")}
    else:
        existing_gbif_ids = set()

    downloaded = 0
    existing_image_count = len([path for path in species_dir.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
    if existing_image_count >= args.max_per_species:
        print(f"[skip] {cn_name}: already has {existing_image_count} candidate images")
        return 0

    target_new_count = args.max_per_species - existing_image_count
    offset = 0
    page_size = 20
    rows: list[dict[str, str]] = []
    searched_pages = 0
    while downloaded < target_new_count and searched_pages < args.max_pages:
        try:
            payload = gbif_occurrence_media(int(taxon["usageKey"]), offset, page_size, args.licenses, args.countries, args.timeout, args.retries)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip-page] {cn_name}: offset={offset} -> {exc.__class__.__name__}: {exc}")
            offset += page_size
            continue
        searched_pages += 1
        results = payload.get("results", [])
        if not results:
            break

        for item in results:
            if downloaded >= target_new_count:
                break

            media_items = item.get("media") or []
            if not isinstance(media_items, list):
                continue

            image_url = None
            selected_media_item: dict[str, object] | None = None
            for media_item in media_items:
                if not isinstance(media_item, dict):
                    continue
                if not is_allowed_media_license(media_item.get("license") or item.get("license")):
                    continue
                image_url = extract_image_url(media_item)
                if image_url:
                    selected_media_item = media_item
                    break
            if not image_url or selected_media_item is None:
                continue
            if not args.no_keyword_filter and is_excluded_by_occurrence_metadata(item, selected_media_item, args.skip_keywords):
                continue

            occurrence_id = str(item.get("key") or item.get("gbifID") or item.get("occurrenceID") or "unknown")
            if occurrence_id in existing_gbif_ids:
                continue
            filename = safe_filename(f"{cn_name}_GBIF_{occurrence_id}.jpg")
            if filename in existing:
                continue

            try:
                data = http_bytes(image_url, args.timeout, retries=args.retries)
                if not verify_image(data, args.min_width, args.min_height):
                    continue
            except Exception as exc:  # noqa: BLE001
                print(f"[skip] {cn_name}: {image_url} -> {exc.__class__.__name__}: {exc}")
                continue

            (species_dir / filename).write_bytes(data)
            rows.append(
                {
                    "filename": filename,
                    "species": cn_name,
                    "scientific_name": latin_name,
                    "source": "GBIF",
                    "author": str(item.get("recordedBy") or selected_media_item.get("creator") or ""),
                    "license": str(selected_media_item.get("license") or item.get("license") or ""),
                    "source_url": f"https://www.gbif.org/occurrence/{item.get('gbifID')}",
                    "gbif_id": occurrence_id,
                    "country": str(item.get("country") or ""),
                    "locality": str(item.get("locality") or item.get("stateProvince") or ""),
                    "sex": str(item.get("sex") or ""),
                    "basis_of_record": str(item.get("basisOfRecord") or ""),
                    "event_date": str(item.get("eventDate") or ""),
                    "media_title": str(selected_media_item.get("title") or ""),
                    "media_description": str(selected_media_item.get("description") or ""),
                    "note": f"GBIF candidate from usageKey={taxon['usageKey']}; keyword_filter={'off' if args.no_keyword_filter else 'on'}",
                }
            )
            downloaded += 1
            existing.add(filename)
            existing_gbif_ids.add(occurrence_id)
            time.sleep(args.sleep)

        offset += page_size
        if offset >= int(payload.get("count") or 0):
            break

    if rows:
        write_metadata(metadata_path, rows, append=True)
    print(f"[done] {cn_name}: {downloaded} images")
    return downloaded


def write_metadata(path: Path, rows: list[dict[str, str]], append: bool) -> None:
    fieldnames = [
        "filename",
        "species",
        "scientific_name",
        "source",
        "author",
        "license",
        "source_url",
        "gbif_id",
        "country",
        "locality",
        "sex",
        "basis_of_record",
        "event_date",
        "media_title",
        "media_description",
        "note",
    ]
    if append and path.exists():
        existing_rows = []
        with path.open("r", encoding="utf-8", newline="") as file:
            existing_rows = list(csv.DictReader(file))
        seen = {row["filename"] for row in existing_rows if row.get("filename")}
        merged = existing_rows + [row for row in rows if row["filename"] not in seen]
    else:
        merged = rows
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fieldnames} for row in merged])


def main() -> int:
    args = parse_args()
    requested_names = set(args.species) if args.species else None
    species_rows = load_species(args.species_file, requested_names)
    if not species_rows:
        raise ValueError("no target species found")

    total = 0
    for species in species_rows:
        total += download_species(species, args)
    print(f"downloaded {total} images total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
