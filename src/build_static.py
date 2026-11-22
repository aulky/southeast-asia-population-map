"""Bangun dataset olahan + ekspor PNG/SVG. Jalankan: python -I src/build_static.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import load_data as L
import project as P
import plot as PL

np.random.seed(L.SEED)


def main():
    gdf = L.build_dataset()
    world = L.load_countries()
    gp = P.add_metrics(gdf)
    year = int(gp["pop_year"].max())

    gp.to_crs(4326).to_file(L.PROCESSED / "asean_population.geojson", driver="GeoJSON")
    gp.drop(columns="geometry").to_csv(L.PROCESSED / "asean_metrics.csv", index=False)

    fig = PL.make_figure(gp, world.clip((85, -16, 145, 32)).to_crs(gp.crs), year)
    print("Overlap label:", PL.label_overlaps(fig))
    out = L.ROOT / "outputs"
    fig.savefig(out / "asean_population_choropleth.png", dpi=300)
    fig.savefig(out / "asean_population_choropleth.svg")
    print("OK")


if __name__ == "__main__":
    main()
