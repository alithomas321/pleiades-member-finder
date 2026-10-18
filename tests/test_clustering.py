import numpy as np
import pandas as pd

from gaia_pleiades.clustering import (
    add_assignments,
    fit_clusters,
    jaccard_index,
    select_target_label,
)


def test_target_label_uses_external_anchor() -> None:
    summaries = pd.DataFrame(
        {
            "cluster_label": [3, 7],
            "count": [100, 100],
            "parallax_median": [7.35, 4.0],
            "pmra_median": [20.0, -3.0],
            "pmdec_median": [-46.0, -20.0],
        }
    )
    assert select_target_label(summaries) == 3


def test_jaccard_index() -> None:
    assert jaccard_index({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jaccard_index(set(), set()) == 1.0


def test_hdbscan_finds_synthetic_pleiades_component() -> None:
    rng = np.random.default_rng(42)
    pleiades = rng.normal([7.35, 20.0, -46.0], [0.08, 0.5, 0.5], size=(100, 3))
    distractor = rng.normal([4.0, -5.0, -20.0], [0.12, 0.7, 0.7], size=(100, 3))
    values = np.vstack([pleiades, distractor])
    frame = pd.DataFrame(values, columns=["parallax", "pmra", "pmdec"])
    frame["source_id"] = [str(index) for index in range(len(frame))]
    result = fit_clusters(frame, min_cluster_size=20)
    assigned = add_assignments(frame, result)
    selected = assigned.loc[assigned["is_target_cluster"]]
    assert len(selected) >= 90
    assert abs(selected["parallax"].median() - 7.35) < 0.1
