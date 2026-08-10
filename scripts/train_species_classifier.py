from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune a local species image classifier.")
    parser.add_argument("--manifest", type=Path, default=Path("storage") / "training" / "species_manifest.csv")
    parser.add_argument("--output-dir", type=Path, default=Path("models") / "species-classifier-local")
    parser.add_argument("--base-model", default="google/mobilenet_v2_1.0_224")
    parser.add_argument("--epochs", type=float, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--best-metric", choices=["accuracy", "loss"], default="accuracy")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--freeze-backbone", action="store_true")
    parser.add_argument("--augment", action="store_true", help="Apply light PIL augmentations to training images.")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest and training dependencies without loading or training a model.")
    return parser.parse_args()


class SpeciesImageDataset:
    def __init__(self, rows: list[dict[str, str]], label_to_id: dict[str, int], processor, augment: bool = False):
        self.rows = rows
        self.label_to_id = label_to_id
        self.processor = processor
        self.augment = augment

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, object]:
        row = self.rows[index]
        with Image.open(row["file_path"]) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            if self.augment:
                image = augment_image(image)
            encoded = self.processor(images=image, return_tensors="pt")
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = self.label_to_id[row["label"]]
        return item


def augment_image(image: Image.Image) -> Image.Image:
    if random.random() < 0.5:
        image = ImageOps.mirror(image)
    if random.random() < 0.35:
        image = image.rotate(random.uniform(-8, 8), resample=Image.Resampling.BILINEAR, fillcolor=(0, 0, 0))
    if random.random() < 0.45:
        image = ImageEnhance.Brightness(image).enhance(random.uniform(0.85, 1.15))
    if random.random() < 0.45:
        image = ImageEnhance.Contrast(image).enhance(random.uniform(0.85, 1.18))
    if random.random() < 0.35:
        image = ImageEnhance.Color(image).enhance(random.uniform(0.85, 1.15))
    return image


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("file_path") and row.get("label")]


def compute_metrics(eval_prediction) -> dict[str, float]:
    import numpy as np

    predictions = eval_prediction.predictions
    if isinstance(predictions, tuple):
        predictions = predictions[0]
    predicted_labels = np.argmax(predictions, axis=1)
    labels = eval_prediction.label_ids
    return {"accuracy": float((predicted_labels == labels).mean())}


def main() -> int:
    args = parse_args()

    from transformers import AutoImageProcessor, AutoModelForImageClassification, Trainer, TrainingArguments, set_seed

    set_seed(args.seed)

    rows = read_manifest(args.manifest)
    if not rows:
        raise ValueError(f"manifest has no training rows: {args.manifest}")

    labels = sorted({row["label"] for row in rows})
    label_to_id = {label: index for index, label in enumerate(labels)}
    id_to_label = {index: label for label, index in label_to_id.items()}
    train_rows = [row for row in rows if row.get("split") != "val"]
    val_rows = [row for row in rows if row.get("split") == "val"]
    if not train_rows:
        raise ValueError("manifest does not contain train rows")
    if not val_rows:
        val_rows = train_rows[:]

    if args.dry_run:
        print(f"labels={len(labels)} rows={len(rows)} train={len(train_rows)} val={len(val_rows)}")
        for label in labels:
            label_rows = [row for row in rows if row["label"] == label]
            print(f"{label}: {len(label_rows)}")
        return 0

    processor = AutoImageProcessor.from_pretrained(args.base_model, local_files_only=args.local_files_only)
    model = AutoModelForImageClassification.from_pretrained(
        args.base_model,
        num_labels=len(labels),
        id2label=id_to_label,
        label2id=label_to_id,
        ignore_mismatched_sizes=True,
        local_files_only=args.local_files_only,
    )
    if args.freeze_backbone:
        trainable = 0
        frozen = 0
        for name, parameter in model.named_parameters():
            is_classifier = "classifier" in name
            parameter.requires_grad = is_classifier
            if is_classifier:
                trainable += parameter.numel()
            else:
                frozen += parameter.numel()
        print(f"freeze_backbone=True trainable_params={trainable} frozen_params={frozen}")

    metric_for_best_model = "accuracy" if args.best_metric == "accuracy" else "loss"
    greater_is_better = args.best_metric == "accuracy"
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        label_smoothing_factor=args.label_smoothing,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model=metric_for_best_model,
        greater_is_better=greater_is_better,
        remove_unused_columns=False,
        logging_steps=10,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=SpeciesImageDataset(train_rows, label_to_id, processor, augment=args.augment),
        eval_dataset=SpeciesImageDataset(val_rows, label_to_id, processor),
        compute_metrics=compute_metrics,
        processing_class=processor,
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))
    processor.save_pretrained(str(args.output_dir))
    print(f"saved classifier with {len(labels)} labels to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
