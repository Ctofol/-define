from __future__ import annotations

"""Fill plant-card covers with openly licensed iNaturalist observation photos."""

import argparse
import json
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image


API = "https://api.inaturalist.org/v1/observations"
OPEN_LICENSES = {"cc0", "cc-by", "cc-by-sa"}
NONCOMMERCIAL_LICENSES = {"cc-by-nc", "cc-by-nc-sa"}


def get(url: str, timeout: int) -> bytes:
    return urlopen(Request(url, headers={"User-Agent": "WildlifePlantKnowledge/1.0"}), timeout=timeout).read()


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("backend/app/data/plant_species_catalog.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("frontend/public/plants"))
    parser.add_argument("--species-ids", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--quality-grade",
        choices=("research", "any"),
        default="research",
        help="Use research-grade observations by default; 'any' also checks verifiable non-research observations.",
    )
    parser.add_argument(
        "--allow-noncommercial",
        action="store_true",
        help="Also accept CC BY-NC / CC BY-NC-SA photos; their reuse must remain non-commercial.",
    )
    parser.add_argument(
        "--taxon-name",
        action="append",
        default=[],
        metavar="SPECIES_ID=NAME",
        help="Override the iNaturalist taxon query for one catalog row; repeatable.",
    )
    args = parser.parse_args()
    taxon_names = dict(item.split("=", 1) for item in args.taxon_name)
    allowed = OPEN_LICENSES | (NONCOMMERCIAL_LICENSES if args.allow_noncommercial else set())
    rows = json.loads(args.catalog.read_text(encoding="utf-8")); args.output_dir.mkdir(parents=True, exist_ok=True)
    selected = set(args.species_ids)
    targets = [r for r in rows if not r.get("image_url") and (not selected or r["species_id"] in selected)]
    if args.limit:
        targets = targets[:args.limit]
    updated = 0
    for row in targets:
        try:
            params = {
                "taxon_name": taxon_names.get(row["species_id"], row["latin_name"]),
                "photos": "true",
                "photo_license": ",".join(sorted(allowed)),
                "per_page": "200",
                "order": "desc",
                "order_by": "observed_on",
            }
            if args.quality_grade == "research":
                params["quality_grade"] = "research"
            observations = json.loads(get(f"{API}?{urlencode(params)}", args.timeout).decode("utf-8")).get("results", [])
            chosen = None
            rejected = set(row.get("rejected_image_sources") or [])
            target = args.output_dir / f"{row['species_id']}.jpg"
            for observation in observations:
                for photo in observation.get("photos") or []:
                    licence = str(photo.get("license_code") or "").lower()
                    source = str(photo.get("url") or "").replace("square", "original")
                    obs_url = str(observation.get("uri") or "")
                    if licence in allowed and source.startswith("http") and obs_url not in rejected:
                        try:
                            if save(get(source, args.timeout), target):
                                chosen = (source, obs_url, photo, licence, observation)
                                break
                        except Exception:  # noqa: BLE001
                            continue
                if chosen:
                    break
            if not chosen:
                print(f"[skip] {row['cn_name']}"); continue
            source, obs_url, photo, licence, observation = chosen
            row.update({"image_url": f"/plants/{row['species_id']}.jpg", "image_source_url": obs_url,
                        "image_author": str(photo.get("attribution") or "iNaturalist observer"),
                        "image_license": licence.upper().replace("CC-", "CC "),
                        "image_basis_of_record": (
                            "iNaturalist research-grade field photo"
                            if observation.get("quality_grade") == "research"
                            else "iNaturalist openly licensed observation photo"
                        )})
            args.catalog.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated += 1; print(f"[done] {row['cn_name']}")
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {row['cn_name']}: {exc.__class__.__name__}")
        time.sleep(0.2)
    print(f"updated={updated} total={len(targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
