from __future__ import annotations

"""Fill missing plant-card covers from Wikimedia Commons with reusable licences."""

import argparse
import html
import json
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image


API = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
BAD_TERMS = (
    "herbarium", "specimen", "sheet", "drawing", "illustration", "map", "people", "person",
    "dried", "drying", "tea", "food", "spice", "powder", "seed packet", "label",
    "preserved", "type material", "museum", "colour chart", "color chart", "scale bar",
    "botanic garden", "botanical garden", "plant label", "information board", "signboard",
    "missing image", "immagine mancante", "no image available", "placeholder",
    "journal", "article", "phylogeny", "classification", ".pdf", "publication",
)
ALLOWED_LICENSES = ("cc0", "cc-by", "cc by", "cc-by-sa", "cc by-sa")


def get(url: str, timeout: int) -> bytes:
    return urlopen(Request(url, headers={"User-Agent": "WildlifePlantKnowledge/1.0"}), timeout=timeout).read()


def search(name: str, timeout: int, rejected_sources: list[str], category_name: str = "", debug: bool = False) -> dict[str, object] | None:
    params = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1400"}
    if category_name:
        params.update({"generator": "categorymembers", "gcmtitle": f"Category:{category_name}", "gcmnamespace": "6", "gcmlimit": "50"})
    else:
        params.update({"generator": "search", "gsrsearch": name, "gsrnamespace": "6", "gsrlimit": "24"})
    data = json.loads(get(f"{API}?{urlencode(params)}", timeout).decode("utf-8"))
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        text = " ".join(str(x) for x in [page.get("title"), meta.get("ImageDescription", {}).get("value", ""), meta.get("Credit", {}).get("value", "")]).lower()
        license_value = str(meta.get("LicenseShortName", {}).get("value", "")).lower()
        url = info.get("thumburl") or info.get("url")
        page_url = f"https://commons.wikimedia.org/wiki/{str(page.get('title','')).replace(' ', '_')}"
        if debug:
            reasons = []
            if page_url in set(rejected_sources): reasons.append("rejected")
            if any(term in text for term in BAD_TERMS): reasons.append("bad-term")
            if not any(term in license_value for term in ALLOWED_LICENSES): reasons.append(f"license:{license_value or 'none'}")
            print(f"[candidate] {page.get('title')} {'|'.join(reasons) or 'eligible'}")
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        if page_url in set(rejected_sources):
            continue
        if any(term in text for term in BAD_TERMS) or not any(term in license_value for term in ALLOWED_LICENSES):
            continue
        return {"url": url, "page": page, "info": info, "meta": meta}
    return None


