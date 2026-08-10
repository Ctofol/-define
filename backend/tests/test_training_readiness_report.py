from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_render_training_readiness_report_orders_missing_samples_first(tmp_path: Path):
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(
        json.dumps(
            {
                "total_rows": 3,
                "label_count": 2,
                "classes": [
                    {
                        "label": "黑熊",
                        "train_count": 18,
                        "val_count": 4,
                        "total": 22,
                        "needed_total": 0,
                        "needed_val": 0,
                        "status": "ready",
                    },
                    {
                        "label": "猕猴",
                        "train_count": 9,
                        "val_count": 2,
                        "total": 11,
                        "needed_total": 9,
                        "needed_val": 1,
                        "status": "need_more_samples",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "report.md"
    subprocess.run(
        [
            "python",
            "scripts\\render_training_readiness_report.py",
            "--audit",
            str(audit_path),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
    )

    content = output_path.read_text(encoding="utf-8")
    assert "训练集补样优先级报告" in content
    assert "| 猕猴 | 11 | 9 | 2 | 9 | 1 | need_more_samples |" in content
    assert content.index("猕猴") < content.index("黑熊")
