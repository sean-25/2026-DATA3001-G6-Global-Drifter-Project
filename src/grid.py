"""Shared grid and map styling for notebooks 02-08. Region and resolution come from config.py.

Import from a notebook with:
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path.cwd() if Path("config.py").exists() else Path.cwd() / "src"))
    from grid import ...
"""
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from config import LON_MIN, LON_MAX, LAT_MIN, LAT_MAX, RES

proj = ccrs.PlateCarree()   # map projection used by every map

# --- Grid definition (built from integer cell counts, so any box and resolution work) ---
nx = int(round((LON_MAX - LON_MIN) / RES))             # number of cells each way
ny = int(round((LAT_MAX - LAT_MIN) / RES))
assert np.isclose(nx * RES, LON_MAX - LON_MIN) and np.isclose(ny * RES, LAT_MAX - LAT_MIN), \
    "region size must be a whole number of cells"
lon_edges = LON_MIN + RES * np.arange(nx + 1)          # cell boundaries
lat_edges = LAT_MIN + RES * np.arange(ny + 1)
lon_c = (lon_edges[:-1] + lon_edges[1:]) / 2           # cell centres
lat_c = (lat_edges[:-1] + lat_edges[1:]) / 2


def cell_index(d):
    """Cell (iy, ix) of each row. Clip keeps points on the far edge in the last cell."""
    ix = np.clip(((d["lon"].values - LON_MIN) // RES).astype(int), 0, nx - 1)
    iy = np.clip(((d["lat"].values - LAT_MIN) // RES).astype(int), 0, ny - 1)
    return iy, ix


def style_map(ax, title=None):
    """Shared map styling: grey land, coastline, study extent, labelled gridlines."""
    ax.add_feature(cfeature.LAND, facecolor="lightgrey", zorder=2)
    ax.coastlines(resolution="50m", linewidth=0.6, zorder=3)
    ax.set_extent([LON_MIN, LON_MAX, LAT_MIN, LAT_MAX], crs=proj)
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)
    gl.top_labels = gl.right_labels = False
    if title:
        ax.set_title(title)
