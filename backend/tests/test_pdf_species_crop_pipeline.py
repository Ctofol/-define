from PIL import Image

from scripts.render_pdf_species_card_crops import crop_bbox_for_item, select_embedded_image_box
from scripts.trim_pdf_weak_reference_crops import (
    trim_decorative_top_strip,
    trim_neighbor_columns,
)


def test_image_crop_keeps_full_portrait_photo_above_label():
    bbox = crop_bbox_for_item({}, (280.0, 361.57, 350.0, 370.0), 396.0, 560.0, "image")

    assert bbox == (270.0, 236.57, 396.0, 341.57)


def test_top_strip_trim_removes_previous_card_label_without_cutting_photo():
    image = Image.new("RGB", (120, 100), "white")
    for x in range(12, 52):
        for y in range(4, 9):
            image.putpixel((x, y), (25, 35, 30))
    for x in range(120):
        for y in range(35, 100):
            image.putpixel((x, y), (45, 105, 65))

    trimmed = trim_decorative_top_strip(image)

    assert 65 <= trimmed.height <= 70
    assert trimmed.getpixel((60, 4)) == (45, 105, 65)


def test_neighbor_column_trim_uses_pdf_column_separator():
    image = Image.new("RGB", (140, 80), "white")
    for x in range(10, 120):
        for y in range(80):
            image.putpixel((x, y), (45, 105, 65))
    for x in range(128, 140):
        for y in range(80):
            image.putpixel((x, y), (35, 70, 120))

    trimmed = trim_neighbor_columns(image)

    assert trimmed.size == (110, 80)
    assert trimmed.getpixel((0, 0)) == (45, 105, 65)


def test_embedded_image_match_handles_two_column_rows():
    latin_box = (225.0, 500.0, 310.0, 512.0)
    image_boxes = [
        (90.0, 375.0, 208.0, 480.0),
        (210.0, 376.0, 328.0, 479.0),
        (276.0, 87.0, 393.0, 178.0),
    ]

    assert select_embedded_image_box(latin_box, image_boxes) == image_boxes[1]
