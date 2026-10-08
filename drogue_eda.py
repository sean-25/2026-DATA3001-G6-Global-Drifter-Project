"""
Step 3: Drogue policy coverage analysis for the Kuroshio region (GDP hourly).

What this does
--------------
1. Prints diagnostics on how drogue information is stored (so we can confirm
   how "unknown" status should be defined).
2. Streams through the dataset in batches of drifters (same ragged-array
   approach as Step 2), keeps only observations inside the region box, and
   classifies each observation as:
       drogued    : drogue_status True  AND consistent with drogue_lost_date
                    (no lost date recorded, or time is before the lost date)
       undrogued  : drogue_status False AND a lost date exists AND
                    time >= lost date
       unknown    : everything else (status contradicts the lost date, or
                    cannot be verified against it)
3. Compares three policies:
       P1  drogued only                       (primary velocity analysis)
       P2  drogued + unknown                  (upper-bound sensitivity)
       P3  all observations                   (slip-bias quantification, SST)
   on SPATIAL coverage (grid cells with >= MIN_OBS observations) and
   TEMPORAL coverage (observations per year and per season).
4. Reports mean speed by category (undrogued is expected to read faster
   because of wind slip).

Outputs (written to the current directory)
------------------------------------------
  drogue_policy_summary.csv    one row per policy
  drogue_category_summary.csv  one row per drogue category
  drogue_policy_by_year.csv    observations per year, per policy
  drogue_policy_by_season.csv  observations per season, per policy
  drogue_cell_counts.npz       per-category gridded counts (for maps later)

Paste the printed output back to me and I will fill in the coverage table
in the proposal.
"""

import numpy as np
import pandas as pd
from clouddrift.datasets import gdp1h

# ---------------------------------------------------------------------------
# Settings -- edit freely; nothing below depends on the exact region.
# ---------------------------------------------------------------------------
REGION = {"lat_min": 15, "lat_max": 40, "lon_min": 115, "lon_max": 145}  # Kuroshio
GRID_RES = 1.0      # degrees
MIN_OBS = 20        # a cell counts as "covered" if it has at least this many obs
BATCH_SIZE = 500    # drifters per network request
YEAR0, YEAR1 = 1987, 2023   # year range for temporal counts (record: 1987-2022)

# ---------------------------------------------------------------------------
# 1. Open dataset and run diagnostics on drogue information
# ---------------------------------------------------------------------------
print("Opening GDP hourly dataset...")
ds = gdp1h()

ids = ds["id"].values
rowsize = ds["rowsize"].values.astype(np.int64)
lost = ds["drogue_lost_date"].values          # traj-level, datetime64 (may be NaT)
n_traj = len(ids)
obs_end = np.cumsum(rowsize)
obs_start = obs_end - rowsize

print("\n" + "=" * 80)
print("DROGUE DIAGNOSTICS")
print("=" * 80)
print(f"drogue_status dtype (obs-level): {ds['drogue_status'].dtype}")
print(f"drogue_lost_date dtype (traj-level): {lost.dtype}")
n_nat = int(np.isnat(lost).sum())
print(f"Drifters with NO recorded drogue_lost_date (NaT): {n_nat:,} of {n_traj:,} "
      f"({100 * n_nat / n_traj:.1f}%)")
print("NOTE: drogue_status is a boolean, so it cannot itself hold 'unknown'. "
      "'Unknown' is defined here as status that is inconsistent with, or "
      "cannot be verified against, drogue_lost_date.")

# ---------------------------------------------------------------------------
# 2. Set up grid and accumulators
# ---------------------------------------------------------------------------
nlat = int(np.ceil((REGION["lat_max"] - REGION["lat_min"]) / GRID_RES))
nlon = int(np.ceil((REGION["lon_max"] - REGION["lon_min"]) / GRID_RES))
ncell = nlat * nlon
n_years = YEAR1 - YEAR0 + 1
CATS = ["drogued", "undrogued", "unknown"]

cell_counts = {c: np.zeros(ncell, dtype=np.int64) for c in CATS}
year_counts = {c: np.zeros(n_years, dtype=np.int64) for c in CATS}
season_counts = {c: np.zeros(4, dtype=np.int64) for c in CATS}   # DJF, MAM, JJA, SON
drifter_sets = {c: set() for c in CATS}
speed_sum = {c: 0.0 for c in CATS}
speed_n = {c: 0 for c in CATS}
first_time = {c: None for c in CATS}
last_time = {c: None for c in CATS}

