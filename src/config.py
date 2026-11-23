"""Single configuration for the whole pipeline (notebooks 01-08).

Everything that defines *what* is analysed lives here: study region, grid
resolution, date windows, method thresholds, random seed and file paths.
To run the pipeline for a different region, edit the "Study region" block
(and REGION_NAME), then rerun from notebook 01. See README.md.

Notebooks import it with:
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path.cwd() if Path("config.py").exists() else Path.cwd() / "src"))
    import config as cfg
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Study region and grid
# ---------------------------------------------------------------------------
REGION_NAME = "kuroshio"            # used in file names of the extract and clean data
LON_MIN, LON_MAX = 115.0, 145.0     # degrees East, -180..180, LON_MIN < LON_MAX (no dateline crossing)
LAT_MIN, LAT_MAX = 15.0, 40.0       # degrees North
RES = 1.0                           # grid cell size (degrees)

# ---------------------------------------------------------------------------
# Date windows
# ---------------------------------------------------------------------------
# Months covered by in-box drifter data ("YYYY-MM", "YYYY-MM"); None = derive from
# the first and last observation in the extract (Kuroshio: 1990-03 to 2022-10).
STUDY = None
# ENSO comparison window for notebook 07 (both months inclusive).
ENSO_WINDOW = ("2002-01", "2022-10")

# ---------------------------------------------------------------------------
# Data preparation (01)
# ---------------------------------------------------------------------------
ENSO_THRESH = 0.5        # |RONI| threshold (°C), NOAA CPC episode definition
MIN_SEASONS = 5          # consecutive overlapping 3-month seasons above threshold
SST_GOOD_FLAG = 5        # keep SST only where flg_sst == 5

# ---------------------------------------------------------------------------
# Method settings (02-07)
# ---------------------------------------------------------------------------
SEED = 20261105                  # base seed; every random draw uses SeedSequence([SEED, iy, ix, stream])
TARGET_CMPS = 10.0               # velocity precision target (cm/s)
SST_TARGET_C = 0.5               # SST precision target (°C)

SUPPORT_THRESHOLDS = (5, 10, 20)  # 02: drifter-count thresholds in the support tables
MIN_DRIFTERS_STATS = 2            # 03: cells used for weighting statistics (= cells with a bootstrap CI)
WEIGHTING_JET_SPEED = 0.40        # 03: "jet" cells for the weighting speed comparison (m/s)

BOOT_B = 3000                     # 04, 07: whole-drifter bootstrap replicates per cell
BOOT_BANDS = (2, 5, 10, 20)       # 04: lower edges of drifter-count bands in the summary (last band open)

DENIAL_MIN_TEST_DRIFTERS = 60     # 05: cells with at least this many drifters are tested
DENIAL_KS = (3, 5, 10, 15, 20, 30)  # 05: drifters kept per subsample
DENIAL_B = 500                    # 05: subsamples per cell per k

ENSO_MIN_LAG = 12                 # 07: smallest circular shift (months) in the permutation null
ENSO_MIN_DRIFTERS_TEST = 2        # 07: drifters needed in each phase for a cell to be tested
ENSO_MIN_VALID_PERMS = 100        # 07: fewer valid permutations -> p-value NaN
ALPHA = 0.05                      # 07: significance level (cell and field)

# Random streams (third element of the SeedSequence), kept distinct across notebooks
STREAMS = {"boot_vel": 1, "boot_sst": 2, "denial": 3,
           "enso_vel_en": 4, "enso_vel_nonen": 5, "enso_sst_en": 6, "enso_sst_nonen": 7}

# ---------------------------------------------------------------------------
# Paths (resolved from the repo root, so the working directory does not matter)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"          # input data only: RONI file and the GDP extract
# Optional sub-folder for a non-default run, e.g. "gulfstream" -> results/gulfstream/..., figures/gulfstream/...
OUTPUT_SUBDIR = os.environ.get("GDP_OUTPUT_SUBDIR", "")
RESULTS_DIR = ROOT / "results" / OUTPUT_SUBDIR   # every numeric output (parquet, csv, json, npy, npz)
FIG_DIR = ROOT / "figures" / OUTPUT_SUBDIR       # every figure (png)

RONI_PATH = DATA_DIR / "RONI.ascii.txt"          # https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt
RAW_PATH = DATA_DIR / f"{REGION_NAME}_obs.parquet"            # in-box GDP hourly extract (01)
META_PATH = DATA_DIR / f"{REGION_NAME}_obs_metadata.json"     # dataset attrs + extraction bounds (01)
CLEAN_NAME = f"{REGION_NAME}_obs_clean.parquet"              # written by 01 into results/01_data_prep_roni_gdp

# Extraction mode for 01: "auto" = extract only if RAW_PATH is missing,
# "force" = always re-extract, "never" = fail if RAW_PATH is missing.
EXTRACT = os.environ.get("GDP_EXTRACT", "auto")
assert EXTRACT in ("auto", "force", "never"), f"GDP_EXTRACT must be auto/force/never, not {EXTRACT!r}"


def out_dir(notebook):
    """results/<notebook>/ (created if needed)."""
    p = RESULTS_DIR / notebook
    p.mkdir(parents=True, exist_ok=True)
    return p


def fig_dir(notebook):
    """figures/<notebook>/ (created if needed)."""
    p = FIG_DIR / notebook
    p.mkdir(parents=True, exist_ok=True)
    return p


def results(notebook):
    """results/<notebook>/ of an earlier notebook (must already exist)."""
    p = RESULTS_DIR / notebook
    assert p.exists(), f"{p} not found: run notebook {notebook} first"
    return p


# ---------------------------------------------------------------------------
# Sanity checks for the default (Kuroshio) run
# ---------------------------------------------------------------------------
# Values recorded from the published run. They are checked only when the
# configuration above is the default one; any other region or window skips them.
DEFAULT_RUN = dict(region=(115.0, 145.0, 15.0, 40.0), res=1.0, enso_window=("2002-01", "2022-10"))
KUROSHIO_EXPECTED = {
    "study_months": ("1990-03", "2022-10"),
    "flag_drogued_after_loss": 14,
    "drogued_obs": 2_135_791,
    "drogued_drifters": 1_177,
    "cells_ge2_drifters": 577,
    "el_nino_events_in_window": 6,
    "n_permutation_lags": 227,
}


def is_default_run():
    return ((LON_MIN, LON_MAX, LAT_MIN, LAT_MAX) == DEFAULT_RUN["region"]
            and RES == DEFAULT_RUN["res"] and tuple(ENSO_WINDOW) == DEFAULT_RUN["enso_window"])


def check_expected(key, value):
    """Assert a recorded Kuroshio value, only for the default configuration."""
    if is_default_run():
        expected = KUROSHIO_EXPECTED[key]
        assert value == expected, f"{key}: got {value}, expected {expected} for the default Kuroshio run"
