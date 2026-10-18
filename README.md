# Gaia Pleiades Member Finder

Which stars in a Gaia field move like the Pleiades, and how much does the answer depend on the selection rule?

![Pleiades-like stars in proper motion and the color–magnitude diagram](figures/pleiades.png)

The workflow groups stars by motion and distance, compares the candidate list with a published catalog, and checks how the list changes under different settings. A candidate is not a confirmed cluster member, and the clustering strength is not a membership probability.

[Read the case study](https://alisonthomasportfolio.com/projects/pleiades) · [Explore the code](https://github.com/alithomas321/pleiades-member-finder/tree/main/src/gaia_pleiades) · [Methods](METHODOLOGY.md)

## Run locally

With Python 3.12 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --frozen --extra dev
uv run pytest
uv run gaia-pleiades run --project-root .
uv run gaia-pleiades verify --project-root .
```

The archived Gaia DR3 field and reference catalog are included, so the analysis can run offline after setup. Data come from ESA Gaia and the Hunt–Reffert catalog via CDS VizieR; [the data manifest](data/dataset_manifest.json) records the sources and checksums.