# ---------------------------------------------------------------------------
# 3. Stream through the data in batches of drifters
# ---------------------------------------------------------------------------
n_batches = int(np.ceil(n_traj / BATCH_SIZE))
print(f"\nProcessing {n_traj:,} drifters in {n_batches} batches...")

for b in range(n_batches):
    i0 = b * BATCH_SIZE
    i1 = min(i0 + BATCH_SIZE, n_traj)
    sl = slice(int(obs_start[i0]), int(obs_end[i1 - 1]))

    batch = ds.isel(obs=sl)[["lat", "lon", "time", "ve", "vn", "drogue_status"]].load()
    lat = batch["lat"].values
    lon = batch["lon"].values

    # Keep only observations inside the region box (cuts the data down early)
    m = ((lat >= REGION["lat_min"]) & (lat < REGION["lat_max"]) &
         (lon >= REGION["lon_min"]) & (lon < REGION["lon_max"]))
    if not m.any():
        continue

    local_rowsize = rowsize[i0:i1]
    id_rep = np.repeat(ids[i0:i1], local_rowsize)[m]
    lost_rep = np.repeat(lost[i0:i1], local_rowsize)[m]

    lat = lat[m]
    lon = lon[m]
    time = batch["time"].values[m]
    status = batch["drogue_status"].values.astype(bool)[m]
    speed = np.sqrt(batch["ve"].values[m].astype(np.float64) ** 2 +
                    batch["vn"].values[m].astype(np.float64) ** 2)

    # --- classify each observation ---
    has_lost = ~np.isnat(lost_rep)
    is_drogued = status & (~has_lost | (time < lost_rep))
    is_undrogued = (~status) & has_lost & (time >= lost_rep)
    is_unknown = ~(is_drogued | is_undrogued)
    masks = {"drogued": is_drogued, "undrogued": is_undrogued, "unknown": is_unknown}

    # --- grid cell, year, season indices ---
    ci = np.clip(np.floor((lat - REGION["lat_min"]) / GRID_RES).astype(int), 0, nlat - 1)
    cj = np.clip(np.floor((lon - REGION["lon_min"]) / GRID_RES).astype(int), 0, nlon - 1)
    cell = ci * nlon + cj
    year = time.astype("datetime64[Y]").astype(np.int64) + 1970
    yidx = np.clip(year - YEAR0, 0, n_years - 1)
    month = time.astype("datetime64[M]").astype(np.int64) % 12 + 1
    season = (month % 12) // 3          # Dec-Feb=0, Mar-May=1, Jun-Aug=2, Sep-Nov=3

    for c in CATS:
        cm = masks[c]
        if not cm.any():
            continue
        cell_counts[c] += np.bincount(cell[cm], minlength=ncell)
        year_counts[c] += np.bincount(yidx[cm], minlength=n_years)
        season_counts[c] += np.bincount(season[cm], minlength=4)
        drifter_sets[c].update(np.unique(id_rep[cm]).tolist())

        sp = speed[cm]
        ok = ~np.isnan(sp)
        speed_sum[c] += float(sp[ok].sum())
        speed_n[c] += int(ok.sum())

        t0, t1 = time[cm].min(), time[cm].max()
        first_time[c] = t0 if first_time[c] is None else min(first_time[c], t0)
        last_time[c] = t1 if last_time[c] is None else max(last_time[c], t1)

    if (b + 1) % 5 == 0 or (b + 1) == n_batches:
        print(f"  batch {b + 1}/{n_batches} done")

# ---------------------------------------------------------------------------
# 4. Category summary (composition + wind-slip check)
# ---------------------------------------------------------------------------
total_obs = sum(int(cell_counts[c].sum()) for c in CATS)
cat_rows = []
for c in CATS:
    n = int(cell_counts[c].sum())
    cat_rows.append({
        "category": c,
        "n_obs": n,
        "pct_of_region_obs": 100 * n / total_obs if total_obs else np.nan,
        "n_unique_drifters": len(drifter_sets[c]),
        "mean_speed_m_s": speed_sum[c] / speed_n[c] if speed_n[c] else np.nan,
        "first_obs": first_time[c],
        "last_obs": last_time[c],
    })
