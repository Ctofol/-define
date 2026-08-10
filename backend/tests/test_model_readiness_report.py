from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_render_model_readiness_report_blocks_weak_classifier(tmp_path: Path):
    classifier_eval = tmp_path / "classifier.json"
    retrieval_eval = tmp_path / "retrieval.json"
    coverage = tmp_path / "coverage.json"

    classifier_eval.write_text(
        json.dumps(
            {
                "accuracy": 0.5,
                "per_class": [
                    {"label": "黑熊", "total": 4, "accuracy": 0.25},
                    {"label": "水鹿", "total": 4, "accuracy": 0.75},
                ],
                "confusion_pairs": [
                    {"true_label": "黑熊", "predicted_label": "水鹿", "count": 2},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    retrieval_eval.write_text(
        json.dumps(
            {
                "topk_accuracy": 0.85,
                "per_class": [
                    {"label": "黑熊", "total": 4, "topk_accuracy": 1.0},
                    {"label": "水鹿", "total": 4, "topk_accuracy": 1.0},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    coverage.write_text(
        json.dumps(
            {
                "species": [
                    {"cn_name": "黑熊", "category": "animal", "total_count": 12, "needed_to_minimum": 0},
                    {"cn_name": "水鹿", "category": "animal", "total_count": 20, "needed_to_minimum": 0},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_json = tmp_path / "readiness.json"
    output_md = tmp_path / "readiness.md"

    subprocess.run(
        [
            "python",
            "scripts\\render_model_readiness_report.py",
            "--classifier-eval-json",
            str(classifier_eval),
            "--retrieval-eval-json",
            str(retrieval_eval),
            "--coverage-json",
            str(coverage),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
    )

    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["overall"]["can_promote"] is False
    assert any(row["status"] == "not_ready" for row in report["rows"])
    assert "模型发布门槛报告" in output_md.read_text(encoding="utf-8")
