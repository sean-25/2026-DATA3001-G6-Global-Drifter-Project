"""Shared 1° Kuroshio grid and map styling for the sampling and aggregation notebooks.

Import from a notebook in this folder with:
    import sys; sys.path.insert(0, "../src")
    from grid import ...
"""
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature

proj = ccrs.PlateCarree()   # map projection used by every map

# --- Grid definition (region bounds kept as variables so any box works) ---
LON_MIN, LON_MAX = 115, 145
LAT_MIN, LAT_MAX = 15, 40
RES = 1.0                                              # cell size in degrees

lon_edges = np.arange(LON_MIN, LON_MAX + RES, RES)     # cell boundaries
lat_edges = np.arange(LAT_MIN, LAT_MAX + RES, RES)
nx, ny = len(lon_edges) - 1, len(lat_edges) - 1        # number of cells each way
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
