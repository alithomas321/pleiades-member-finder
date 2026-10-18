"""Independently check saved sensitivity artifacts without importing fit code.

Run from the continuation root:
    analysis/reproduction/.venv/bin/python analysis/verify_sensitivity_outputs.py

Uses only the Python standard library. Its only write is
data/checks/verification.log, replaced with the current PASS or FAIL record.
Source IDs remain strings throughout. This checks consistency and recorded
hashes, not scientific correctness or membership accuracy.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "checks"
LOG = OUT / "verification.log"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    """Keep checks enabled even if Python is invoked with optimization."""
    if not condition:
        raise ValueError(message)


def verify() -> dict:
    audit = json.loads((OUT / "audit.json").read_text())
    checks = []
    for relative, expected in audit["inputs"].items():
        require(sha256(ROOT / relative) == expected, f"Input hash differs: {relative}")
    require(
        sha256(ROOT / "analysis" / "sensitivity_audit.py") == audit["script_sha256"],
        "Sensitivity script hash differs",
    )
    require(
        sha256(ROOT / "research" / "PROTOCOL.md") == audit["protocol_sha256"],
        "Protocol hash differs",
    )
    checks.append(
        "All recorded source data, query, modules, lock, sensitivity script and protocol hashes match."
    )
    manifest = json.loads((OUT / "output_hashes.json").read_text())
    for name, expected in manifest.items():
        require(sha256(OUT / name) == expected, f"Output hash differs: {name}")
    checks.append(f"All {len(manifest)} recorded output hashes match.")

    sets: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(OUT / "sensitivity_candidate_ids.csv"):
        source_id, experiment = row["source_id"], row["experiment"]
        require(re.fullmatch(r"\d+", source_id) is not None, "Malformed source ID")
        require(source_id not in sets[experiment], f"Duplicate ID in {experiment}")
        sets[experiment].add(source_id)

    raw = read_csv(ROOT / "analysis/reproduction/data/raw/gaia_dr3_pleiades_field.csv")
    raw_by_id = {row["source_id"]: row for row in raw}
    field = set(raw_by_id)
    reference = {
        row["source_id"]
        for row in read_csv(
            ROOT / "analysis/reproduction/data/reference/hunt_reffert_2024_members.csv"
        )
        if float(row["catalog_probability"]) >= 0.5 and int(row["inrt"]) == 1
    }
    eligible = reference & field
    main = sets["main"]
    rectangle = sets["fixed_rectangle"]
    summary = read_csv(OUT / "sensitivity_summary.csv")
    require(
        set(sets) == {row["experiment"] for row in summary},
        "Summary and ID-table experiment names differ",
    )
    for row in summary:
        selected = sets[row["experiment"]]
        require(selected <= field, f"Unknown source in {row['experiment']}")
        expected = {
            "candidate_count": len(selected),
            "shared_with_main": len(selected & main),
            "added_vs_main": len(selected - main),
            "lost_vs_main": len(main - selected),
            "shared_with_rectangle": len(selected & rectangle),
            "reference_members_total": len(reference),
            "reference_members_in_snapshot": len(eligible),
            "reference_intersection": len(selected & reference),
            "selected_only_vs_reference": len(selected - reference),
            "eligible_reference_not_selected": len(eligible - selected),
        }
        for key, value in expected.items():
            require(int(row[key]) == value, f"{row['experiment']}: wrong {key}")
        for key, other in (
            ("jaccard_vs_main", main),
            ("jaccard_vs_rectangle", rectangle),
            ("jaccard_vs_eligible_reference", eligible),
        ):
            union = selected | other
            expected_jaccard = len(selected & other) / len(union) if union else 1.0
            require(
                math.isclose(float(row[key]), expected_jaccard, rel_tol=1e-14),
                f"{row['experiment']}: wrong {key}",
            )
    require(
        sets["threshold_0.9"]
        <= sets["threshold_0.7"]
        <= sets["threshold_0.5"]
        <= sets["threshold_0.3"],
        "Threshold sets are not nested",
    )
    require(
        sets["threshold_0.5"] == sets["min_samples_10"] == main,
        "Default experiment sets differ",
    )
    require(main <= rectangle, "Main set is not contained in rectangular baseline")
    require(
        len(field) == len(raw) == audit["retained_rows"] == audit["unique_source_ids"],
        "Field/unique-ID counts differ",
    )
    checks.append(
        f"All saved ID sets, overlaps and Jaccard values agree for {len(summary)} experiment rows; "
        "thresholds nested and default fit identical."
    )
    absent = {
        row["source_id"] for row in read_csv(OUT / "reference_absent_from_snapshot.csv")
    }
    require(absent == reference - field, "Absent-reference table differs")
    checks.append(
        f"Absent-reference table contains exactly {len(absent)} unavailable filtered-reference IDs."
    )
    for row in read_csv(OUT / "query_cut_audit.csv"):
        require(
            int(row["rows_checked"]) == int(row["passing_rows"]) == len(raw)
            and int(row["failing_rows"]) == 0,
            f"Query-cut audit count differs: {row['cut']}",
        )
    subsets = {
        "retained_field": raw,
        "main_candidates": [raw_by_id[source_id] for source_id in main],
    }
    for row in read_csv(OUT / "missingness.csv"):
        subset = subsets[row["subset"]]
        require(int(row["rows"]) == len(subset), "Missingness subset count differs")
        require(
            int(row["missing_rows"])
            == sum(item[row["column"]] == "" for item in subset),
            f"Missingness count differs: {row['subset']}, {row['column']}",
        )
    for row in read_csv(OUT / "radial_velocity_availability.csv"):
        subset = subsets[row["subset"]]
        present = sum(item["radial_velocity"] != "" for item in subset)
        usable = sum(
            item["radial_velocity"] != ""
            and item["radial_velocity_error"] != ""
            and float(item["radial_velocity_error"]) < 5
            for item in subset
        )
        require(int(row["rv_present"]) == present, "RV-present count differs")
        require(
            int(row["rv_missing"]) == len(subset) - present, "RV-missing count differs"
        )
        require(int(row["rv_error_lt5"]) == usable, "RV error-cut count differs")
    checks.append(
        "Query audit counts, all missingness counts and RV availability counts agree with raw CSV."
    )
    examples = json.loads((OUT / "teaching_examples.json").read_text())
    for item in examples:
        source_id = item["source_id"]
        require(
            isinstance(source_id, str) and source_id in field,
            "Teaching example ID must be a known string ID",
        )
        require(
            item["is_main_candidate"] == (source_id in main),
            "Example candidate flag differs",
        )
        require(
            item["in_filtered_reference"] == (source_id in reference),
            "Example reference flag differs",
        )
        require(
            item["in_fixed_rectangle"] == (source_id in rectangle),
            "Example rectangle flag differs",
        )
        require(
            item["is_main_candidate"]
            == (item["is_target_component"] and item["cluster_strength"] >= 0.5),
            "Example target/strength classification differs",
        )
    checks.append(
        "Teaching JSON preserves IDs as strings; all candidate/reference/baseline classifications agree."
    )
    pipeline = ROOT / "analysis/reproduction/data/processed/pleiades_candidates.csv"
    pipeline_rows = read_csv(pipeline)
    pipeline_ids = {row["source_id"] for row in pipeline_rows}
    require(len(pipeline_rows) == len(pipeline_ids), "Duplicate pipeline candidate IDs")
    require(
        main == pipeline_ids, "Independent main and pipeline candidate ID sets differ"
    )
    checks.append(
        f"Independent sensitivity main IDs exactly equal pipeline candidate IDs ({len(main)})."
    )
    doc = ROOT / "research/SENSITIVITY.md"
    for link in re.findall(r"\]\(([^)]+)\)", doc.read_text()):
        if "://" not in link:
            target = (doc.parent / link).resolve()
            require(target == LOG or target.exists(), f"Broken document link: {link}")
    checks.append("All relative links in SENSITIVITY.md resolve.")
    return {
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "result": "PASS",
        "checks": checks,
        "verification_script_sha256": sha256(Path(__file__)),
        "command": "analysis/reproduction/.venv/bin/python analysis/verify_sensitivity_outputs.py",
        "python_executable": sys.executable,
        "audit_sha256": sha256(OUT / "audit.json"),
        "script_sha256": audit["script_sha256"],
        "protocol_sha256": audit["protocol_sha256"],
        "sensitivity_document_sha256": sha256(doc),
        "pipeline_candidates_sha256": sha256(pipeline),
        "pipeline_candidates_modified_at_utc": datetime.fromtimestamp(
            pipeline.stat().st_mtime, UTC
        ).isoformat(),
        "main_candidate_count": len(main),
        "source_id_conversion": "CSV string fields only; no floating-point ID conversion",
        "scope": "Stored artifact consistency and source preservation; not human scientific approval.",
    }


def main() -> int:
    try:
        result = verify()
    except Exception as error:
        result = {
            "verified_at_utc": datetime.now(UTC).isoformat(),
            "result": "FAIL",
            "verification_script_sha256": sha256(Path(__file__)),
            "error_type": type(error).__name__,
            "error": str(error),
        }
    serialized = json.dumps(result, indent=2) + "\n"
    LOG.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
