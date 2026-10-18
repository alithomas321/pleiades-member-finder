"""Derived quantities used for descriptive checks and visualization."""

from __future__ import annotations

import numpy as np
import pandas as pd


def corrected_bp_rp_excess(color: pd.Series, excess: pd.Series) -> pd.Series:
    """Compute the Riello et al. (2021) corrected BP/RP excess diagnostic C*."""
    x = color.to_numpy(dtype=float)
    raw = excess.to_numpy(dtype=float)
    expected = np.select(
        [x < 0.5, (x >= 0.5) & (x < 4.0), x >= 4.0],
        [
            1.154360 + 0.033772 * x + 0.032277 * x**2,
            1.162004 + 0.011464 * x + 0.049255 * x**2 - 0.005879 * x**3,
            1.057572 + 0.140537 * x,
        ],
        default=np.nan,
    )
    return pd.Series(raw - expected, index=color.index, name="corrected_bp_rp_excess")


def add_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add clearly labeled descriptive distance and photometry columns."""
    result = frame.copy()
    parallax = result["parallax"].astype(float)
    result["distance_pc_inverse_parallax"] = 1000.0 / parallax
    result["absolute_g_naive"] = (
        result["phot_g_mean_mag"].astype(float) + 5.0 * np.log10(parallax) - 10.0
    )
    result["corrected_bp_rp_excess"] = corrected_bp_rp_excess(
        result["bp_rp"], result["phot_bp_rp_excess_factor"]
    )
    return result
