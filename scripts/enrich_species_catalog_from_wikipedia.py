from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path
from typing import Any


API_URL = "https://zh.wikipedia.org/w/api.php"
USER_AGENT = "WildlifeCatalogEnricher/0.1 (local biodiversity catalog enrichment)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill missing short species summaries from Chinese Wikipedia extracts.")
    parser.add_argument("--catalog", type=Path, default=Path("backend/app/data/pdf_species_catalog.json"))
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of entries to enrich. 0 means no limit.")
    parser.add_argument("--names", nargs="*", default=[], help="Only enrich these Chinese species names.")
    parser.add_argument("--force", action="store_true", help="Replace existing monitoring_value for matched entries.")
    parser.add_argument("--save-every", type=int, default=10, help="Write the catalog after this many updates.")
    parser.add_argument("--sleep", type=float, default=0.1, help="Delay between API calls.")
    args = parser.parse_args()

    species = json.loads(args.catalog.read_text(encoding="utf-8-sig"))
    target_items = [item for item in species if should_enrich(item, args.names, args.force)]
    direct_extracts = batch_fetch_title_extracts(
        [str(item.get("cn_name") or "").strip() for item in target_items if item.get("cn_name")]
    )
    updated = 0
    attempted = 0

    for item in target_items:
        if args.limit and updated >= args.limit:
            break
        cn_name = str(item.get("cn_name") or "").strip()
        latin_name = str(item.get("latin_name") or "").strip()
        if not cn_name:
            continue

        attempted += 1
        extract, source_title = direct_extracts.get(cn_name, ("", ""))
        if not extract:
            extract, source_title = fetch_extract(cn_name, latin_name)
        if not extract:
            time.sleep(args.sleep)
            continue

        summary = build_summary(item, extract)
        if summary:
            item["monitoring_value"] = summary
            scope = str(item.get("source_scope") or "").strip()
            source_note = f"联网补充：中文维基百科《{source_title}》"
            item["source_scope"] = f"{scope}；{source_note}" if scope else source_note
            updated += 1
            if args.save_every and updated % args.save_every == 0:
                write_catalog(args.catalog, species)
        time.sleep(args.sleep)

    write_catalog(args.catalog, species)
    print(f"attempted={attempted} updated={updated} catalog={args.catalog}")


def should_enrich(item: dict[str, Any], names: list[str], force: bool) -> bool:
    cn_name = str(item.get("cn_name") or "").strip()
    if names and cn_name not in set(names):
        return False
    if force:
        return True
    return not (item.get("monitoring_value") or item.get("habitat") or item.get("features"))


def batch_fetch_title_extracts(titles: list[str], chunk_size: int = 40) -> dict[str, tuple[str, str]]:
    results: dict[str, tuple[str, str]] = {}
    unique_titles = list(dict.fromkeys(title for title in titles if title))
    for index in range(0, len(unique_titles), chunk_size):
        chunk = unique_titles[index : index + chunk_size]
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "redirects": "1",
            "titles": "|".join(chunk),
            "origin": "*",
        }
        data = request_json(params)
        pages = data.get("query", {}).get("pages", {})
        redirects = {
            str(item.get("from") or ""): str(item.get("to") or "")
            for item in data.get("query", {}).get("redirects", [])
        }
        by_page_title: dict[str, tuple[str, str]] = {}
        for page in pages.values():
            if page.get("missing") is not None:
                continue
            page_title = str(page.get("title") or "")
            extract = clean_extract(str(page.get("extract") or ""))
            if extract and page_title:
                by_page_title[page_title] = (extract, page_title)
        for title in chunk:
            page_title = redirects.get(title, title)
            if page_title in by_page_title:
                results[title] = by_page_title[page_title]
    return results


def fetch_extract(cn_name: str, latin_name: str) -> tuple[str, str]:
    titles = [cn_name]
    if latin_name:
        titles.append(latin_name)
    for title in titles:
        extract = fetch_title_extract(title)
        if extract[0]:
            return extract

    search_query = f"{cn_name} {latin_name}".strip()
    matched_title = search_title(search_query)
    if matched_title:
        return fetch_title_extract(matched_title)
    return "", ""


def fetch_title_extract(title: str) -> tuple[str, str]:
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "exintro": "1",
        "explaintext": "1",
        "redirects": "1",
        "titles": title,
        "origin": "*",
    }
    data = request_json(params)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if page.get("missing") is not None:
            continue
        extract = clean_extract(str(page.get("extract") or ""))
        if extract:
            return extract, str(page.get("title") or title)
    return "", ""


def search_title(query: str) -> str:
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srlimit": "1",
        "origin": "*",
    }
    data = request_json(params)
    hits = data.get("query", {}).get("search", [])
    if not hits:
        return ""
    return str(hits[0].get("title") or "")


def request_json(params: dict[str, str]) -> dict[str, Any]:
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                time.sleep(2 + attempt * 3)
                continue
            return {}
        except (TimeoutError, URLError):
            time.sleep(1 + attempt)
    return {}


def write_catalog(path: Path, species: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(species, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_summary(item: dict[str, Any], extract: str) -> str:
    cn_name = str(item.get("cn_name") or "").strip()
    taxon = " / ".join(str(item.get(key) or "").strip() for key in ["taxon_group", "order", "family"] if item.get(key))
    sentence = first_sentence(extract)
    sentence = sentence.replace("\n", " ").strip()
    sentence = truncate_sentence(sentence)
    if cn_name and sentence and cn_name not in sentence[:12]:
        sentence = f"{cn_name}：{sentence}"
    if taxon and taxon not in sentence:
        return f"{sentence}（分类：{taxon}）"
    return sentence


def first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。！？.!?])\s*", text.strip(), maxsplit=1)
    return parts[0].strip() if parts else ""


def truncate_sentence(text: str, limit: int = 110) -> str:
    if len(text) <= limit:
        return text
    candidate = text[:limit]
    breakpoints = [candidate.rfind(mark) for mark in "。！？；;，,、"]
    breakpoint = max(breakpoints)
    if breakpoint >= 36:
        candidate = candidate[: breakpoint + 1]
    else:
        candidate = candidate.rstrip("，,；;、 ")
    return candidate.rstrip("，,；;、 ") + ("。" if not candidate.endswith(("。", "！", "？")) else "")


def clean_extract(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    blocked = ["消歧义", "可以指", "可能指"]
    if any(word in text[:80] for word in blocked):
        return ""
    return text


if __name__ == "__main__":
    main()
