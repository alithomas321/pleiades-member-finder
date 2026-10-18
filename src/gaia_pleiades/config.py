"""Scientific configuration and filesystem layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FIELD_CENTER_RA_DEG = 56.75
FIELD_CENTER_DEC_DEG = 24.1167
FIELD_RADIUS_DEG = 5.0

FEATURE_COLUMNS = ("parallax", "pmra", "pmdec")
SCALER_QUANTILE_RANGE = (10.0, 90.0)
MIN_CLUSTER_SIZE = 50
MIN_SAMPLES = 10
STRENGTH_THRESHOLD = 0.5
SENSITIVITY_CLUSTER_SIZES = (20, 40, 50, 80, 100)

# The anchor identifies which unsupervised component is the Pleiades. It does
# not assign membership. Parallax is the inverse of the independent VLBI
# distance from Melis et al. (2014); proper motions are a deliberately rough
# archive-use-case location.
TARGET_ANCHOR = (1000.0 / 136.2, 20.0, -50.0)
TARGET_ANCHOR_SCALES = (1.0, 5.0, 5.0)

REFERENCE_CATALOG = "J/A+A/686/A42"
REFERENCE_CLUSTER_NAME = "Melotte_22"
REFERENCE_PROBABILITY_THRESHOLD = 0.5
VLBI_DISTANCE_PC = 136.2
VLBI_DISTANCE_ERROR_PC = 1.2
LITERATURE_RV_KMS = 5.52
LITERATURE_RV_ERROR_KMS = 0.31


@dataclass(frozen=True)
class ProjectPaths:
    """All pipeline paths rooted at an explicit checkout/output directory."""

    root: Path

    @property
    def query(self) -> Path:
        return self.root / "queries" / "pleiades_field.adql"

    @property
    def raw_gaia(self) -> Path:
        return self.root / "data" / "raw" / "gaia_dr3_pleiades_field.csv"

    @property
    def reference_members(self) -> Path:
        return self.root / "data" / "reference" / "hunt_reffert_2024_members.csv"

    @property
    def reference_cluster(self) -> Path:
        return self.root / "data" / "reference" / "hunt_reffert_2024_cluster.csv"

    @property
    def manifest(self) -> Path:
        return self.root / "data" / "dataset_manifest.json"

    @property
    def processed_field(self) -> Path:
        return self.root / "data" / "processed" / "pleiades_field_clustered.csv"

    @property
    def candidates(self) -> Path:
        return self.root / "data" / "processed" / "pleiades_candidates.csv"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def figures(self) -> Path:
        return self.outputs / "figures"

    @property
    def tables(self) -> Path:
        return self.outputs / "tables"

    @property
    def metrics(self) -> Path:
        return self.outputs / "metrics.json"

    @property
    def results(self) -> Path:
        return self.outputs / "RESULTS.md"

    @property
    def model(self) -> Path:
        return self.outputs / "hdbscan_model.joblib"

    @property
    def artifact_manifest(self) -> Path:
        return self.outputs / "artifact_manifest.json"

    def make_directories(self) -> None:
        for directory in (
            self.raw_gaia.parent,
            self.reference_members.parent,
            self.processed_field.parent,
            self.figures,
            self.tables,
        ):
            directory.mkdir(parents=True, exist_ok=True)
