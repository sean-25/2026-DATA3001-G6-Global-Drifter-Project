# Kuroshio surface-current climatology from GDP hourly drifters

UNSW, DATA3001 Data Science and Decisions in Practice, Term 3 2026, Group 6.

Authors: Sean Enzo Nebres, Saihil Arandkar, Xintong Liu, Jiaying Li.

## Summary

We built a 1° gridded climatology of near-surface velocity and sea-surface temperature (SST) for the
Kuroshio region (115–145°E, 15–40°N) from the NOAA Global Drifter Program hourly dataset (GDP 1h,
v2.01.1, 1990–2022). Drifters sample the ocean unevenly and preferentially follow the current, so
a cell can hold thousands of hourly observations yet rest on only a few independent drifters. Every
cell's estimate therefore comes with its own uncertainty and support. Each cell carries:

* a whole-drifter bootstrap 95% confidence interval for the mean;
* the number of distinct drifters behind it;
* a reliability flag from a precision rule. A data-denial experiment gives the number of drifters
  N* needed for a ±10 cm/s mean current. The bootstrap uncertainty must also meet that target;
* an El Niño vs non-El Niño comparison, with ENSO phases from NOAA's Relative Oceanic Niño Index
  (RONI). Its significance comes from a block-permutation (circular-shift) null.

**Research question.** How many distinct drifters does a 1° cell need for the GDP hourly record to
estimate the mean surface current of the Kuroshio region to ±10 cm/s, and where, including across
ENSO phases, does the record meet that standard?

**Objectives** (115–145°E, 15–40°N, 1° grid), with the notebooks that address them:

1. **Characterise sampling.** Map observation counts and distinct drifter counts per cell, and
   summarise how the record is distributed across years, ENSO phases and drogue status. (01, 02)
2. **Build a gridded climatology with uncertainty.** Estimate the mean surface velocity (drogued
   drifters) and SST (all drifters) in each cell, with 95% confidence intervals from a
   whole-drifter bootstrap, and measure the bias in SST from uneven seasonal sampling. (03, 04, 06)
3. **Derive a precision rule.** In well-sampled cells, repeatedly subsample to fewer drifters and
   measure how the error in the mean falls as drifter count increases. Use this to set the number
   of drifters needed for ±10 cm/s, and apply that standard to every cell to produce a reliability
   map. (05, 06)
4. **Test whether ENSO differences can be resolved.** Compare mean velocity and SST between El Niño
   and non-El Niño conditions, classified with RONI. Assess each difference against a
   block-permutation null, and report where the record meets the precision standard for each
   phase. (07)

**Key results** (full method and discussion in the final report; numbers in
`results/<notebook>/*_summary.json`):

* N* = 26 drifters for recirculation cells and 83 for jet cells (mean speed ≥ 34 cm/s, Otsu
  threshold). The jet value is extrapolated beyond the largest subsample of 30, and both are lower
  bounds.
* 310 of 595 velocity cells (52%) are reliable, mostly upstream, east of Luzon and Taiwan. SST is
  reliable in 147 of 618 cells (24%), limited mainly by the seasonal cycle.
* No cell has a reliable El Niño mean current. Across the region, velocity differs between El Niño
  and non-El Niño months more often than chance (field p = 0.026); SST does not (field p = 0.42).
* Reliable means precise, not unbiased: along the Kuroshio path, hour-weighted speeds are lower
  than drifter-weighted speeds (median 24.8 cm/s in cells faster than 40 cm/s), so treat them as
  lower bounds.

## Repository structure

```
src/config.py                        single configuration: region, grid, windows, seed, paths
run_all.py                           runs notebooks 01-08 in order
requirements.txt, environment.yml    pinned environment
data/                                input data only
  RONI.ascii.txt                     NOAA CPC Relative Oceanic Niño Index (committed)
  kuroshio_obs.parquet               in-box GDP hourly extract, made by 01 (117 MB, not in git)
  kuroshio_obs_metadata.json         GDP dataset attributes + extraction bounds (committed)
results/<notebook>/                  every numeric output (csv, json, npy, npz, parquet)
figures/<notebook>/                  every figure (png, 300 dpi)
src/                                 notebooks and shared modules
```

