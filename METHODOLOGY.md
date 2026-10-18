# Methodology

## Research question

Can a compact Pleiades-like component be recovered from a quality-filtered Gaia DR3 field
using only parallax and proper motion, and does that component remain astrophysically
plausible under checks that were withheld from clustering?

This is a target-specific candidate-selection analysis. It is not a blind all-sky search,
a calibrated membership classifier, or a dynamical model of the cluster.

## 1. Data acquisition and provenance

### Gaia DR3 field

The committed query in [`queries/pleiades_field.adql`](queries/pleiades_field.adql) first
uses an asynchronous job against `gaiadr3.gaia_source` through the Gaia Archive TAP
service. If asynchronous result retrieval returns an HTTP error, the acquisition layer
uses the official synchronous endpoint with a 20,000-row cap and rejects a result that
reaches that cap as potentially truncated. The cone is centered at:

- right ascension: 56.75°;
- declination: 24.1167°; and
- radius: 5.0°.

The cone is intended to sample the central and tidal-region environment. It is not a fitted
tidal boundary and is not wide enough to characterize the full extended Pleiades tails.

The exact committed query applies these cuts:

| Quantity | Cut | Purpose and consequence |
|---|---:|---|
| Parallax | `2 <= parallax <= 15` mas | Broad distance preselection |
| Proper motion in RA | `-20 <= pmra <= 50` mas yr⁻¹ | Broad kinematic preselection |
| Proper motion in Dec | `-80 <= pmdec <= -10` mas yr⁻¹ | Broad kinematic preselection |
| Parallax S/N | `parallax_over_error > 10` | Retain better-measured parallaxes |
| Proper-motion error | `pmra_error < 1`, `pmdec_error < 1` mas yr⁻¹ | Limit astrometric uncertainty |
| RUWE | `ruwe < 1.4` | Astrometric-quality screen; can exclude binaries |
| Visibility periods | `visibility_periods_used > 8` | Require repeated observing coverage |
| G magnitude | `phot_g_mean_mag < 20` | Magnitude-limited sample |
| Color availability | `bp_rp IS NOT NULL` | Support later CMD checks |
| BP and RP flux S/N | both `> 10` | Support later photometric checks |

The resulting snapshot contains **12,520 quality-filtered sources**. Results therefore
describe this conditional sample, not every star in the field and not a complete Pleiades
population.

Rows are normalized and sorted by Gaia `source_id` before fitting. The manifest records the
query hash, access mode, archive job identifier when available, acquisition timestamp, row
count, file path, and SHA-256 digest.

### Comparison catalog

The pipeline retrieves the `clusters` and `members` tables for `Melotte_22` from the current
Hunt–Reffert (2024) VizieR catalog, `J/A+A/686/A42`. It retains source identifiers,
Hunt–Reffert membership scores, and the catalog's within-tidal-radius flag for later
comparison.

The high-confidence comparison subset is defined as:

```text
catalog_probability >= 0.5 AND inrt == 1
```

That produces 1,014 reference sources; 872 of them also satisfy this project's Gaia field
query. The comparison catalog does not participate in scaling, clustering, component
selection, or the assignment-strength threshold.

## 2. Derived descriptive quantities

The pipeline computes three post-query diagnostics:

1. Descriptive inverse-parallax distance:

   ```text
   distance_pc = 1000 / parallax_mas
   ```

2. Naive absolute G magnitude:

   ```text
   M_G = G + 5 log10(parallax_mas) - 10
   ```

3. Corrected BP/RP excess diagnostic, C*, using the piecewise color relation from
   Riello et al. (2021).

These derived quantities are not HDBSCAN features. The inverse-parallax distance is a
descriptive summary, not a Bayesian distance estimate. The absolute magnitude is called
“naive” because extinction and the Gaia parallax zero point are not corrected.

## 3. Feature construction

The model matrix contains exactly three columns:

```text
[parallax, pmra, pmdec]
```

The analysis deliberately omits sky coordinates, magnitudes, colors, radial velocities,
photometric excess, and reference-catalog labels. A `RobustScaler` transforms each feature
using its 10th and 90th percentiles. This makes units comparable while reducing sensitivity
to the broad field distribution.

The scaling is empirical for this queried sample. The saved scaler should not be interpreted
as a universal Gaia transformation.

## 4. Density-based clustering

The main fit uses scikit-learn's HDBSCAN implementation with:

| Setting | Value |
|---|---:|
| `min_cluster_size` | 50 |
| `min_samples` | 10 |
| `cluster_selection_method` | `eom` |
| `allow_single_cluster` | `False` |
| `copy` | `True` |

HDBSCAN labels low-density sources as noise (`-1`) and assigns non-noise observations to
density components. The value exposed by `probabilities_` is stored as
`cluster_strength`. In this project it means **strength of assignment to the selected
density component**. It is not a calibrated probability that a star is a physical Pleiades
member.

## 5. Identifying the Pleiades component

HDBSCAN discovers components without class labels, but component identifiers are arbitrary.
After fitting, the pipeline summarizes each non-noise component in physical units and
chooses the one nearest a rough external Pleiades anchor:

```text
parallax = 1000 / 136.2 pc
pmra     = 20 mas yr^-1
pmdec    = -50 mas yr^-1
```

Distances to this anchor are scaled by `(1 mas, 5 mas yr⁻¹, 5 mas yr⁻¹)`. The parallax term
comes from the Melis et al. (2014) VLBI distance; the proper-motion values are deliberately
coarse target locators.

