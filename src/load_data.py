"""Pemuatan data: Natural Earth (batas negara) dan World Bank WDI (populasi).

Semua path relatif terhadap akar proyek, sehingga skrip dapat dijalankan ulang.
Arsip unduhan diperlakukan sebagai data tidak tepercaya: diekstrak ke direktori
khusus dengan pengecekan path (anti zip-slip).
"""
from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
NE_DIR = RAW / "naturalearth_admin0"
WB_DIR = RAW / "worldbank"

NE_URLS = [  # 50m dahulu; 10m sebagai cadangan
    "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
    "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
]
WB_URL = (
    "https://api.worldbank.org/v2/country/{codes}/indicator/SP.POP.TOTL"
    "?format=json&per_page=1000&date=2015:2030"
)

AREA_URL = (
    "https://api.worldbank.org/v2/country/{codes}/indicator/AG.SRF.TOTL.K2"
    "?format=json&per_page=1000&date=2015:2030"
)

# 11 negara ASEAN (ISO3) -> nama Indonesia
TARGETS = {
    "BRN": "Brunei Darussalam", "KHM": "Kamboja", "IDN": "Indonesia",
    "LAO": "Laos", "MYS": "Malaysia", "MMR": "Myanmar", "PHL": "Filipina",
    "SGP": "Singapura", "THA": "Thailand", "TLS": "Timor Leste", "VNM": "Vietnam",
}


def _safe_extract(zip_path: Path, dest: Path) -> None:
    """Ekstrak zip dengan menolak path yang keluar dari direktori tujuan."""
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if dest != target and dest not in target.parents:
                raise ValueError(f"Path berbahaya di dalam arsip: {member.filename}")
        zf.extractall(dest)


def download_natural_earth() -> Path:
    """Unduh + ekstrak Natural Earth admin-0; kembalikan path .shp."""
    NE_DIR.mkdir(parents=True, exist_ok=True)
    for url in NE_URLS:
        name = url.rsplit("/", 1)[1]
        shp = NE_DIR / name.replace(".zip", ".shp")
        if shp.exists():
            return shp
        zpath = RAW / name
        if not zpath.exists():
            r = requests.get(url, timeout=120)
            if r.status_code != 200:
                print(f"[peringatan] {url} -> HTTP {r.status_code}, coba cadangan")
                continue
            zpath.write_bytes(r.content)
        _safe_extract(zpath, NE_DIR)
        return shp
    raise RuntimeError("Natural Earth tidak dapat diunduh dari semua URL.")


def download_population() -> Path:
    """Unduh SP.POP.TOTL World Bank untuk 11 negara; simpan JSON mentah + metadata."""
    WB_DIR.mkdir(parents=True, exist_ok=True)
    out = WB_DIR / "SP.POP.TOTL_asean_raw.json"
    if out.exists():
        return out
    url = WB_URL.format(codes=";".join(TARGETS))
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    out.write_bytes(r.content)
    meta = {
        "sumber": "World Bank, World Development Indicators",
        "indikator": "SP.POP.TOTL (Population, total)",
        "url_api": url,
        "halaman_indikator": "https://data.worldbank.org/indicator/SP.POP.TOTL",
        "tanggal_unduh": date.today().isoformat(),
        "lisensi": "CC BY 4.0",
    }
    (WB_DIR / "SOURCE.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")
    return out


def download_area() -> Path:
    """Unduh luas permukaan resmi World Bank (AG.SRF.TOTL.K2) + catat sumbernya."""
    WB_DIR.mkdir(parents=True, exist_ok=True)
    out = WB_DIR / "AG.SRF.TOTL.K2_asean_raw.json"
    if out.exists():
        return out
    url = AREA_URL.format(codes=";".join(TARGETS))
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    out.write_bytes(r.content)
    meta_path = WB_DIR / "SOURCE.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    meta["luas_permukaan"] = {
        "indikator": "AG.SRF.TOTL.K2 (Surface area, sq. km)",
        "url_api": url,
        "halaman_indikator": "https://data.worldbank.org/indicator/AG.SRF.TOTL.K2",
        "tanggal_unduh": date.today().isoformat(),
        "lisensi": "CC BY 4.0",
        "catatan": "Tahun 2025 belum tersedia; dipakai tahun terbaru yang tidak kosong (lihat kolom area_year).",
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")
    return out


def load_area() -> pd.DataFrame:
    """Luas resmi: tahun terbaru tidak-null per negara -> iso3, area_official_km2, area_year."""
    raw = json.loads(download_area().read_text("utf-8"))
    rows = pd.DataFrame(raw[1])
    rows["iso3"] = rows["countryiso3code"]
    rows["year"] = rows["date"].astype(int)
    valid = rows.dropna(subset=["value"]).sort_values("year")
    latest = valid.groupby("iso3").tail(1)[["iso3", "value", "year"]]
    latest = latest.rename(columns={"value": "area_official_km2", "year": "area_year"})
    out = pd.DataFrame({"iso3": list(TARGETS)}).merge(latest, on="iso3", how="left")
    out["area_official_km2"] = out["area_official_km2"].astype("float64")
    return out


def load_population() -> pd.DataFrame:
    """Parse JSON mentah: ambil tahun terbaru yang tidak-null per negara.

    Kembalikan kolom iso3, pop, pop_year, serta pop_latest_year_in_api.
    Negara tanpa nilai tetap hadir dengan NaN (ditangani eksplisit di hilir).
    """
    raw = json.loads(download_population().read_text("utf-8"))
    rows = pd.DataFrame(raw[1])
    rows["iso3"] = rows["countryiso3code"]
    rows["year"] = rows["date"].astype(int)
    valid = rows.dropna(subset=["value"]).sort_values("year")
    latest = valid.groupby("iso3").tail(1)[["iso3", "value", "year"]]
    latest = latest.rename(columns={"value": "pop", "year": "pop_year"})
    base = pd.DataFrame({"iso3": list(TARGETS)})
    out = base.merge(latest, on="iso3", how="left")
    out["pop"] = out["pop"].astype("float64")
    return out


def load_countries() -> gpd.GeoDataFrame:
    """Baca shapefile Natural Earth lengkap (belum difilter)."""
    return gpd.read_file(download_natural_earth())


def select_targets(world: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter 11 negara via ADM0_A3 (ISO_A3 bisa -99 untuk beberapa negara)."""
    sel = world[world["ADM0_A3"].isin(TARGETS)].copy()
    sel["iso3"] = sel["ADM0_A3"]
    missing = set(TARGETS) - set(sel["iso3"])
    if missing:
        raise ValueError(f"Negara hilang dari Natural Earth: {sorted(missing)}")
    return sel


def build_dataset() -> gpd.GeoDataFrame:
    """Gabungkan geometri dan populasi, simpan ke data/processed/."""
    sel = select_targets(load_countries())
    pop = load_population()
    area = load_area()
    gdf = sel[["iso3", "NAME", "SUBREGION", "geometry"]].merge(pop, on="iso3", how="left", validate="1:1")
    gdf = gdf.merge(area, on="iso3", how="left", validate="1:1")
    gdf["name_id"] = gdf["iso3"].map(TARGETS)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    return gdf


if __name__ == "__main__":
    g = build_dataset()
    print(g.drop(columns="geometry").to_string())
