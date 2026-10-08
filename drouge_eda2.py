"""
Step 3 (v4): How the drogue policy changes spatial and temporal coverage
in the Kuroshio region (GDP hourly product).

Policies
--------
  P1  drogued only
  P2  drogued + undrogued          (every observation with VERIFIED drogue state)
  P3  all observations
  UNKNOWN = P3 - P2  (all observations minus drogued plus undrogued)

Why "drogued" and "undrogued" need positive evidence
----------------------------------------------------
drogue_status is a boolean, so every observation is True or False and a naive
residual would always be empty. An observation is therefore only called
drogued / undrogued if drogue_lost_date EXISTS and agrees with the flag:

  drogued    status True,  a lost date exists, time <  lost date
  undrogued  status False, a lost date exists, time >= lost date
  unknown    everything else, split into two reasons:
     unknown_no_date        the drifter has no recorded drogue_lost_date
     unknown_contradiction  a lost date exists but the flag disagrees with it

Extra check: drifters whose lost date equals their end of record (+-1 day).
That may be an end-of-record default rather than a measured loss. Those
drogued observations are kept in their own class (drogued_lost_eq_end),
included in P1 by default, and a sensitivity row "P1s" shows coverage if they
are excluded.

Coverage measures (spatial and temporal)
----------------------------------------
A cell is SUPPORTED only if it passes three data-based screens:
   (a) >= MIN_OBS hourly observations (a minimum screen only)
   (b) >= MIN_DRIFTERS distinct drifters
   (c) observations in >= MIN_YEARS distinct years
       (seasonal fields: within that season)
Temporal coverage: observations AND distinct drifters per year and per season.
Bootstrap uncertainty (the fourth criterion) is applied later, in the main
analysis. All thresholds are starting values -- tune them.

typedeath (why a drifter's whole record ended: 0 alive, 1 aground, 2 picked up,
3 stopped transmitting, 4 sporadic, 5 bad batteries, 6 inactive) is NOT a
drogue field. It is used only for diagnostics: coverage by typedeath, and a
check of drogued speed near the end of record.

Outputs (current directory)
---------------------------
  drogue_class_summary.csv, drogue_policy_summary.csv,
  drogue_policy_by_year.csv, drogue_policy_by_year_drifters.csv,
  drogue_policy_by_season.csv, drogue_policy_supported_by_season.csv,
  drogue_by_typedeath.csv, drogue_endoflife_speed.csv,
  drogue_lost_vs_end_by_typedeath.csv, drogue_cell_support.npz

Paste the printed output back to me.
"""

import numpy as np
import pandas as pd
from clouddrift.datasets import gdp1h

# ---------------------------------------------------------------------------
# Settings -- edit freely; nothing below depends on the exact region.
# ---------------------------------------------------------------------------
REGION = {"lat_min": 15, "lat_max": 40, "lon_min": 115, "lon_max": 145}  # Kuroshio
GRID_RES = 1.0        # degrees
MIN_OBS = 20
MIN_DRIFTERS = 5
MIN_DAYS = 20
DAY0 = np.datetime64("1987-01-01", "D")
N_DAYS = int((np.datetime64("2023-01-01", "D") - DAY0).astype(int))
_days = DAY0 + np.arange(N_DAYS)
_months = _days.astype("datetime64[M]").astype(np.int64) % 12 + 1
DAY_SEASON = (_months % 12) // 3
BATCH_SIZE = 500      # drifters per network request
YEAR0, YEAR1 = 1987, 2023

TD_NAMES = {0: "0 alive", 1: "1 aground", 2: "2 picked up", 3: "3 stopped transmitting",
            4: "4 sporadic", 5: "5 bad batteries", 6: "6 inactive", 7: "other/missing"}
EOL_BINS = ["last 0-24h", "24-72h before end", ">72h before end"]
SEASONS = ["DJF", "MAM", "JJA", "SON"]

# ---------------------------------------------------------------------------
# 1. Open dataset; trajectory-level diagnostics (cheap: no observation data)
# ---------------------------------------------------------------------------
print("Opening GDP hourly dataset...")
ds = gdp1h()

ids = ds["id"].values
rowsize = ds["rowsize"].values.astype(np.int64)
lost = ds["drogue_lost_date"].values
end_date = ds["end_date"].values
typedeath = ds["typedeath"].values.astype(np.int64)
n_traj = len(ids)
obs_end = np.cumsum(rowsize)
obs_start = obs_end - rowsize
td_idx_traj = np.where((typedeath >= 0) & (typedeath <= 6), typedeath, 7)