def wikipedia_lead(name: str, timeout: int, rejected_sources: list[str]) -> dict[str, object] | None:
    params = {"action": "query", "format": "json", "redirects": "1", "titles": name,
              "prop": "pageimages", "piprop": "name", "pilicense": "free"}
    data = json.loads(get(f"{WIKIPEDIA_API}?{urlencode(params)}", timeout).decode("utf-8"))
    page = next(iter((data.get("query", {}).get("pages", {}) or {}).values()), {})
    filename = page.get("pageimage")
    if not isinstance(filename, str):
        return None
    commons_params = {"action": "query", "format": "json", "titles": f"File:{filename}",
                      "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1400"}
    commons = json.loads(get(f"{API}?{urlencode(commons_params)}", timeout).decode("utf-8"))
    file_page = next(iter((commons.get("query", {}).get("pages", {}) or {}).values()), {})
    info = (file_page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    text = " ".join(str(x) for x in [file_page.get("title"), meta.get("ImageDescription", {}).get("value", "")]).lower()
    license_value = str(meta.get("LicenseShortName", {}).get("value", "")).lower()
    page_url = f"https://commons.wikimedia.org/wiki/{str(file_page.get('title','')).replace(' ', '_')}"
    url = info.get("url") or info.get("thumburl")
    if (not isinstance(url, str) or not url.startswith("http") or page_url in set(rejected_sources)
            or any(term in text for term in BAD_TERMS) or not any(term in license_value for term in ALLOWED_LICENSES)):
        return None
    return {"url": url, "page": file_page, "info": info, "meta": meta}


def exact_file(title: str, timeout: int, rejected_sources: list[str]) -> dict[str, object] | None:
    file_title = title if title.startswith("File:") else f"File:{title}"
    params = {"action": "query", "format": "json", "titles": file_title,
              "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1400"}
    data = json.loads(get(f"{API}?{urlencode(params)}", timeout).decode("utf-8"))
    page = next(iter((data.get("query", {}).get("pages", {}) or {}).values()), {})
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    licence = str(meta.get("LicenseShortName", {}).get("value", "")).lower()
    page_url = f"https://commons.wikimedia.org/wiki/{str(page.get('title','')).replace(' ', '_')}"
    url = info.get("url") or info.get("thumburl")
    if (not isinstance(url, str) or not url.startswith("http") or page_url in set(rejected_sources)
            or not any(term in licence for term in ALLOWED_LICENSES)):
        return None
    return {"url": url, "page": page, "info": info, "meta": meta}


def save(data: bytes, target: Path) -> bool:
    try:
        with Image.open(BytesIO(data)) as image:
            image = image.convert("RGB")
            if min(image.size) < 280:
                return False
            image.thumbnail((1280, 1280))
            image.save(target, "JPEG", quality=88, optimize=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def plain(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(str(value or "")))).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("backend/app/data/plant_species_catalog.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("frontend/public/plants"))
    parser.add_argument("--species-ids", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--query-suffix", default="")
    parser.add_argument("--category-search", action="store_true")
    parser.add_argument("--debug-candidates", action="store_true")
    parser.add_argument("--wikipedia-lead", action="store_true")
    parser.add_argument("--file-title", default="")
    parser.add_argument(
        "--taxon-name",
        action="append",
        default=[],
        metavar="SPECIES_ID=NAME",
        help="Override the Commons/Wikipedia query name for one catalog row; repeatable.",
    )
    args = parser.parse_args()
    taxon_names = dict(item.split("=", 1) for item in args.taxon_name)
    rows = json.loads(args.catalog.read_text(encoding="utf-8")); args.output_dir.mkdir(parents=True, exist_ok=True)
    targets = [row for row in rows if not row.get("image_url") and (not args.species_ids or row["species_id"] in set(args.species_ids))]
    if args.limit: targets = targets[:args.limit]
    updated = 0
    for row in targets:
        try:
            base = taxon_names.get(row["species_id"], str(row["latin_name"]))
            query = f'incategory:"{base}"' if args.category_search else base
            if args.query_suffix.strip():
                query = f"{query} {args.query_suffix.strip()}"
            rejected = list(row.get("rejected_image_sources") or [])
            if args.file_title:
                found = exact_file(args.file_title, args.timeout, rejected)
            elif args.wikipedia_lead:
                found = wikipedia_lead(base, args.timeout, rejected)
            else:
                found = search(query, args.timeout, rejected, base if args.category_search else "", args.debug_candidates)
            if not found or not save(get(found["url"], args.timeout), args.output_dir / f"{row['species_id']}.jpg"):
                print(f"[skip] {row['cn_name']}"); continue
            meta = found["meta"]; page = found["page"]
            row.update({
                "image_url": f"/plants/{row['species_id']}.jpg",
                "image_source_url": f"https://commons.wikimedia.org/wiki/{str(page.get('title','')).replace(' ', '_')}",
                "image_author": plain(meta.get("Artist", {}).get("value")) or "Wikimedia Commons contributor",
                "image_license": plain(meta.get("LicenseShortName", {}).get("value")),
                "image_basis_of_record": "Wikimedia Commons field photo",
            })
            args.catalog.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated += 1; print(f"[done] {row['cn_name']}")
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {row['cn_name']}: {exc.__class__.__name__}")
        time.sleep(0.15)
    print(f"updated={updated} total={len(targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
