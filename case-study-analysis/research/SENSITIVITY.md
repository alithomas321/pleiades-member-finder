# Fixed sensitivity checks and retained-data audit

Completed locally on 2026-09-19 UTC against the retained 2026-07-10 Gaia DR3 snapshot. This is a descriptive extension of the existing result, not a new membership catalogue. Human science/copy/release approval remains pending. Original data and legacy code were read only; new code and outputs live in the continuation area.

## What this establishes

The unchanged three-feature model returns **866 kinematic candidates**. The selected component contains 1,288 rows before the conventional assignment-strength cut of 0.5. A separate implementation of the unchanged fit with `min_samples=10` exactly matches its labels, assignment strengths and target-component choice.

All 12,520 retained rows have unique string-preserved Gaia source IDs and finite parallax/proper-motion inputs. Every row satisfies all 13 independently evaluated clauses of the committed query, including a spherical 5° footprint around ICRS (56.75°, 24.1167°). The largest great-circle separation is 4.9998498061°. This checks the retained snapshot; it cannot establish whether the archive query retrieved every eligible source or explain exclusion of rows that were never retained.

The Hunt–Reffert comparison subset uses the existing conditions `catalog_probability >= 0.5` and `inrt == 1`: 1,014 source IDs qualify, 872 occur in this snapshot and 142 do not. The missing IDs are retained in a separate table. Their individual absence reasons cannot be inferred from the filtered Gaia file or the retained reference-member columns.

## Prespecified comparisons

The experiment list follows [PROTOCOL.md](PROTOCOL.md). Scaling remains RobustScaler with its 10th–90th percentile range; HDBSCAN uses `min_cluster_size=50`, EOM selection and no single-cluster allowance. Apart from the named change, each fit retains the main defaults. No experiment was selected or tuned to maximize catalog agreement.

Jaccard is the number of shared source IDs divided by the number in either list. “Reference intersection” is descriptive overlap with the filtered reference catalog, **not correct classifications**.

| Selection | Candidate count | Added vs main | Lost vs main | Jaccard vs main | Reference intersection |
|---|---:|---:|---:|---:|---:|
| Main, strength ≥0.5 | 866 | 0 | 0 | 1.000000 | 781 |
| Strength ≥0.3 | 1,099 | 233 | 0 | 0.787989 | 871 |
| Strength ≥0.7 | 582 | 0 | 284 | 0.672055 | 539 |
| Strength ≥0.9 | 254 | 0 | 612 | 0.293303 | 240 |
| `min_samples=5` | 884 | 31 | 13 | 0.950948 | 788 |
| `min_samples=20` | 856 | 12 | 22 | 0.961276 | 774 |
| Proper-motion-only inputs | 886 | 82 | 62 | 0.848101 | 770 |
| Fixed rectangular baseline | 1,196 | 330 | 0 | 0.724080 | 872 |

The threshold rows all use the same unchanged fitted component. Changing the cut changes how much of that component is reported, so the list is not broadly “insensitive to parameters.” The previously recorded cluster-size stability is a narrower statement. Assignment strength remains a density-clustering measure, not an astrophysical probability; 0.9 does not mean 90% membership confidence.

The proper-motion-only fit drops parallax from clustering and selects the component with the smallest physical-unit median distance from `(pmRA, pmDec) = (20, −50)` mas/yr, dividing each coordinate by 5 mas/yr as in the original anchor. Its selected-component medians are (19.887445, −45.360347) mas/yr. The snapshot itself still has the original parallax and quality prefilters. Thus this ablation isolates the clustering input change; it is not a wholly distance-free search. Its total of 886 looks close to 866, but **144 source identities change** (82 added, 62 lost).

The baseline uses inclusive intervals around the existing external anchor: parallax `1000/136.2 ±1` mas, pmRA `20 ±5` mas/yr, and pmDec `−50 ±10` mas/yr. It is deliberately simple and was fixed before its result was examined. It contains every main candidate plus 330 further sources; 872 of its 1,196 rows occur in the filtered reference catalog and 324 do not. This does not make the rectangle superior, nor does the model's smaller list establish greater astrophysical purity. A related Gaia-based catalog cannot decide those claims. The baseline does show that the machine-learning step extracts a density-defined subset beyond applying a broad box.

## Missing measurements and measurement precision

Every retained column other than radial velocity and its error is populated, including all three pairwise parallax/proper-motion correlation columns. The initial protocol statement that these correlations were absent was a factual inspection error; it was corrected before extension results. No astrometric perturbation study was performed in this bounded revival. Proper uncertainty propagation and interpretation would be a separate method extension; available correlations should be used if that extension is pursued.

| Quantity | Retained-field median | Main-candidate median | Main-candidate 95th percentile |
|---|---:|---:|---:|
| Parallax standard error (mas) | 0.0749944 | 0.0535933 | 0.146098 |
| pmRA standard error (mas/yr) | 0.0886553 | 0.0636686 | 0.176590 |
| pmDec standard error (mas/yr) | 0.0597270 | 0.0436729 | 0.122164 |

These are summaries of reported measurement errors, not uncertainty on cluster membership or total systematic error. The original model treats measured feature values as points; this audit does not propagate their uncertainties. The original analysis also does not apply a Gaia parallax zero-point correction.