one_day = np.timedelta64(1, "D")
has_lost_traj = ~np.isnat(lost)
lost_eq_end_traj = has_lost_traj & ~np.isnat(end_date) & (np.abs(lost - end_date) <= one_day)

print("\n" + "=" * 90)
print("TRAJECTORY-LEVEL DIAGNOSTICS (whole dataset)")
print("=" * 90)
print(f"Drifters: {n_traj:,}")
print(f"No recorded drogue_lost_date:            {int((~has_lost_traj).sum()):,} "
      f"({100 * (~has_lost_traj).mean():.1f}%)")
print(f"Lost date equals end of record (+-1 d):  {int(lost_eq_end_traj.sum()):,} "
      f"({100 * lost_eq_end_traj.mean():.1f}%)")

rel = np.full(n_traj, "lost date before end", dtype=object)
rel[~has_lost_traj] = "no lost date"
rel[has_lost_traj & ~np.isnat(end_date) & (lost > end_date + one_day)] = "lost date after end"
rel[lost_eq_end_traj] = "lost date == end date (+-1d)"
tl = pd.DataFrame({"typedeath": [TD_NAMES[i] for i in td_idx_traj], "drogue_lost_vs_end": rel})
xtab = pd.crosstab(tl["typedeath"], tl["drogue_lost_vs_end"], margins=True)
print("\nHow does drogue_lost_date relate to the end of record, by typedeath?")
print(xtab.to_string())
xtab.to_csv("drogue_lost_vs_end_by_typedeath.csv")

# ---------------------------------------------------------------------------
# 2. Grid and accumulators
# ---------------------------------------------------------------------------
nlat = int(np.ceil((REGION["lat_max"] - REGION["lat_min"]) / GRID_RES))
nlon = int(np.ceil((REGION["lon_max"] - REGION["lon_min"]) / GRID_RES))
ncell = nlat * nlon
n_years = YEAR1 - YEAR0 + 1
CATS = ["drogued", "drogued_lost_eq_end", "undrogued",
        "unknown_no_date", "unknown_contradiction"]

cell_counts = {c: np.zeros(ncell, dtype=np.int64) for c in CATS}
season_cell_counts = {c: np.zeros(4 * ncell, dtype=np.int64) for c in CATS}
cell_season_year = {c: np.zeros((ncell, 4, n_years), dtype=bool) for c in CATS}
cell_day = {c: np.zeros((ncell, N_DAYS), dtype=bool) for c in CATS}
pair_keys = {c: [] for c in CATS}        # unique (season, cell, drifter) keys
year_keys = {c: [] for c in CATS}        # unique (year, drifter) keys
year_counts = {c: np.zeros(n_years, dtype=np.int64) for c in CATS}
season_counts = {c: np.zeros(4, dtype=np.int64) for c in CATS}
td_counts = {c: np.zeros(8, dtype=np.int64) for c in CATS}
drifter_sets = {c: set() for c in CATS}
td_drifters = {t: set() for t in range(8)}
speed_sum = {c: 0.0 for c in CATS}
speed_n = {c: 0 for c in CATS}
eol_sum = np.zeros(8 * 3)
eol_n = np.zeros(8 * 3)