This anchor identifies which already-discovered component to call “Pleiades.” It does not
assign individual sources, but it does make the workflow target-specific and must not be
described as a fully blind discovery method.

## 6. Candidate definition

A row is emitted as a kinematic candidate when both conditions are true:

```text
cluster_label == selected_target_label
cluster_strength >= 0.5
```

The main run selects **866 candidates**. The threshold is an explicit operational choice;
it is not optimized against the Hunt–Reffert catalog.

## 7. Post-clustering checks

### Catalog agreement

Gaia source IDs are compared with the Hunt–Reffert high-confidence, within-tidal-radius
subset. Three denominators answer three different questions:

| Metric | Formula | Result |
|---|---|---:|
| Candidate catalog agreement | shared / this project's candidates | 781 / 866 = **90.2%** |
| Eligible reference recovery | shared / reference sources passing this query | 781 / 872 = **89.6%** |
| All-reference recovery | shared / all high-confidence reference sources | 781 / 1,014 = **77.0%** |

These terms are intentionally not called precision, recall, or accuracy. Hunt–Reffert is a
related-method comparison catalog rather than ground truth, and its missing or additional
sources do not by themselves prove that either analysis is wrong.

### Astrophysical plausibility

The pipeline evaluates evidence not supplied to HDBSCAN:

- the Gaia color–magnitude sequence;
- median astrometry relative to the Hunt–Reffert cluster summary;
- descriptive inverse-parallax distance relative to the 136.2 ± 1.2 pc VLBI result from
  Melis et al. (2014); and
- available Gaia radial velocities with reported uncertainty below 5 km s⁻¹, compared
  descriptively with the Torres (2020) literature value.

Radial velocities can be broadened by binaries and contaminants. Neither radial velocity
nor photometry converts a candidate into a confirmed member in this workflow.

### Sensitivity analysis

The pipeline repeats the fit at `min_cluster_size` values 20, 40, 50, 80, and 100. It also
reruns the main cluster-size setting with standard 25th–75th percentile robust scaling.
Each experiment reports:

- target-component and candidate counts;
- Jaccard overlap of candidate source IDs with the main run; and
- median parallax and proper motion.

The exact table is generated at `outputs/tables/parameter_sensitivity.csv` rather than being
hard-coded into this document.

## 8. Reproducibility and integrity checks

Two manifests protect different stages of the analysis:

- `data/dataset_manifest.json` hashes the downloaded Gaia and VizieR snapshots.
- `outputs/artifact_manifest.json` hashes the processed tables and generated outputs.

Running:

```bash
export UV_NO_EDITABLE=1
uv run gaia-pleiades verify --project-root .
```

performs all of the following without refreshing remote data:

1. verifies source snapshot hashes;
2. verifies processed and output artifact hashes;
3. independently refits the clustering pipeline from the raw Gaia snapshot;
4. checks the recomputed candidate IDs against the cached candidate table;
5. checks assignment strengths numerically;
6. checks that the candidate count agrees with `metrics.json`; and
7. rejects missing, truncated, or invalid PNG figure files.

The CI workflow additionally runs linting, Python compilation, unit tests, and a package
build from the locked dependency environment.

## 9. Interpretation boundaries

- **Kinematic candidate, not confirmed member.** Membership would benefit from a fuller
  treatment of uncertainties, covariance, binaries, spectroscopy, and selection effects.
- **Assignment strength, not probability.** `cluster_strength` is not calibrated to the
  probability of physical membership.
- **Conditional sample.** Broad astrometric windows make the computation tractable but rule
  out candidates beyond those windows by construction.
- **Selection bias.** Magnitude, BP/RP S/N, RUWE, visibility-period, and astrometric-error
  cuts reduce contamination while lowering completeness for faint stars and some binaries.
- **Finite sky region.** The 5° field targets the central/tidal-region environment, not the
  full extended tidal tails.
- **No Gaia parallax zero-point correction.** Gaia DR3 retains a position-, magnitude-, and
  color-dependent astrometric zero point. No correction is applied here.
- **No extinction correction.** The CMD and naive absolute magnitudes are descriptive.
- **Catalog dependence.** Agreement with Hunt–Reffert is informative but not an independent
  ground-truth test because both workflows use Gaia DR3 and density-based methods.
- **Not a reusable classifier.** The saved bundle captures a fitted, field-specific
  clustering analysis; it is not an inference service for arbitrary new Gaia rows.

## References

1. Gaia Collaboration, [Gaia DR3 documentation](https://gea.esac.esa.int/archive/documentation/GDR3/)
   and [Gaia ESA Archive](https://gea.esac.esa.int/archive/).
2. Hunt, E. L. & Reffert, S. (2024), [“Improving the open cluster census. III”](https://doi.org/10.1051/0004-6361/202348662),
   A&A 686, A42; [VizieR J/A+A/686/A42](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/A+A/686/A42).
3. Melis, C. et al. (2014), [“A VLBI Resolution of the Pleiades Distance Controversy”](https://doi.org/10.1126/science.1256101),
   Science 345, 1029–1032.
4. Riello, M. et al. (2021), [“Gaia Early Data Release 3: Photometric content and validation”](https://doi.org/10.1051/0004-6361/202039587),
   A&A 649, A3.
5. Torres, G. (2020), [“Spectroscopic monitoring of rapidly-rotating early-type stars in the Pleiades cluster”](https://doi.org/10.3847/1538-4357/abb136),
   ApJ 901, 91.
