from __future__ import annotations

import csv
from pathlib import Path


AUDIT_CSV = Path("docs") / "viverrid_gbif_quality_audit" / "viverrid_gbif_quality_audit.csv"
REVIEW_STATUS = Path("reference_species") / "待复核" / "gbif" / "review_status.csv"


def main() -> int:
    if not AUDIT_CSV.exists():
        raise FileNotFoundError(f"missing audit csv: {AUDIT_CSV}")

    with AUDIT_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        audit_rows = list(csv.DictReader(file))

    fieldnames = [
        "species",
        "filename",
        "status",
        "reason",
        "suggested_action",
        "license_allowed",
        "license",
        "country",
        "locality",
        "source_url",
        "contact_sheet",
    ]
    existing: dict[tuple[str, str], dict[str, str]] = {}
    if REVIEW_STATUS.exists():
        with REVIEW_STATUS.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                key = (row.get("species", ""), row.get("filename", ""))
                if all(key):
                    existing[key] = row

    for row in audit_rows:
        key = (row["species"], row["filename"])
        status = row["status"]
        if status == "priority_review":
            suggested_action = "review first; approve only after species and scene are visually confirmed"
        elif status == "review_needed":
            suggested_action = "manual review needed; likely reference-only unless subject is clear"
        else:
            suggested_action = "deprioritize; do not train unless manually rescued"

        existing[key] = {
            "species": row["species"],
            "filename": row["filename"],
            "status": status,
            "reason": row["reasons"],
            "suggested_action": suggested_action,
            "license_allowed": "yes" if "creativecommons.org" in row.get("license", "").lower() else "unknown",
            "license": row.get("license", ""),
            "country": row.get("country", ""),
            "locality": row.get("locality", ""),
            "source_url": row.get("source_url", ""),
            "contact_sheet": f"docs/viverrid_gbif_quality_audit/viverrid_gbif_quality_sheet.jpg",
        }

    REVIEW_STATUS.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_STATUS.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: existing[key].get(field, "") for field in fieldnames} for key in sorted(existing))

    print(f"wrote {len(existing)} rows to {REVIEW_STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