# ---------------------------------------------------------------------------
# 3. Stream through drifters in batches
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
    time_full = batch["time"].values
    local_rowsize = rowsize[i0:i1]

    # hours until each drifter's last observation (needs the full track)
    last_idx = np.clip(np.cumsum(local_rowsize) - 1, 0, len(time_full) - 1)
    last_time_rep = np.repeat(time_full[last_idx], local_rowsize)
    hours_to_end_full = (last_time_rep - time_full) / np.timedelta64(1, "h")

    m = ((lat >= REGION["lat_min"]) & (lat < REGION["lat_max"]) &
         (lon >= REGION["lon_min"]) & (lon < REGION["lon_max"]))
    if not m.any():
        continue

    id_rep = np.repeat(ids[i0:i1], local_rowsize)[m]
    gidx_rep = np.repeat(np.arange(i0, i1), local_rowsize)[m]
    lost_rep = np.repeat(lost[i0:i1], local_rowsize)[m]
    leqe_rep = np.repeat(lost_eq_end_traj[i0:i1], local_rowsize)[m]
    td_rep = np.repeat(td_idx_traj[i0:i1], local_rowsize)[m]

    lat, lon, time = lat[m], lon[m], time_full[m]
    hours_to_end = hours_to_end_full[m]
    status = batch["drogue_status"].values.astype(bool)[m]
    speed = np.sqrt(batch["ve"].values[m].astype(np.float64) ** 2 +
                    batch["vn"].values[m].astype(np.float64) ** 2)

    # --- classification: positive evidence required for drogued / undrogued ---
    has_lost = ~np.isnat(lost_rep)
    drogued_any = has_lost & status & (time < lost_rep)
    undrogued = has_lost & (~status) & (time >= lost_rep)
    unknown_no_date = ~has_lost
    unknown_contra = has_lost & ~(drogued_any | undrogued)
    masks = {
        "drogued": drogued_any & ~leqe_rep,
        "drogued_lost_eq_end": drogued_any & leqe_rep,
        "undrogued": undrogued,
        "unknown_no_date": unknown_no_date,
        "unknown_contradiction": unknown_contra,
    }

    # --- indices ---
    ci = np.clip(np.floor((lat - REGION["lat_min"]) / GRID_RES).astype(int), 0, nlat - 1)
    cj = np.clip(np.floor((lon - REGION["lon_min"]) / GRID_RES).astype(int), 0, nlon - 1)
    cell = ci * nlon + cj
    year = time.astype("datetime64[Y]").astype(np.int64) + 1970
    yidx = np.clip(year - YEAR0, 0, n_years - 1)
    month = time.astype("datetime64[M]").astype(np.int64) % 12 + 1
    season = (month % 12) // 3                      # DJF=0, MAM=1, JJA=2, SON=3
    sc = (season * ncell + cell).astype(np.int64)
    key = sc * n_traj + gidx_rep                    # (season, cell, drifter)
    ykey = yidx.astype(np.int64) * n_traj + gidx_rep  # (year, drifter)
    didx = np.clip((time.astype("datetime64[D]") - DAY0).astype(np.int64), 0, N_DAYS - 1)

    for c in CATS:
        cm = masks[c]
        if not cm.any():
            continue
        cell_counts[c] += np.bincount(cell[cm], minlength=ncell)
        season_cell_counts[c] += np.bincount(sc[cm], minlength=4 * ncell)
        cell_season_year[c][cell[cm], season[cm], yidx[cm]] = True
        cell_day[c][cell[cm], didx[cm]] = True
        pair_keys[c].append(np.unique(key[cm]))
        year_keys[c].append(np.unique(ykey[cm]))
        year_counts[c] += np.bincount(yidx[cm], minlength=n_years)
        season_counts[c] += np.bincount(season[cm], minlength=4)
        td_counts[c] += np.bincount(td_rep[cm], minlength=8)
        drifter_sets[c].update(np.unique(id_rep[cm]).tolist())
        for t in np.unique(td_rep[cm]):
            td_drifters[int(t)].update(np.unique(id_rep[cm & (td_rep == t)]).tolist())
        sp = speed[cm]
        ok = ~np.isnan(sp)
        speed_sum[c] += float(sp[ok].sum())
        speed_n[c] += int(ok.sum())

    # end-of-record speed check, drogued observations only
    dm = drogued_any & ~np.isnan(speed)
    if dm.any():
        tb = np.where(hours_to_end[dm] <= 24, 0, np.where(hours_to_end[dm] <= 72, 1, 2))
        flat = td_rep[dm] * 3 + tb
        eol_sum += np.bincount(flat, weights=speed[dm], minlength=24)
        eol_n += np.bincount(flat, minlength=24)

    if (b + 1) % 5 == 0 or (b + 1) == n_batches:
        print(f"  batch {b + 1}/{n_batches} done")

empty = np.array([], dtype=np.int64)
all_keys = {c: (np.unique(np.concatenate(pair_keys[c])) if pair_keys[c] else empty) for c in CATS}
all_ykeys = {c: (np.unique(np.concatenate(year_keys[c])) if year_keys[c] else empty) for c in CATS}

# ---------------------------------------------------------------------------
# 4. Class summary, unknown breakdown, typedeath diagnostics
# ---------------------------------------------------------------------------
total_obs = sum(int(cell_counts[c].sum()) for c in CATS)
class_summary = pd.DataFrame([{
    "class": c,
    "n_obs": int(cell_counts[c].sum()),
    "pct_of_region_obs": 100 * cell_counts[c].sum() / total_obs if total_obs else np.nan,
    "n_unique_drifters": len(drifter_sets[c]),
    "mean_speed_m_s": speed_sum[c] / speed_n[c] if speed_n[c] else np.nan,
} for c in CATS])
print("\n" + "=" * 90)
print("OBSERVATION CLASSES (inside the region box)")
print("=" * 90)
print(class_summary.to_string(index=False))

