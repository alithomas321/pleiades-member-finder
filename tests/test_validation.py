import pandas as pd

from gaia_pleiades.validation import reference_agreement, robust_sigma


def test_reference_agreement_uses_only_query_eligible_denominator() -> None:
    field = pd.DataFrame({"source_id": ["1", "2", "3"]})
    candidates = pd.DataFrame({"source_id": ["1", "3"]})
    members = pd.DataFrame(
        {
            "source_id": ["1", "2", "4", "5"],
            "catalog_probability": [0.9, 0.8, 0.95, 0.2],
            "inrt": [1, 1, 1, 1],
        }
    )
    result = reference_agreement(field, candidates, members)
    assert result["overlap_count"] == 1
    assert result["candidate_catalog_agreement"] == 0.5
    assert result["eligible_reference_recovery"] == 0.5
    assert result["all_catalog_recovery"] == 1 / 3


def test_robust_sigma_rejects_extreme_outlier() -> None:
    assert robust_sigma(pd.Series([0.0, 1.0, 2.0, 100.0])) < 2.0