cat_summary = pd.DataFrame(cat_rows)

print("\n" + "=" * 90)
print("DROGUE CATEGORY SUMMARY (inside the region box)")
print("=" * 90)
print(cat_summary.to_string(index=False))

# ---------------------------------------------------------------------------
# 5. Policy comparison: spatial and temporal coverage
# ---------------------------------------------------------------------------
POLICIES = {
    "P1 drogued only": ["drogued"],
    "P2 drogued + unknown": ["drogued", "unknown"],
    "P3 all observations": ["drogued", "undrogued", "unknown"],
}

p3_cells = sum(cell_counts[c] for c in POLICIES["P3 all observations"])
p3_obs = int(p3_cells.sum())
p3_cells_ok = int((p3_cells >= MIN_OBS).sum())

pol_rows, year_rows, season_rows = [], [], []
season_names = ["DJF", "MAM", "JJA", "SON"]

for name, cats in POLICIES.items():
    cells = sum(cell_counts[c] for c in cats)
    yrs = sum(year_counts[c] for c in cats)
    seas = sum(season_counts[c] for c in cats)
    drifters = set().union(*[drifter_sets[c] for c in cats])
    n_ok = int((cells >= MIN_OBS).sum())
    yrs_with_data = np.arange(YEAR0, YEAR1 + 1)[yrs > 0]

    pol_rows.append({
        "policy": name,
        "n_obs": int(cells.sum()),
        "pct_of_P3_obs": 100 * cells.sum() / p3_obs if p3_obs else np.nan,
        "n_unique_drifters": len(drifters),
        f"cells_with_>={MIN_OBS}_obs": n_ok,
        "pct_of_grid_cells_covered": 100 * n_ok / ncell,
        "pct_of_P3_covered_cells_retained": 100 * n_ok / p3_cells_ok if p3_cells_ok else np.nan,
        "cells_with_any_obs": int((cells > 0).sum()),
        "years_with_data": len(yrs_with_data),
        "first_year": int(yrs_with_data.min()) if len(yrs_with_data) else None,
        "last_year": int(yrs_with_data.max()) if len(yrs_with_data) else None,
    })
    for y, n in zip(range(YEAR0, YEAR1 + 1), yrs):
        year_rows.append({"policy": name, "year": y, "n_obs": int(n)})
    for s, n in zip(season_names, seas):
        season_rows.append({"policy": name, "season": s, "n_obs": int(n)})

pol_summary = pd.DataFrame(pol_rows)
by_year = pd.DataFrame(year_rows).pivot(index="year", columns="policy", values="n_obs")
by_season = pd.DataFrame(season_rows).pivot(index="season", columns="policy", values="n_obs").loc[season_names]

print("\n" + "=" * 90)
print(f"POLICY COMPARISON  (grid {GRID_RES} deg, {ncell} cells; 'covered' = >= {MIN_OBS} obs)")
print("=" * 90)
print(pol_summary.to_string(index=False))

print("\n" + "=" * 90)
print("OBSERVATIONS PER SEASON, BY POLICY")
print("=" * 90)
print(by_season.to_string())

print("\n" + "=" * 90)
print("OBSERVATIONS PER YEAR, BY POLICY")
print("=" * 90)
print(by_year.to_string())

# ---------------------------------------------------------------------------
# 6. Save outputs
# ---------------------------------------------------------------------------
cat_summary.to_csv("drogue_category_summary.csv", index=False)
pol_summary.to_csv("drogue_policy_summary.csv", index=False)
by_year.to_csv("drogue_policy_by_year.csv")
by_season.to_csv("drogue_policy_by_season.csv")
np.savez(
    "drogue_cell_counts.npz",
    nlat=nlat, nlon=nlon, grid_res=GRID_RES,
    lat_min=REGION["lat_min"], lon_min=REGION["lon_min"],
    **{c: cell_counts[c].reshape(nlat, nlon) for c in CATS},
)
print("\nSaved: drogue_category_summary.csv, drogue_policy_summary.csv, "
      "drogue_policy_by_year.csv, drogue_policy_by_season.csv, drogue_cell_counts.npz")
print("Please paste the printed output back to me.")