n_unknown = int(cell_counts["unknown_no_date"].sum() + cell_counts["unknown_contradiction"].sum())
n_p2 = int(sum(cell_counts[c].sum() for c in ["drogued", "drogued_lost_eq_end", "undrogued"]))
print(f"\nUNKNOWN (all observations minus drogued plus undrogued): {n_unknown:,} observations "
      f"= {100 * n_unknown / total_obs:.4f}% of all observations in the region")
print(f"Check: all ({total_obs:,}) - verified ({n_p2:,}) = {total_obs - n_p2:,}")

n_leqe = int(cell_counts["drogued_lost_eq_end"].sum())
n_dr = n_leqe + int(cell_counts["drogued"].sum())
print(f"Drogued observations from drifters whose lost date equals end of record: "
      f"{n_leqe:,} of {n_dr:,} drogued ({100 * n_leqe / max(n_dr, 1):.1f}%)")

td_table = pd.DataFrame({c: td_counts[c] for c in CATS}, index=[TD_NAMES[i] for i in range(8)])
td_table["total"] = td_table.sum(axis=1)
td_table["unique_drifters"] = [len(td_drifters[i]) for i in range(8)]
td_table["pct_drogued_of_total"] = (100 * (td_table["drogued"] + td_table["drogued_lost_eq_end"])
                                    / td_table["total"].replace(0, np.nan))
print("\n" + "=" * 90)
print("OBSERVATIONS BY CLASS AND typedeath (inside region)")
print("A low pct_drogued for a death type means drogued-only data under-represents it.")
print("=" * 90)
print(td_table.to_string())

eol_mean = np.where(eol_n > 0, eol_sum / np.maximum(eol_n, 1), np.nan).reshape(8, 3)
eol_df = pd.DataFrame(eol_mean, index=[TD_NAMES[i] for i in range(8)],
                      columns=[f"mean_speed {b}" for b in EOL_BINS])
for k, bname in enumerate(EOL_BINS):
    eol_df[f"n_obs {bname}"] = eol_n.reshape(8, 3).astype(int)[:, k]
print("\n" + "=" * 90)
print("DROGUED SPEED vs TIME-TO-END-OF-RECORD, by typedeath (m/s, inside region)")
print("If the last 0-24h is faster for aground / picked-up drifters, trimming may be justified.")
print("=" * 90)
print(eol_df.to_string())

# ---------------------------------------------------------------------------
# 5. Cell support and temporal coverage under each policy
# ---------------------------------------------------------------------------
def cell_support(cats):
    obs_full = sum(cell_counts[c] for c in cats)
    obs_seas = sum(season_cell_counts[c] for c in cats).reshape(4, ncell)

    keys = np.unique(np.concatenate([all_keys[c] for c in cats]))
    traj = keys % n_traj
    scell = keys // n_traj
    dr_seas = np.bincount(scell, minlength=4 * ncell).reshape(4, ncell)
    cell_of = scell % ncell
    dr_full = np.bincount(np.unique(cell_of.astype(np.int64) * n_traj + traj) // n_traj,
                          minlength=ncell)

    cd = np.zeros((ncell, N_DAYS), dtype=bool)
    for c in cats:
        cd |= cell_day[c]
    days_full = cd.sum(axis=1)
    days_seas = np.stack([cd[:, DAY_SEASON == k].sum(axis=1) for k in range(4)])  # (4, ncell)

    sup_full = (obs_full >= MIN_OBS) & (dr_full >= MIN_DRIFTERS) & (days_full >= MIN_DAYS)
    sup_seas = (obs_seas >= MIN_OBS) & (dr_seas >= MIN_DRIFTERS) & (days_seas >= MIN_DAYS)
    return {"obs": obs_full, "drifters": dr_full, "days": days_full, "supported": sup_full,
            "supported_season": sup_seas, "obs_only": obs_full >= MIN_OBS}