Notebooks, in run order (each reads only `data/` and earlier notebooks' `results/`):

| Notebook | What it does |
|---|---|
| `src/01_data_prep_roni_gdp.ipynb` | Extracts the in-box GDP observations (one-off, skipped if present). Classifies RONI months as El Niño / La Niña / Neutral (±0.5 °C for ≥5 overlapping seasons). Applies the SST QC (`flg_sst == 5`) and the drogue policy (hourly flag cross-checked against the drogue-loss date). Tags every hour with its ENSO phase. |
| `src/02_sampling_characterisation.ipynb` | Sampling support per cell and ENSO phase, cost of the drogue rule, coverage vs drifter threshold, record by year, effective drifters per cell. |
| `src/03_aggregation_and_means.ipynb` | Aggregates to one row per (cell, drifter, phase). Computes hour-weighted mean velocity and SST, and the weighting sensitivity (per-drifter vs per-hour mean). |
| `src/04_bootstrap.ipynb` | Whole-drifter bootstrap (B = 3000) per cell: component CIs, U95 (95% radius of the mean vector), SNR, SST CIs, and a Monte Carlo seed check. |
| `src/05_data_denial.ipynb` | Splits cells into jet and recirculation with an Otsu threshold on mean speed. A data-denial subsampling experiment then gives N*, the drifters needed for E95 ≤ 10 cm/s (FPC-corrected). |
| `src/06_reliability.ipynb` | Reliability rule. **Main product tables** (velocity and SST). |
| `src/07_enso_comparison.ipynb` | El Niño vs non-El Niño over 2002-01 to 2022-10 on seasonal anomalies: per-phase bootstrap, block-permutation p-values, field significance. **ENSO product tables.** |
| `src/08_maps_with_reliability.ipynb` | Report versions of the climatology, weighting and uncertainty maps, with unreliable cells hatched. |
| `src/config.py`, `src/grid.py` | Configuration, plus the shared grid (`cell_index`) and map styling. |
| `src/initialEDA.ipynb` | Proposal-stage exploration of the global dataset. **Not part of the pipeline.** It loads the full GDP dataset, and its figures in `figures/proposal_init_eda/` were saved by hand. |

## Setup

**Environment** (Python 3.13). Use one of the two options below:

```bash
# Option A: pip
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Option B: conda (conda-forge cartopy, then the same pinned pip packages)
conda env create -f environment.yml && conda activate gdp-kuroshio
```

On first use, cartopy downloads Natural Earth coastlines (a few MB), so the first run needs internet.

**Data.**

* **RONI**: `data/RONI.ascii.txt` is committed. Last downloaded on 2026-11-11 from
  <https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt> and runs to JAS 2026. NOAA revises
  RONI, so a fresh download may differ slightly; keep the committed file to reproduce our results.
* **GDP hourly**: accessed with CloudDrift's `clouddrift.datasets.gdp1h()`, which reads the public
  Zarr store on AWS (<https://registry.opendata.aws/noaa-oar-hourly-gdp/>, no account needed).
  Notebook 01 extracts the in-box hours once into `data/kuroshio_obs.parquet`. This file is not in
  git (117 MB), so a fresh clone runs the extraction automatically on the first run (see below).

## How to reproduce

From the repository root, with the environment active:

```bash
python run_all.py                  # full pipeline; extracts GDP data only if data/kuroshio_obs.parquet is missing
python run_all.py --no-extract     # same, but fail instead of extracting (use when the extract exists)
python run_all.py --force-extract  # redo the extraction even if the extract exists
python run_all.py --from 04        # rerun from notebook 04 onwards
```

`run_all.py` executes each notebook top to bottom in a fresh kernel and saves it in place, so the
notebooks' stored outputs always match `results/` and `figures/`. You can also open the notebooks
in Jupyter and run them in order (01 → 08). They work from any working directory. Outside
`run_all.py`, extraction is controlled by the environment variable `GDP_EXTRACT=auto|force|never`
(default `auto`).

The extraction is the only slow step. Once `data/kuroshio_obs.parquet` exists, every later run skips
it. To skip it on a fresh clone, copy an existing `kuroshio_obs.parquet` (for example, from a team
member) into `data/`. Its bounds are checked against `data/kuroshio_obs_metadata.json`.

**Reproducibility.** All randomness (bootstrap, data-denial subsampling) uses
`numpy.random.SeedSequence([SEED, iy, ix, stream])` with `SEED = 20261105` from `src/config.py`. Each
cell and analysis therefore has its own fixed random stream, and reruns are bit-for-bit identical.
The only run-to-run differences are the timing fields `permutation_seconds` and `bootstrap_seconds`
in `results/07_enso_comparison/07_summary.json`.

## Running for a different region

Everything region-specific lives in `src/config.py`:

1. Set `REGION_NAME` (a new name gives a new extract `data/<name>_obs.parquet`), `LON_MIN`,
   `LON_MAX`, `LAT_MIN`, `LAT_MAX` and, if needed, `RES` and `ENSO_WINDOW`. `STUDY = None` derives
   the study period from the data.
2. Optionally keep the Kuroshio outputs by writing the new run to sub-folders:

   ```bash
   GDP_OUTPUT_SUBDIR=myregion python run_all.py    # -> results/myregion/..., figures/myregion/...
   ```

3. The first run extracts the new box from GDP hourly (the slow step above).

Notebook 01 refuses to reuse an extract whose bounds differ from the config. The sanity checks
against our published Kuroshio numbers (`KUROSHIO_EXPECTED` in `config.py`) only run for the
default configuration. Method thresholds (targets, B, N* test settings, permutation settings) are
also in `config.py`; we used the values shown.

Limitations for other regions:

* The box must not cross the dateline (longitudes −180..180 with `LON_MIN < LON_MAX`).
* Notebook 05 needs cells with ≥ 60 distinct drifters on both sides of the jet/recirculation split.
* Notebook 07 needs at least one El Niño event in `ENSO_WINDOW`.
* Some colour-bar limits (e.g. SST 10–30 °C in 04) and the numbers quoted in the notebooks'
  markdown text are Kuroshio-specific.

## Product documentation

The deliverable is four cell-level tables on the full 30 × 25 grid (750 rows each, one per 1° cell,
including cells without data). Each is saved as parquet (exact dtypes, regenerated by the pipeline)
and as CSV (committed):

| File | Content |
|---|---|
| `results/06_reliability/product_velocity_1deg.{parquet,csv}` | Mean surface current, bootstrap uncertainty, reliability |
| `results/06_reliability/product_sst_1deg.{parquet,csv}` | Mean SST, bootstrap uncertainty, seasonal bias, reliability |
| `results/07_enso_comparison/product_enso_velocity_1deg.{parquet,csv}` | El Niño vs non-El Niño velocity, 2002-01 to 2022-10 |
| `results/07_enso_comparison/product_enso_sst_1deg.{parquet,csv}` | El Niño vs non-El Niño SST, 2002-01 to 2022-10 |

Supporting numbers quoted in the report are in each notebook's `results/<notebook>/*_summary.json`.

### Loading

```python
import pandas as pd

vel = pd.read_csv("results/06_reliability/product_velocity_1deg.csv",
                  dtype={"weighting_sensitive": "boolean"})
sst = pd.read_csv("results/06_reliability/product_sst_1deg.csv")

reliable = vel[vel["reliable"]]                                  # cells that pass the precision rule
print(len(reliable), "reliable velocity cells;",
      f"max reliable speed {reliable['mean_vector_speed_cmps'].max():.0f} cm/s")

# As 2-D (lat x lon) arrays: rows are in grid order (iy, then ix)
ny, nx = vel["iy"].max() + 1, vel["ix"].max() + 1
speed = vel["mean_vector_speed_cmps"].to_numpy().reshape(ny, nx)  # NaN where no data
```

After running the pipeline, `pd.read_parquet(...)` on the `.parquet` files gives the same tables
with exact dtypes.

### Conventions (all tables)

* **Grid.** `iy`, `ix` are the 0-based cell indices from the south-west corner. `lon_center` and
  `lat_center` (degrees E, N) are the cell centres. Cell `ix` spans
  `[LON_MIN + ix·RES, LON_MIN + (ix+1)·RES)`. Points on the outer east and north edges are put in
  the last cell.
* **Units.** Velocity in cm/s (`_cmps`), SST in °C (`_c`). `ve` is eastward and `vn` northward.
* **Means** are hour-weighted: the sum of all hourly values in the cell divided by the hours. Mean
  speed is the magnitude of the mean vector, not the mean of hourly speeds.
* **Velocity** uses drogued hours only. A drifter counts as drogued when its hourly flag says so
  and the hour is before its recorded drogue-loss date. **SST** uses all drifters, with
  `flg_sst == 5` only.
* **Missing and unreliable cells.**
  * Cells with no data have `n_drifters = 0`, NaN in every estimate, `reliable = False` and
    category 0.
  * Cells with only one drifter have a mean but NaN CIs, U95 and SNR. A bootstrap interval needs
    ≥ 2 drifters.
  * Unreliable cells keep their estimates but have `reliable = False`. Always filter on
    `reliable` before quoting a cell's value.
  * `weighting_sensitive` is a nullable boolean: empty in the CSV where no interval exists.

### `product_velocity_1deg`

| Column | Units | Meaning |
|---|---|---|
| `iy`, `ix`, `lon_center`, `lat_center` | –, °E, °N | Cell index and centre |
| `n_drifters`, `n_hours` | count | Distinct drogued drifters and drogued hours in the cell |
| `mean_ve_cmps`, `mean_vn_cmps` | cm/s | Hour-weighted mean eastward and northward velocity |
| `mean_vector_speed_cmps` | cm/s | Magnitude of the mean velocity vector |
| `ve_ci_low_cmps`, `ve_ci_high_cmps`, `ve_ci_halfwidth_cmps` (and `vn_…`) | cm/s | 95% percentile bootstrap CI per component (B = 3000, resampling whole drifters) and its half-width |
| `bootstrap_vector_radius95_cmps` | cm/s | **U95**: 95th percentile of the distance between bootstrap mean vectors and the cell mean |
| `snr` | – | `mean_vector_speed_cmps / U95`. Above 1 means the direction of the mean current is resolved |
| `region` | – | `jet` if the mean speed is ≥ 34 cm/s (Otsu threshold from 05), else `recirculation`. Cells without data are also labelled `recirculation` |
| `N_star` | drifters | Drifters needed for a ±10 cm/s mean in this region: 83 (jet), 26 (recirculation) |
| `reliable` | bool | **Reliability flag**: `n_drifters ≥ N_star` **and** `U95 ≤ 10 cm/s` |
| `direction_resolved` | bool | `reliable` **and** `snr > 1` |
| `drifters_needed` | drifters | `max(N_star − n_drifters, 0)`; NaN where no data |
| `weighting_diff_cmps` | cm/s | Magnitude of the difference between the per-drifter-weighted and hour-weighted mean vectors |
| `weighting_sensitive` | nullable bool | `weighting_diff_cmps > U95`; NA where no interval |
| `category`, `category_label` | – | 0 no data · 1 too few drifters · 2 enough drifters, not yet precise · 3 reliable · 4 reliable, direction resolved |

### `product_sst_1deg`

| Column | Units | Meaning |
|---|---|---|
| `iy`, `ix`, `lon_center`, `lat_center`, `n_drifters`, `n_hours` | | As above, for hours with valid SST (all drifters) |
| `mean_sst_c` | °C | Hour-weighted mean SST |
| `sst_ci_low_c`, `sst_ci_high_c`, `sst_ci_halfwidth_c` | °C | 95% whole-drifter bootstrap CI and half-width |
| `n_seasons` | 0–4 | Seasons (DJF, MAM, JJA, SON) with any SST data in the cell |
| `sst_balanced_c` | °C | Mean of the four seasonal means (NaN unless all four seasons are present) |
| `seasonal_bias_c` | °C | `mean_sst_c − sst_balanced_c`: the bias from uneven seasonal sampling |
| `reliable` | bool | **Reliability flag**: all 4 seasons, CI half-width ≤ 0.5 °C **and** \|seasonal bias\| ≤ 0.5 °C |
| `sst_category`, `sst_category_label` | – | First failing condition: 0 no data · 1 missing a season · 2 uncertainty too large · 3 seasonal bias too large · 4 reliable |

### `product_enso_velocity_1deg` and `product_enso_sst_1deg`

These cover the window 2002-01 to 2022-10. El Niño months follow the RONI episode definition, and
the non-El Niño phase pools Neutral and La Niña. Columns ending `_en` describe El Niño and `_nonen`
describe non-El Niño. The per-phase columns repeat the 06 definitions within each phase:
`n_drifters_*`, `n_hours_*`, `mean_*`, CI columns, `U95_cmps_*`, `snr_*`.

| Column | Units | Meaning |
|---|---|---|
| `region`, `N_star` | | Full-record region and N* from 06 |
| `anom_ve_cmps_*`, `anom_vn_cmps_*`, `anom_sst_c_*` | cm/s, °C | Phase mean of seasonal anomalies (each hour minus its cell-season mean over the window) |
| `reliable_*` | bool | Velocity: `n_drifters_* ≥ N_star` and `U95_cmps_* ≤ 10`. SST: `sst_ci_halfwidth_c_* ≤ 0.5` |
| `achievable_E95_cmps_*` | cm/s | E95 expected at this phase's drifter count, from 05's fitted data-denial curve |
| `drifters_needed_*` | drifters | `max(N_star − n_drifters_*, 0)`; NaN where the cell has no full-record velocity |
| `d_ve_cmps`, `d_vn_cmps`, `abs_du_cmps` / `d_sst_c`, `abs_d_sst_c` | cm/s, °C | El Niño − non-El Niño difference of the anomaly means, and its magnitude |
| `tested` | bool | ≥ 2 drifters in each phase |
| `p_value` | – | Block-permutation p-value: the monthly phase series is shifted circularly by 12 to 238 months (227 shifts), giving `(1 + #null ≥ observed) / (1 + #valid)`. NaN if untested or < 100 valid shifts |
| `n_valid_perms` | count | Shifts in which both phases still had ≥ 2 drifters |
| `significant` | bool | **Significance mask**: `p_value < 0.05` (NaN → False). This is a cell-level test; field significance is reported in `07_summary.json` |
| `robust` | bool | `significant` and reliable in both phases |
| `significant_nonEN_reliable` | bool | `significant` and reliable in the non-El Niño phase |

## Notebook → figure and table mapping

| Notebook | Figures (`figures/<notebook>/`) | Tables (`results/<notebook>/`) |
|---|---|---|
| 01 | `roni_enso_phases.png` (RONI with ENSO phases) | `enso_phase_support.csv` (months, hours and drifters per phase), `data_prep_summary.json` |
| 02 | `drogue_share_map.png`, `drifters_per_cell_all_vs_drogued.png`, `drifters_per_cell_by_phase.png`, `coverage_vs_threshold.png`, `history_by_year.png` | `drogue_policy_support.csv`, `drogue_cost.csv`, `support_{vel,sst}_by_phase.csv`, `coverage_vs_threshold.csv`, `enso_events.csv`, `history_by_year.csv`, `cell_support_medians.csv`, `02_summary.json` |
| 03 | `climatology_vel_sst_initial.png`, `weighting_sensitivity_initial.png` (quick-look, ≥ 5 drifters) | `03_summary.json` |
| 04 | `bootstrap_ci_halfwidth_map_initial.png`, `bootstrap_U95_map_initial.png`, `U95_vs_ndrifters.png`, `example_bootstrap.png`, `bootstrap_sst_map_initial.png` | `bootstrap_{velocity,sst}_1deg.csv`, `bootstrap_summary.json` |
| 05 | `otsu_speed_histogram.png`, `data_denial_curves.png`, `n_star_map.png` | `data_denial_results.csv`, `05_summary.json` |
| 06 | `reliability_map_velocity.png`, `drifters_needed_map.png`, `reliability_map_sst.png`, `sst_seasonal_bias_map.png` | `product_{velocity,sst}_1deg.csv`, `06_summary.json` |
| 07 | `enso_velocity_difference_map.png`, `enso_sst_difference_map.png`, `enso_field_significance.png`, `elnino_achievable_precision_map.png`, `elnino_months_by_season.png` | `product_enso_{velocity,sst}_1deg.csv`, `07_summary.json` |
| 08 | `climatology_vel_sst_reliability.png`, `weighting_sensitivity_reliability.png`, `U95_map_reliability.png`, `sst_halfwidth_map_reliability.png` (report versions of the 03 and 04 maps) | `08_summary.json` |

## Data sources and citations

### Data sources

* **GDP hourly drifter data** (v2.01.1; Elipot et al. 2016, 2022). Accessed on 9 November 2026
  through CloudDrift 0.48.1 (`clouddrift.datasets.gdp1h()`, <https://github.com/Cloud-Drift/clouddrift>)
  from NOAA's public Zarr store on the AWS Open Data registry
  (<https://registry.opendata.aws/noaa-oar-hourly-gdp/>). SST and its quality flag (`flg_sst`) are
  documented in Elipot et al. (2022), *Scientific Data*.
* **Relative Oceanic Niño Index** (CPC 2026c). Committed as `data/RONI.ascii.txt`, downloaded on
  11 November 2026. ENSO episodes follow NOAA's definition (CPC 2026a): RONI at or beyond ±0.5 °C
  for at least five consecutive overlapping seasons.

### References

UNSW Harvard style. The CPC labels match the reference list in the final report.

Climate Prediction Center (CPC) 2026a, *Implementing a Relative Oceanic Niño Index effective
February 1, 2026*, Public Information Statement 26-05, National Weather Service, National Oceanic
and Atmospheric Administration, viewed 11 November 2026,
<https://weather.gov/media/notification/pdf_2026/pns26-05_Relative_ONI.pdf>.

Climate Prediction Center (CPC) 2026c, *Relative Oceanic Niño Index (RONI)*, dataset, National
Oceanic and Atmospheric Administration, viewed 11 November 2026,
<https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt>.

Elipot, S, Lumpkin, R, Perez, RC, Lilly, JM, Early, JJ & Sykulski, AM 2016, 'A global surface
drifter data set at hourly resolution', *Journal of Geophysical Research: Oceans*, vol. 121, no. 5,
pp. 2937–2966, DOI:10.1002/2016JC011716.

Elipot, S, Sykulski, A, Lumpkin, R, Centurioni, L & Pazos, M 2022, 'A dataset of hourly sea surface
temperature from drifting buoys', *Scientific Data*, vol. 9, article 567,
DOI:10.1038/s41597-022-01670-2.

Elipot, S, Sykulski, A, Lumpkin, R, Centurioni, L & Pazos, M 2022, *Hourly location, current
velocity, and temperature collected from Global Drifter Program drifters world-wide*, version
2.01.1, dataset, NOAA National Centers for Environmental Information, viewed 9 November 2026,
<https://doi.org/10.25921/x46c-3620>.
