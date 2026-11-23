# Kuroshio drifter climatology

DATA3001 Term 3, 2026, group S02-G6 (Sean Enzo Nebres, Saihil Arandkar, Xintong Liu, Jiaying Li)

How many distinct drifters does a 1° cell need for the NOAA Global Drifter Program (GDP) hourly record to estimate the mean surface current of the Kuroshio region (115–145°E, 15–40°N) to ±10 cm/s, and where, including across ENSO phases, does the record meet that standard?

The pipeline builds a 1° gridded climatology of surface velocity and SST. Every cell carries its bootstrap uncertainty, its drifter support and a reliability flag. It also builds an El Niño vs non-El Niño comparison with block-permutation significance. The method and results are in the project report.

## Repository layout

```
src/
  grid.py                           shared 1° grid and map styling
  01_data_prep_roni_gdp.ipynb       ... 08_maps_with_reliability.ipynb
  initialEDA.ipynb                  exploratory only, not part of the pipeline
data/
  raw/                              inputs (RONI file, cached GDP extract)
  01_data_prep_roni_gdp/ ... 08_maps_with_reliability/    one folder per notebook
figures/
  01_data_prep_roni_gdp/ ... 08_maps_with_reliability/
requirements.txt
```

Every notebook creates its own output folders. Only `data/raw/RONI.ascii.txt` has to be in place before the first run.

## Requirements

- Python 3.13.1 (the version used for the report)
- The packages in `requirements.txt`: NumPy, pandas, Matplotlib, Cartopy, pyarrow, CloudDrift (v0.48.1) and Jupyter