def drifters_per_year(cats):
    yk = np.unique(np.concatenate([all_ykeys[c] for c in cats]))
    return np.bincount(yk // n_traj, minlength=n_years)

POLICIES = {
    "P1 drogued only": ["drogued", "drogued_lost_eq_end"],
    "P2 drogued + undrogued": ["drogued", "drogued_lost_eq_end", "undrogued"],
    "P3 all observations": CATS,
    "P1s sensitivity (lost date = end excluded)": ["drogued"],
}
SHORT = {"P1 drogued only": "P1", "P2 drogued + undrogued": "P2",
         "P3 all observations": "P3", "P1s sensitivity (lost date = end excluded)": "P1s"}

support = {n: cell_support(c) for n, c in POLICIES.items()}
p3 = support["P3 all observations"]
p3_obs = int(p3["obs"].sum())
p3_supported = int(p3["supported"].sum())

pol_rows, year_rows, yrdr_rows, season_rows, supseason_rows = [], [], [], [], []
for name, cats in POLICIES.items():
    s = support[name]
    yrs = sum(year_counts[c] for c in cats)
    yr_dr = drifters_per_year(cats)
    seas = sum(season_counts[c] for c in cats)
    drifters = set().union(*[drifter_sets[c] for c in cats])
    yrs_with = np.arange(YEAR0, YEAR1 + 1)[yrs > 0]
    pol_rows.append({
        "policy": name,
        "n_obs": int(s["obs"].sum()),
        "pct_of_P3_obs": 100 * s["obs"].sum() / p3_obs if p3_obs else np.nan,
        "n_unique_drifters": len(drifters),
        f"cells_obs>={MIN_OBS}_only": int(s["obs_only"].sum()),
        "cells_supported_all_3_screens": int(s["supported"].sum()),
        "pct_of_grid_supported": 100 * s["supported"].sum() / ncell,
        "pct_of_P3_supported_kept": 100 * s["supported"].sum() / p3_supported if p3_supported else np.nan,
        "median_drifters_per_cell": float(np.median(s["drifters"][s["drifters"] > 0])) if (s["drifters"] > 0).any() else np.nan,
        "years_with_data": len(yrs_with),
        "first_year": int(yrs_with.min()) if len(yrs_with) else None,
        "last_year": int(yrs_with.max()) if len(yrs_with) else None,
    })
    for y, n, d in zip(range(YEAR0, YEAR1 + 1), yrs, yr_dr):
        year_rows.append({"policy": name, "year": y, "n_obs": int(n)})
        yrdr_rows.append({"policy": name, "year": y, "n_drifters": int(d)})
    for k, sn in enumerate(SEASONS):
        season_rows.append({"policy": name, "season": sn, "n_obs": int(seas[k])})
        supseason_rows.append({"policy": name, "season": sn,
                               "supported_cells": int(s["supported_season"][k].sum())})

pol_summary = pd.DataFrame(pol_rows)
by_year = pd.DataFrame(year_rows).pivot(index="year", columns="policy", values="n_obs")
by_year_dr = pd.DataFrame(yrdr_rows).pivot(index="year", columns="policy", values="n_drifters")
by_season = pd.DataFrame(season_rows).pivot(index="season", columns="policy", values="n_obs").loc[SEASONS]
sup_season = pd.DataFrame(supseason_rows).pivot(index="season", columns="policy", values="supported_cells").loc[SEASONS]

print("\n" + "=" * 90)
print(f"POLICY COMPARISON (grid {GRID_RES} deg, {ncell} cells)")
print(f"supported = >= {MIN_OBS} obs AND >= {MIN_DRIFTERS} distinct drifters AND >= {MIN_DAYS} distinct calendar days")
print("=" * 90)
print(pol_summary.to_string(index=False))
print("\nSUPPORTED CELLS PER SEASON, BY POLICY")
print(sup_season.to_string())
print("\nOBSERVATIONS PER SEASON, BY POLICY")
print(by_season.to_string())
print("\nOBSERVATIONS PER YEAR, BY POLICY")
print(by_year.to_string())
print("\nDISTINCT DRIFTERS PER YEAR, BY POLICY")
print(by_year_dr.to_string())

p1 = support["P1 drogued only"]
print(f"\nP1 cells passing the count screen only: {int(p1['obs_only'].sum())}   "
      f"passing all three screens: {int(p1['supported'].sum())}")

# ---------------------------------------------------------------------------
# 6. Save
# ---------------------------------------------------------------------------
class_summary.to_csv("drogue_class_summary.csv", index=False)
td_table.to_csv("drogue_by_typedeath.csv")
eol_df.to_csv("drogue_endoflife_speed.csv")
pol_summary.to_csv("drogue_policy_summary.csv", index=False)
by_year.to_csv("drogue_policy_by_year.csv")
by_year_dr.to_csv("drogue_policy_by_year_drifters.csv")
by_season.to_csv("drogue_policy_by_season.csv")
sup_season.to_csv("drogue_policy_supported_by_season.csv")
np.savez(
    "drogue_cell_support.npz", nlat=nlat, nlon=nlon, grid_res=GRID_RES,
    lat_min=REGION["lat_min"], lon_min=REGION["lon_min"],
    **{f"{SHORT[n]}_{k}": (v.reshape(nlat, nlon) if v.ndim == 1 else v.reshape(4, nlat, nlon))
       for n, s in support.items() for k, v in s.items()},
)
print("\nSaved all CSVs and drogue_cell_support.npz. Please paste the printed output back to me.")