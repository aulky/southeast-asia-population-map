"""Proyeksi dan metrik turunan (luas, kepadatan)."""
from __future__ import annotations

import geopandas as gpd
from pyproj import CRS

# Albers Equal-Area Conic: parameter sesuai spesifikasi tugas.
ALBERS = CRS.from_proj4(
    "+proj=aea +lat_1=-5 +lat_2=22 +lat_0=5 +lon_0=115 +x_0=0 +y_0=0 "
    "+datum=WGS84 +units=m +no_defs"
)
# Lambert Azimuthal Equal-Area berpusat di (115E, 5N), untuk perbandingan.
LAEA = CRS.from_proj4(
    "+proj=laea +lat_0=5 +lon_0=115 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
)


def add_metrics(gdf: gpd.GeoDataFrame, crs: CRS = ALBERS) -> gpd.GeoDataFrame:
    """Tambah kolom luas dan kepadatan.

    - area_km2          : luas RESMI World Bank (AG.SRF.TOTL.K2), dasar kepadatan.
    - area_geom_km2     : luas dari geometri 1:50m di CRS equal-area (hanya pembanding).
    - area_diff_pct     : (geom - resmi) / resmi * 100.
    - density           : pop / area_km2 (jiwa/km²).
    """
    out = gdf.to_crs(crs).copy()
    out["area_geom_km2"] = out.geometry.area / 1e6
    out["area_km2"] = out["area_official_km2"]
    out["area_diff_pct"] = (out["area_geom_km2"] - out["area_km2"]) / out["area_km2"] * 100
    out["density"] = out["pop"] / out["area_km2"]
    return out


def distortion_report(gdf_wgs84: gpd.GeoDataFrame) -> dict:
    """Bandingkan luas hasil Albers vs LAEA (keduanya equal-area -> harus ~sama)."""
    a = gdf_wgs84.to_crs(ALBERS).area / 1e6
    b = gdf_wgs84.to_crs(LAEA).area / 1e6
    return {"max_rel_diff": float(((a - b).abs() / a).max())}
