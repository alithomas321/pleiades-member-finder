from pathlib import Path


def test_query_keeps_broad_field_and_quality_filters() -> None:
    root = Path(__file__).resolve().parents[1]
    query = (root / "queries" / "pleiades_field.adql").read_text(encoding="utf-8").lower()
    required = [
        "circle('icrs', 56.75, 24.1167, 5.0)",
        "parallax between 2 and 15",
        "pmra between -20 and 50",
        "pmdec between -80 and -10",
        "parallax_over_error > 10",
        "ruwe < 1.4",
        "visibility_periods_used > 8",
        "phot_bp_mean_flux_over_error > 10",
        "phot_rp_mean_flux_over_error > 10",
        "order by source_id",
    ]
    for clause in required:
        assert clause in query


def test_query_does_not_tightly_preselect_the_pleiades_motion() -> None:
    root = Path(__file__).resolve().parents[1]
    query = (root / "queries" / "pleiades_field.adql").read_text(encoding="utf-8")
    assert "ABS(pmra" not in query
    assert "ABS(pmdec" not in query
