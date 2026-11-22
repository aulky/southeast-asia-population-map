"""Bangun outputs/dashboard.html (mandiri: plotly.js ditanam inline, tanpa server).

Jalankan: python -I src/build_dashboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib.colors as mc
import numpy as np
from plotly.offline import get_plotlyjs

import load_data as L
import plot as PL
import project as P
import validate as V

TEMPLATE = (Path(__file__).parent / "dashboard_template.html").read_text("utf-8")


def coords(geom):
    """Ubah (Multi)Polygon menjadi list x,y dengan None sebagai pemisah ring."""
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    xs, ys = [], []
    for p in polys:
        x, y = p.exterior.xy
        xs += [round(v / 1000, 1) for v in x] + [None]   # km
        ys += [round(v / 1000, 1) for v in y] + [None]
    return xs[:-1], ys[:-1]


def main():
    gdf = L.build_dataset()
    gp = P.add_metrics(gdf)
    checks = V.run_checks(gp)
    simp = gp.copy()
    simp["geometry"] = gp.geometry.simplify(2000)  # 2 km, ringan untuk HTML

    rows, colors, legends = [], {}, {}
    for kind, cmap_name in (("pop", "YlOrRd"), ("density", "YlGnBu")):
        edges, cmap_d, norm, title = PL._classify(gp, kind, cmap_name)
        col = "pop" if kind == "pop" else "density"
        colors[kind] = {r.iso3: mc.to_hex(cmap_d(norm(r[col]))) for _, r in gp.iterrows()}
        legends[kind] = {
            "title": title,
            "items": [{"color": mc.to_hex(cmap_d(i)), "label": PL._leg_label(edges[i], edges[i + 1], kind)}
                      for i in range(len(edges) - 1)],
        }
    for (_, r), (_, s) in zip(gp.iterrows(), simp.iterrows()):
        x, y = coords(s.geometry)
        rows.append({"iso3": r.iso3, "name": r.name_id, "pop": r["pop"], "year": int(r.pop_year),
                     "area": r.area_km2, "area_year": int(r.area_year), "area_geom": r.area_geom_km2,
                     "area_diff": r.area_diff_pct, "density": r.density, "x": x, "y": y})
    missing = [r["iso3"] for r in rows if r["pop"] != r["pop"]]
    payload = {
        "rows": rows, "colors": colors, "legends": legends, "checks": checks,
        "summary": {"n": len(rows), "total_pop": float(gp["pop"].sum()), "missing": missing,
                    "year": int(gp["pop_year"].max())},
    }
    html = (TEMPLATE.replace("/*PLOTLYJS*/", get_plotlyjs())
            .replace("/*DATA*/null", json.dumps(payload, ensure_ascii=False, allow_nan=False)))
    out = L.ROOT / "outputs" / "dashboard.html"
    out.write_text(html, "utf-8")
    print(f"OK {out} ({out.stat().st_size / 1e6:.1f} MB); gagal: {[c['name'] for c in checks if not c['ok'] and not c['warn']]}; peringatan: {[c['name'] for c in checks if c['warn']]}")


if __name__ == "__main__":
    main()
