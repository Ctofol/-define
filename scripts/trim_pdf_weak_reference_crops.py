from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path("reference_species/pdf_guangxi_species_images_v2")
CROPS_DIR = ROOT / "crops"
BACKUP_DIR = ROOT / "crops_before_trim"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MANIFEST_PATH = ROOT / "weak_reference_manifest.csv"


def is_near_white(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red >= 246 and green >= 246 and blue >= 246


def nonwhite_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()

    cols: list[int] = []
    for x in range(width):
        nonwhite = sum(1 for y in range(height) if is_content_pixel(pixels[x, y]))
        if nonwhite / height >= 0.015:
            cols.append(x)

    rows: list[int] = []
    for y in range(height):
        nonwhite = sum(1 for x in range(width) if is_content_pixel(pixels[x, y]))
        if nonwhite / width >= 0.015:
            rows.append(y)

    if not cols or not rows:
        return None
    return min(cols), min(rows), max(cols) + 1, max(rows) + 1


def trim_decorative_top_strip(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    search_height = min(96, max(0, height // 2))
    if search_height < 12:
        return image

    white_ratios: list[float] = []
    content_ratios: list[float] = []
    for y in range(search_height):
        pixels = [rgb.getpixel((x, y)) for x in range(width)]
        white_ratios.append(sum(1 for pixel in pixels if is_near_white(pixel)) / width)
        content_ratios.append(sum(1 for pixel in pixels if is_content_pixel(pixel)) / width)

    # Some three-column PDF cards place the previous species label immediately
    # above the next photo.  Locate the transition from that mostly-white paper
    # strip to a sustained full-width photo instead of using a fixed pixel trim.
    run = 6
    for y in range(6, search_height - run):
        previous_white = sum(white_ratios[max(0, y - 10) : y]) / min(10, y)
        following_content = sum(content_ratios[y : y + run]) / run
        if previous_white >= 0.68 and following_content >= 0.55:
            trim_to = max(0, y - 2)
            return image.crop((0, trim_to, width, height))

    return image


def trim_bottom_label_strip(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    start_y = int(height * 0.55)
    min_run = max(8, height // 30)

    for y in range(start_y, height - min_run):
        run_ok = True
        for yy in range(y, min(height, y + min_run)):
            white = sum(1 for x in range(width) if is_near_white(pixels[x, yy])) / width
            content = sum(1 for x in range(width) if is_content_pixel(pixels[x, yy])) / width
            if white < 0.62 or content > 0.38:
                run_ok = False
                break
        if run_ok and y >= height * 0.62:
            cropped = image.crop((0, 0, width, max(80, y - 1)))
            if cropped.height >= 110:
                return cropped
    return image


def trim_neighbor_columns(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width < 100 or height < 80:
        return image

    white_ratios = [
        sum(1 for y in range(height) if is_near_white(rgb.getpixel((x, y)))) / height
        for x in range(width)
    ]
    edge_width = max(8, int(width * 0.16))
    min_run = max(3, width // 120)

    def white_runs(start: int, end: int) -> list[tuple[int, int]]:
        runs: list[tuple[int, int]] = []
        run_start: int | None = None
        for x in range(start, end):
            if white_ratios[x] >= 0.96:
                run_start = x if run_start is None else run_start
            elif run_start is not None:
                if x - run_start >= min_run:
                    runs.append((run_start, x))
                run_start = None
        if run_start is not None and end - run_start >= min_run:
            runs.append((run_start, end))
        return runs

    left = 0
    left_runs = white_runs(0, edge_width)
    if left_runs:
        left = left_runs[0][1]

    right = width
    right_runs = white_runs(width - edge_width, width)
    if right_runs:
        right = right_runs[0][0]

    if right - left < width * 0.72:
        return image
    return image.crop((left, 0, right, height)) if left or right < width else image


def is_content_pixel(pixel: tuple[int, int, int]) -> bool:
    return not is_near_white(pixel) and not is_pdf_rule_color(pixel)


def is_pdf_rule_color(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red >= 145 and 55 <= green <= 190 and blue <= 130 and red >= green + 20


def should_replace(original: Image.Image, trimmed: Image.Image) -> bool:
    original_area = original.size[0] * original.size[1]
    trimmed_area = trimmed.size[0] * trimmed.size[1]
    if trimmed.size[0] < 80 or trimmed.size[1] < 80:
        return False
    return trimmed_area <= original_area * 0.995


def refresh_manifest_hashes() -> None:
    if not MANIFEST_PATH.is_file():
        return
    with MANIFEST_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        return
    fieldnames = list(rows[0])
    for row in rows:
        relative_path = row.get("relative_path", "")
        image_path = ROOT / relative_path
        if not image_path.is_file():
            continue
        digest = hashlib.sha256()
        with image_path.open("rb") as image_file:
            for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
                digest.update(chunk)
        row["sha256"] = digest.hexdigest()
    with MANIFEST_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not CROPS_DIR.is_dir():
        raise SystemExit(f"Missing crop directory: {CROPS_DIR}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    changed = 0
    skipped = 0

    for path in sorted(CROPS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        original = Image.open(path).convert("RGB")
        bbox = nonwhite_bbox(original)
        if not bbox:
            skipped += 1
            continue

        left, top, right, bottom = bbox
        padded = (
            max(0, left - 2),
            max(0, top - 2),
            min(original.size[0], right + 2),
            min(original.size[1], bottom + 2),
        )
        trimmed = trim_neighbor_columns(
            trim_bottom_label_strip(trim_decorative_top_strip(original.crop(padded)))
        )
        if not should_replace(original, trimmed):
            skipped += 1
            continue

        backup_path = BACKUP_DIR / path.name
        if not backup_path.exists():
            shutil.copy2(path, backup_path)
        trimmed.save(path, quality=92)
        changed += 1

    refresh_manifest_hashes()
    print(f"trimmed={changed} skipped={skipped} backup={BACKUP_DIR} manifest={MANIFEST_PATH}")


if __name__ == "__main__":
    main()
