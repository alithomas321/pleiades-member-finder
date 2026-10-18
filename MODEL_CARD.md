# Model Card: Gaia Pleiades Kinematic Candidate Finder

## Model details

| Field | Value |
|---|---|
| Project version | 1.0.0 |
| Owner | Alison Thomas |
| Model family | Robust scaling + HDBSCAN density clustering |
| Implementation | `sklearn.preprocessing.RobustScaler` and `sklearn.cluster.HDBSCAN` |
| Fit population | 12,520 quality-filtered Gaia DR3 rows in one 5° Pleiades field |
| Output | Field-specific kinematic candidate table and fitted analysis bundle |
| License | MIT for code and documentation; source-data terms remain with providers |

## Summary

This model recovers a compact Pleiades-like astrometric component from a preselected Gaia
DR3 field. It is an unsupervised, transductive analysis: HDBSCAN fits the entire field,
component summaries are used to identify the Pleiades-like component, and an assignment-
strength threshold produces the published candidate table.

It is **not** a calibrated binary classifier. Its output should be called “Pleiades
kinematic candidates,” not “confirmed members,” and `cluster_strength` should not be called
a membership probability.

## Intended use

Appropriate uses include:

- reproducing this specific Pleiades candidate-selection experiment;
- inspecting density clustering and astronomy data-engineering practices;
- teaching the distinction between model selection and independent validation; and
- adapting the source code to a new, explicitly revalidated research workflow.

Out-of-scope uses include:

- certifying individual stars as physical Pleiades members;
- applying the saved model bundle to arbitrary Gaia sources as a general classifier;
- measuring the full Pleiades mass function, binary fraction, completeness, or tidal tails;
- inferring cluster dynamics, age, extinction, or gravitational boundedness; and
- treating catalog agreement as ground-truth accuracy.

## Inputs

### Model features

| Feature | Unit | Role |
|---|---|---|
| `parallax` | mas | Line-of-sight astrometric separation |
| `pmra` | mas yr⁻¹ | Proper motion in right ascension, including cos(dec) convention |
| `pmdec` | mas yr⁻¹ | Proper motion in declination |

Features are transformed with a `RobustScaler` using the 10th–90th percentile range.

### Information withheld from clustering

- sky position beyond defining the 5° query field;
- Gaia magnitudes and colors;
- radial velocity;
- the corrected BP/RP excess diagnostic; and
- Hunt–Reffert member rows and cluster summary values.

The query does require usable BP/RP photometry for later checks, so the fitted population is
photometrically filtered even though photometry is not a model feature.

## Candidate logic

The HDBSCAN configuration is:

```text
min_cluster_size=50
min_samples=10
cluster_selection_method="eom"
allow_single_cluster=False
```

The selected target component is the non-noise component nearest a rough, external
Pleiades astrometric anchor. A source is emitted when it belongs to that component and has:

```text
cluster_strength >= 0.5
```

`cluster_strength` comes from HDBSCAN's fitted assignment-strength output. It expresses how
strongly a source is associated with its assigned density component within this fit. It is
not calibrated against physical membership labels.

## Evidence summary

| Check | Reproduced result |
|---|---:|
| Quality-filtered Gaia field | 12,520 sources |
| Kinematic candidates | 866 sources |
| Shared with high-confidence, within-tidal-radius Hunt–Reffert subset | 781 sources |
| Candidate catalog agreement | 90.2% |
| Eligible reference recovery | 89.6% (781 of 872) |
| All-reference recovery | 77.0% (781 of 1,014) |

These are comparison-catalog overlap statistics, not accuracy, precision, or recall. The
reference catalog is not ground truth; it uses the same Gaia release and related
density-based methodology.

Additional generated checks include:

- comparison of median astrometry with the Hunt–Reffert cluster summary;
- descriptive distance comparison with the Melis et al. (2014) VLBI measurement;
- a color–magnitude diagram not used for clustering;
- a descriptive radial-velocity comparison; and
- candidate-ID stability across cluster-size and scaling experiments.

See `outputs/metrics.json`, `outputs/RESULTS.md`, and
`outputs/tables/parameter_sensitivity.csv` for the exact generated values.

## Known limitations and biases

### Target and field specificity

The model is fitted to a 5° cone centered on the Pleiades and uses broad Pleiades-compatible
astrometric windows before clustering. The external anchor then identifies the target
component. This is not blind cluster discovery and should not be extrapolated to other sky
regions.

The field approximates the central/tidal-region environment but is not a fitted tidal-radius
selection. It does not cover the full extended stellar tails.

### Sample selection

- `phot_g_mean_mag < 20` and BP/RP S/N cuts reduce faint-source completeness.
- `ruwe < 1.4` can preferentially exclude unresolved binaries or other non-single-star
  astrometric solutions.
- parallax and proper-motion uncertainty cuts favor better-measured sources.
- requiring more than eight visibility periods changes the archive selection function.
- broad parallax and proper-motion windows exclude any member outside those windows by
  construction.

No completeness correction is attempted.

### Astrophysical interpretation

- Gaia DR3's position-, color-, and magnitude-dependent parallax zero point is not corrected.
- Inverse-parallax distance is reported only as a descriptive median, not a Bayesian
  distance estimate.
- Extinction is not corrected in the CMD or naive absolute G magnitude.
- HDBSCAN uses no astrometric covariance matrix or per-source uncertainty model.
- Kinematic similarity alone does not establish gravitational binding or membership.
- Radial velocities are missing for many candidates and can be broadened by binaries and
  contaminants.

### Evaluation dependence

Hunt–Reffert is a scientifically relevant comparison, but not an independent set of labeled
truth. The agreement metrics measure reproducibility relative to that catalog under this
project's query, not false-positive or false-negative rates in the physical population.

## Reproducibility

The model bundle stores the fitted scaler, HDBSCAN object, feature order, selected component,
threshold, scaling range, cluster settings, target anchor, and an interpretation warning.
Raw snapshots and generated outputs are protected by SHA-256 manifests.

To refit from the committed snapshot and then independently verify candidate IDs and
strengths:

```bash
export UV_NO_EDITABLE=1
uv sync --frozen --extra dev --python 3.12
uv run gaia-pleiades run --project-root .
uv run gaia-pleiades verify --project-root .
```

The locked dependency graph, unit tests, source compilation, linting, scientific-artifact
verification, and package build run in GitHub Actions.

## Monitoring and update policy

Treat any change to the ADQL, archive release, reference catalog, quality cuts, features,
scaling quantiles, HDBSCAN implementation or settings, target anchor, or strength threshold
as a new scientific result. Regenerate every artifact, rerun sensitivity checks, review the
figures, and update this card before comparing counts across versions.

## References

- [Gaia DR3 documentation](https://gea.esac.esa.int/archive/documentation/GDR3/)
- [Hunt & Reffert (2024)](https://doi.org/10.1051/0004-6361/202348662)
- [Melis et al. (2014)](https://doi.org/10.1126/science.1256101)
- [Riello et al. (2021)](https://doi.org/10.1051/0004-6361/202039587)
- [Full project methodology](METHODOLOGY.md)
