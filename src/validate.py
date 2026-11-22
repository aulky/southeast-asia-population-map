"""Validasi dataset akhir. Dipakai oleh notebook dan dashboard.

Jalankan langsung: python -I src/validate.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_data as L
import project as P


def raw_value(iso3: str) -> tuple[int, float]:
    """Hitung ulang MANDIRI dari JSON mentah (tanpa memakai load_population)."""
    raw = json.loads((L.WB_DIR / "SP.POP.TOTL_asean_raw.json").read_text("utf-8"))[1]
    best = max((r for r in raw if r["countryiso3code"] == iso3 and r["value"] is not None),
               key=lambda r: int(r["date"]))
    return int(best["date"]), float(best["value"])


def run_checks(gp) -> list[dict]:
    """gp: GeoDataFrame terproyeksi dengan kolom pop, pop_year, area_km2, density."""
    checks = []

    def add(name, ok, detail="", warn=False):
        """warn=True: bila tidak ok, ditandai 'peringatan' (bukan kegagalan pipeline)."""
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "warn": bool(warn) and not ok})

    add("Jumlah negara = 11", len(gp) == 11, f"{len(gp)} negara")
    add("Seluruh ISO3 target hadir", set(gp["iso3"]) == set(L.TARGETS))
    add("Join populasi 11/11 (tanpa NaN)", gp["pop"].notna().all(),
        f"hilang: {list(gp.loc[gp['pop'].isna(), 'iso3'])}")
    add("Geometri valid", gp.geometry.is_valid.all())
    add("Luas resmi tersedia 11/11", gp["area_km2"].notna().all(),
        f"hilang: {list(gp.loc[gp['area_km2'].isna(), 'iso3'])}; tahun: {sorted(int(y) for y in gp['area_year'].dropna().unique())}")
    add("Luas resmi > 0 untuk semua negara", (gp["area_km2"] > 0).all())
    add("Kepadatan = populasi / luas resmi", np.allclose(gp["density"], gp["pop"] / gp["area_km2"]))
    big = gp.loc[gp["area_diff_pct"].abs() > 10, ["iso3", "area_diff_pct"]]
    ds = gp.set_index("iso3")["area_diff_pct"]
    add("Selisih luas geometri vs resmi <= 10% (pelaporan)", big.empty,
        "selisih (%): " + ", ".join(f"{k} {v:+.1f}" for k, v in ds.sort_values().items())
        + ("" if big.empty else " | DITANDAI >10%: " + ", ".join(big["iso3"])), warn=True)
    diff = P.distortion_report(gp.to_crs(4326))["max_rel_diff"]
    add("Luas geometri Albers vs LAEA konsisten (selisih < 1%)", diff < 0.01, f"selisih maks {diff:.3%}")
    for iso in ["IDN", "SGP", "TLS"]:  # tiga negara dihitung ulang manual
        yr, val = raw_value(iso)
        r = gp.set_index("iso3").loc[iso]
        add(f"Cek manual {iso}: nilai & tahun = sumber mentah",
            r["pop"] == val and int(r["pop_year"]) == yr, f"mentah {val:,.0f} ({yr}); dataset {r['pop']:,.0f} ({int(r['pop_year'])})")
    add("Tahun data seragam", gp["pop_year"].nunique() == 1, f"tahun: {sorted(int(y) for y in gp['pop_year'].dropna().unique())}")
    return checks


if __name__ == "__main__":
    gp = P.add_metrics(L.build_dataset())
    res = run_checks(gp)
    for c in res:
        tag = "PERINGATAN" if c["warn"] else ("LOLOS" if c["ok"] else "GAGAL")
        print(f"[{tag}] {c['name']} {c['detail']}")
    raise SystemExit(0 if all(c["ok"] or c["warn"] for c in res) else 1)