Among 866 main candidates, 347 have radial velocities and **519 do not**. Applying the original additional error cut (`radial_velocity_error < 5 km/s`) leaves **229**, whose median RV is 5.565687 km/s and robust spread (1.4826 × MAD) is 1.625551 km/s. Those 229 stars have median G=11.462444; the remaining 637 candidates have median G=16.544926. Lower G means brighter. Thus the RV check samples a much brighter subset and cannot validate every candidate. An RV measured separately from the three fitted astrometric features is useful held-out evidence, but not a membership certificate. The CMD likewise was not a clustering feature, while parallax enters absolute magnitude and photometric quality enters the initial query.

## Individual examples for teaching

All IDs below are strings. The full measurements, algorithmic classifications, comparison flags and deterministic selection rules are in [teaching_examples.json](../data/checks/teaching_examples.json) and the full-precision [CSV](../data/checks/teaching_examples.csv). These are deliberately selected illustrations, not a representative statistical sample.

| Gaia DR3 source ID | Teaching use | Main assignment strength | Interpretation |
|---|---|---:|---|
| `66885942316710784` | Strong candidate | 1.000000 | In the target component and above the cut; its RV is unavailable. Strength 1 is not certainty. |
| `66732423004453376` | Just above the cut | 0.500065 | Retained by the convention; measured RV 22.42745 ±3.151752 km/s differs substantially from the candidate-group median. This is a reason for investigation, not a diagnosed cause. |
| `65330099002345216` | Just below the cut | 0.499779 | In the selected component but omitted from the final list; that tiny threshold difference does not prove nonmembership. |
| `68409590552589184` | Outside the selected component | 0.000000 | HDBSCAN labels this row noise, although it falls inside the simple rectangle. “Noise” is an algorithmic label. |
| `53029278307021696` | Candidate without filtered-reference overlap | 1.000000 | High assignment strength but absent from the filtered comparison subset; this is not proof of a newly discovered member or a false positive. |

For the first example the rule chooses maximum strength, then smallest original-anchor distance, then source ID. Boundary examples use closest strength above/below 0.5. The outside-component example is the nearest original-anchor row outside the selected component. The final example uses maximum strength among candidates absent from the filtered comparison, then source ID. These disclosed choices avoid implying that one illustrative star represents the population.

## Exact files and verification

From the continuation root:

```sh
PYTHONPATH=analysis/reproduction/src analysis/reproduction/.venv/bin/python analysis/sensitivity_audit.py
```

Then independently verify the stored outputs, without importing the model implementation:

```sh
analysis/reproduction/.venv/bin/python analysis/verify_sensitivity_outputs.py
```

The [verification script](../analysis/verify_sensitivity_outputs.py) uses only the Python standard library and changes only `data/checks/verification.log`. It exits 0 on PASS or 1 on a failed check, replacing the log with the current result. The log records its own script hash, the checked document hash, all relevant evidence hashes and the verification time. Re-running it does not refit the model or change the sensitivity script or protocol.

The final execution completed at **2026-09-19T01:50:46.838996+00:00**, exit 0, using Python 3.12.13, NumPy 2.5.1, pandas 3.0.3 and scikit-learn 1.9.0 as read from that interpreter. Its [audit.json](../data/checks/audit.json) records exact executable, script/protocol/source-module/lock/input SHA-256 hashes. These measured versions take precedence over informal setup estimates. The script passed Ruff formatting and lint checks. The first shell attempt to redirect a log failed because `data/checks/` did not yet exist; no Python executed and no data were changed. Creating that output directory resolved it. The first successful scientific run and the final metadata-expanded run produced the same tabulated results.

- [sensitivity_summary.csv](../data/checks/sensitivity_summary.csv): all fixed experiments, medians, candidate-set and reference overlaps.
- [threshold_sensitivity.csv](../data/checks/threshold_sensitivity.csv): the four threshold rows, including unchanged 0.5.
- [sensitivity_candidate_ids.csv](../data/checks/sensitivity_candidate_ids.csv): every selected ID for every experiment; load `source_id` as a string.
- [alternative_component_summaries.csv](../data/checks/alternative_component_summaries.csv): every alternative-fit component, physical medians and anchor distance.
- [query_cut_audit.csv](../data/checks/query_cut_audit.csv), [missingness.csv](../data/checks/missingness.csv), [measurement_distributions.csv](../data/checks/measurement_distributions.csv), [radial_velocity_availability.csv](../data/checks/radial_velocity_availability.csv): independent retained-row audit and distribution tables.
- [reference_absent_from_snapshot.csv](../data/checks/reference_absent_from_snapshot.csv): 142 filtered-reference rows unavailable to this analysis; no assigned exclusion causes.
- [output_hashes.json](../data/checks/output_hashes.json): final run output, artifact hashes and independent output-consistency checks.

The independent check reloads CSVs without numeric ID conversion, recomputes set counts/intersections/Jaccard from the saved IDs, verifies threshold nesting and example classifications, and checks all recorded artifact/input/script/protocol hashes. It also checks counts against the freshly reproduced pipeline candidate file. Passing those checks validates these stored results and their consistency; it does not supply the pending human scientific review.