```
python -m venv .venv
.venv\Scripts\activate            # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Internet access is needed for two things: the GDP download in notebook 01, and the Natural Earth coastline files that Cartopy fetches the first time it draws a map.

## Input data

| Input | How to get it | Where it goes |
|---|---|---|
| NOAA GDP hourly, v2.01.1 | Downloaded automatically by notebook 01 through CloudDrift's `gdp1h()` on its first run. | Cached as `data/raw/kuroshio_obs.parquet` and `data/raw/gdp_metadata.json` |
| NOAA CPC Relative Oceanic Niño Index (RONI) | Download `RONI.ascii.txt` from [URL: NOAA CPC RONI page] | `data/raw/RONI.ascii.txt` [committed to the repo / must be downloaded] |

The first run of notebook 01 downloads the full global GDP hourly dataset before cutting out the Kuroshio box, which needs [X GB] of disk and [Y GB] of memory. Later runs reload the cached parquet and do not touch the network.

## Running the pipeline

Start Jupyter from the `src/` folder, because every notebook uses relative paths (`../data`, `../figures`) and imports `grid.py` from `../src`. Run the notebooks in order, using **Run All** in each.

```
cd src
jupyter lab
```

| # | Notebook | Reads | Writes |
|---|---|---|---|
| 01 | `01_data_prep_roni_gdp` | `data/raw/RONI.ascii.txt`, GDP via CloudDrift (first run) | `kuroshio_obs_clean.parquet`, `roni_phase.csv`, `enso_phase_support.csv`, `data_prep_summary.json` |
| 02 | `02_sampling_characterisation` | 01 | sampling tables and maps (descriptive; later notebooks do not read it) |
| 03 | `03_aggregation_and_means` | 01 | `agg_vel_1deg.parquet`, `agg_sst_1deg.parquet`, `weighting_diff_1deg.npy`, `03_summary.json` |
| 04 | `04_bootstrap` | 03 | `bootstrap_velocity_1deg.parquet`, `bootstrap_sst_1deg.parquet/.csv`, `bootstrap_summary.json` |
| 05 | `05_data_denial` | 03 | `data_denial_1deg.npz`, `data_denial_results.csv`, `05_summary.json` (N* for jet and recirculation cells) |
| 06 | `06_reliability` | 01, 04, 05 | **`product_velocity_1deg`, `product_sst_1deg`** (`.parquet` and `.csv`), `06_summary.json` |
| 07 | `07_enso_comparison` | 01, 05, 06 | **`product_enso_velocity_1deg`, `product_enso_sst_1deg`** (`.parquet` and `.csv`), `07_summary.json` |
| 08 | `08_maps_with_reliability` | 03, 06 | report figures with reliability marked, `08_summary.json` |

Each notebook after 01 reads only the saved outputs of earlier notebooks, so you can restart from any notebook once its inputs exist. 

## Product

The product is the set of tables written by notebooks 06 and 07, one row per 1° cell on the full 25 × 30 grid, with cells that have no data left empty.

**`data/06_reliability/product_velocity_1deg.csv`**

| Column(s) | Meaning |
|---|---|
| `iy`, `ix`, `lon_center`, `lat_center` | Cell index and centre |
| `n_drifters`, `n_hours` | Distinct drogued drifters and hours |
| `mean_ve_cmps`, `mean_vn_cmps`, `mean_vector_speed_cmps` | Hour-weighted mean eastward and northward velocity, and the speed of the mean vector (cm/s) |
| `ve_ci_*`, `vn_ci_*` | 95% whole-drifter bootstrap interval per component (low, high, half-width) |
| `bootstrap_vector_radius95_cmps` | U95, the 95th percentile vector error of the bootstrap |
| `snr` | Mean speed divided by U95; above 1 means the direction is resolved |
| `region`, `N_star` | Jet or recirculation group, and the drifters that group needs |
| `reliable`, `direction_resolved` | Reliability flags (at least N* drifters and U95 ≤ 10 cm/s) |
| `drifters_needed` | Additional drifters needed to reach N* (0 where met) |
| `weighting_diff_cmps`, `weighting_sensitive` | Hour- vs drifter-weighted difference, and whether it exceeds U95 |
| `category`, `category_label` | One category per cell, as used in the reliability map |

**`data/06_reliability/product_sst_1deg.csv`**: `n_drifters`, `n_hours`, `mean_sst_c`, `sst_ci_low_c`, `sst_ci_high_c`, `sst_ci_halfwidth_c`, `n_seasons`, `sst_balanced_c`, `seasonal_bias_c`, `reliable`, `sst_category`, `sst_category_label`.

**`data/07_enso_comparison/product_enso_*_1deg.csv`**: El Niño and non-El Niño means, intervals, drifter counts and reliability flags, the El Niño minus non-El Niño difference from seasonal anomalies, its permutation p-value, and the `significant` and `robust` flags.

How to use it:
1. Filter on `reliable` first. A mean is given for every cell with data, whether or not it can be trusted.
2. Read `n_drifters` as well as the interval. Bootstrap intervals are too narrow in cells with very few drifters, so a small U95 from a handful of drifters does not mean the cell is precise.
3. Where `weighting_sensitive` is true, the choice between hour- and drifter-weighting matters more than sampling noise, so treat the mean with extra caution.
4. For SST north of about 22°N, use `sst_balanced_c` rather than `mean_sst_c`.

## Reproducibility

- **Seeds.** Every random step is seeded from the base seed `20261105`, with a separate stream per cell and per step: velocity bootstrap (04, stream 1), SST bootstrap (04, stream 2), data-denial subsampling (05, stream 3) and the ENSO bootstrap (07, streams 4–7). The block-permutation test in 07 is deterministic: it uses every circular shift from 12 to 238 months. Rerunning the pipeline on the same data reproduces the reported numbers.
- **Checks built in.** Several notebooks assert known counts, for example 2,135,791 drogued observations from 1,177 drifters (02, 03), 577 cells with a bootstrap interval (03) and six El Niño events in the comparison window (07). Notebook 08 asserts that every map matches the counts saved by 06. If an assertion fails after a fresh GDP download, the downloaded GDP data differ from the version used for the report (v2.01.1).
- **Python and packages.** See `requirements.txt` for the versions used.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `FileNotFoundError: ../data/...` or `No module named 'grid'` | Jupyter was not started from `src/`. |
| `FileNotFoundError: RONI.ascii.txt` | Put the RONI file in `data/raw/` (see Input data). |
| A notebook says an input file is missing | An earlier notebook has not been run yet; run them in the order above. |
| Maps are slow or fail on the first run | Cartopy is downloading coastline data; check the internet connection and run again. |

## Reusing the method for another region

Change the bounds and cell size in `src/grid.py` (`LON_MIN`, `LON_MAX`, `LAT_MIN`, `LAT_MAX`, `RES`) and the same four bounds in notebook 01. Also set `STUDY` in notebook 01 (the first and last months with drifter data in the new box) and `WINDOW` in notebook 07 (the ENSO comparison period). Several notebooks contain checks with this study’s counts, so those asserts must be updated as well. N* is specific to this study: it was derived from test cells with at least 60 drifters in the Kuroshio box for a ±10 cm/s target, and the jet value is extrapolated beyond 30 drifters. A new region or target needs notebook 05 rerun.

## Data and references

- Elipot, S. et al. (2016, 2022). NOAA GDP hourly product, v2.01.1, accessed through CloudDrift (v0.48.1).
- NOAA Climate Prediction Center. Relative Oceanic Niño Index (RONI).
- Full references are in the project report.