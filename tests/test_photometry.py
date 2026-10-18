import numpy as np
import pandas as pd

from gaia_pleiades.photometry import add_derived_columns, corrected_bp_rp_excess


def test_corrected_excess_uses_all_riello_branches() -> None:
    color = pd.Series([0.0, 1.0, 5.0])
    expected_raw = pd.Series([1.154360, 1.216844, 1.760257])
    result = corrected_bp_rp_excess(color, expected_raw)
    assert np.allclose(result, 0.0, atol=1e-6)


def test_derived_distance_and_absolute_magnitude() -> None:
    frame = pd.DataFrame(
        {
            "parallax": [10.0],
            "phot_g_mean_mag": [10.0],
            "bp_rp": [1.0],
            "phot_bp_rp_excess_factor": [1.217018],
        }
    )
    result = add_derived_columns(frame)
    assert result.loc[0, "distance_pc_inverse_parallax"] == 100.0
    assert result.loc[0, "absolute_g_naive"] == 5.0
