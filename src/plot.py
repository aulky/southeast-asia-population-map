"""Pembuatan peta choropleth dua panel (total populasi dan kepadatan)."""
from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm
from matplotlib.patches import Rectangle
from matplotlib.cm import ScalarMappable
import mapclassify

SOURCE_TEXT = (
    "Sumber: populasi World Bank WDI (SP.POP.TOTL, {year}); luas permukaan World Bank (AG.SRF.TOTL.K2, 2024, dasar kepadatan); "
    "batas negara Natural Earth 1:50m.\n"
    "Proyeksi: Albers Equal-Area Conic (parallels -5° & 22°, CM 115°E)."
)

# Tepi kelas total populasi: skala log (kira-kira kelipatan 2,5-5).
TOTAL_EDGES = np.array([0.1e6, 1e6, 5e6, 15e6, 40e6, 100e6, 300e6])

# Posisi label: iso3 -> (lon_label, lat_label, lon_anchor, lat_anchor); anchor None = tanpa garis.
LABELS = {
    "MMR": (96.3, 21.0, None, None),
    "THA": (100.9, 16.0, None, None),
    "LAO": (103.9, 19.6, None, None),
    "VNM": (111.2, 15.5, 108.0, 15.0),
    "KHM": (103.0, 9.2, 104.6, 12.6),
    "MYS": (106.4, 5.4, 102.3, 4.3),
    "IDN": (113.6, -1.9, None, None),
    "PHL": (128.4, 12.0, 122.5, 12.5),
    "TLS": (127.8, -9.8, 125.9, -8.8),
}
CALLOUT = {  # inset/callout: iso3 -> (lon_label, lat_label, lon_anchor, lat_anchor)
    "SGP": (106.6, -3.2, 103.82, 1.35),
    "BRN": (118.8, 6.8, 114.65, 4.6),
}


def fmt_num(v: float, kind: str) -> str:
    if kind == "pop":
        if v >= 1e6:
            return f"{v / 1e6:,.1f} jt".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{v / 1e3:,.0f} rb".replace(",", ".")
    return f"{v:,.0f}/km²".replace(",", ".")


def _classify(gdf, kind: str, cmap_name: str):
    cmap = matplotlib.colormaps[cmap_name]
    if kind == "pop":
        edges = TOTAL_EDGES
        title_leg = "Total populasi (skala log, jiwa)"
    else:
        q = mapclassify.Quantiles(gdf["density"].values, k=5)
        edges = np.concatenate([[0], q.bins])
        edges[-1] = edges[-1] * 1.0001
        title_leg = "Kepadatan (jiwa/km², kuantil)"
    n = len(edges) - 1
    colors = cmap(np.linspace(0.12, 0.95, n))
    cmap_d = matplotlib.colors.ListedColormap(colors)
    norm = BoundaryNorm(edges, n)
    return edges, cmap_d, norm, title_leg


def _leg_label(lo, hi, kind):
    if kind == "pop":
        f = lambda v: (f"{v / 1e6:g} jt")
    else:
        f = lambda v: f"{v:,.0f}".replace(",", ".")
    return f"{f(lo)} – {f(hi)}"


def draw_panel(ax, gdf, world, kind, cmap_name, title, bounds, year):
    col = "pop" if kind == "pop" else "density"
    edges, cmap_d, norm, leg_title = _classify(gdf, kind, cmap_name)
    xmin, ymin, xmax, ymax = bounds
    ax.set_facecolor("#dfe9f1")
    world.plot(ax=ax, color="#eceae4", edgecolor="#c7c3b8", linewidth=0.3, zorder=1)
    gdf.plot(ax=ax, column=col, cmap=cmap_d, norm=norm, edgecolor="#333", linewidth=0.4, zorder=2)
    ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_xlabel(''); ax.set_ylabel('')
    for s in ax.spines.values():
        s.set_color("#888")
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left")

    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", gdf.crs, always_xy=True)
    rows = gdf.set_index("iso3")

    def txt(iso, lonlat, **kw):
        x, y = tr.transform(*lonlat[:2])
        r = rows.loc[iso]
        label = f"{r['name_id']}\n{fmt_num(r[col], kind)}"
        kw.setdefault("ha", "center"); kw.setdefault("va", "center")
        t = ax.text(x, y, label, fontsize=6.6, zorder=6, linespacing=1.15,
                    bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.78), **kw)
        t.set_gid(f"label-{iso}")
        return t

    for iso, (lx, ly, ax_, ay_) in LABELS.items():
        txt(iso, (lx, ly))
        if ax_ is not None:
            x0, y0 = tr.transform(lx, ly); x1, y1 = tr.transform(ax_, ay_)
            ax.plot([x0, x1], [y0, y1], color="#444", lw=0.6, zorder=5)
            ax.plot([x1], [y1], "o", color="#444", ms=1.8, zorder=5)
    for iso, (lx, ly, ax_, ay_) in CALLOUT.items():
        txt(iso, (lx, ly), bbox_extra=None) if False else None
        x0, y0 = tr.transform(lx, ly); x1, y1 = tr.transform(ax_, ay_)
        r = rows.loc[iso]
        label = f"{r['name_id']}\n{fmt_num(r[col], kind)}"
        t = ax.annotate(
            label, xy=(x1, y1), xytext=(x0, y0), fontsize=6.6, ha="center", va="center", zorder=7,
            arrowprops=dict(arrowstyle="-|>", color="#222", lw=0.8, shrinkB=1),
            bbox=dict(boxstyle="round,pad=0.25", fc="#fffbe6", ec="#222", lw=0.6))
        t.set_gid(f"label-{iso}")
        # lingkaran penanda agar negara kecil terlihat
        ax.plot([x1], [y1], "o", mfc="none", mec="#222", ms=7, mew=0.9, zorder=7)

    # legenda
    handles = []
    labels = []
    for i in range(len(edges) - 1):
        handles.append(Rectangle((0, 0), 1, 1, fc=cmap_d(i), ec="#555", lw=0.4))
        labels.append(_leg_label(edges[i], edges[i + 1], kind))
    leg = ax.legend(handles, labels, title=leg_title, loc="lower left", fontsize=7,
                    title_fontsize=7.5, frameon=True, framealpha=0.92, borderpad=0.7)
    leg.set_zorder(10)

    # skala 500 km
    bar = 500_000
    x0 = xmax - bar - 0.04 * (xmax - xmin); y0 = ymin + 0.045 * (ymax - ymin)
    ax.plot([x0, x0 + bar], [y0, y0], color="k", lw=2.2, solid_capstyle="butt", zorder=9)
    ax.text(x0 + bar / 2, y0 + 0.012 * (ymax - ymin), "500 km", ha="center", va="bottom", fontsize=7, zorder=9)
    # panah utara (utara-grid pada meridian pusat 115°E)
    nx = xmax - 0.05 * (xmax - xmin); ny = ymax - 0.16 * (ymax - ymin)
    ax.annotate("", xy=(nx, ny + 0.09 * (ymax - ymin)), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="-|>", color="k", lw=1.4), zorder=9)
    ax.text(nx, ny + 0.10 * (ymax - ymin), "U", ha="center", va="bottom", fontsize=9, fontweight="bold", zorder=9)
    return edges


def make_figure(gdf, world, year: int, cmap_total="YlOrRd", cmap_dens="YlGnBu"):
    """Buat figure dua panel. gdf harus sudah diproyeksikan dan punya kolom metrik."""
    # Batas tampilan dari bounding box 11 negara + margin
    xmin, ymin, xmax, ymax = gdf.total_bounds
    mx, my = 0.04 * (xmax - xmin), 0.06 * (ymax - ymin)
    bounds = (xmin - mx, ymin - my - 0.04 * (ymax - ymin), xmax + mx, ymax + my)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.4), dpi=100)
    draw_panel(axes[0], gdf, world, "pop", cmap_total, "(a) Total populasi", bounds, year)
    draw_panel(axes[1], gdf, world, "density", cmap_dens, "(b) Kepadatan penduduk", bounds, year)
    fig.suptitle("Populasi Negara-negara ASEAN (Asia Tenggara)", fontsize=16, fontweight="bold", x=0.01, ha="left")
    fig.text(0.01, 0.015, SOURCE_TEXT.format(year=year), fontsize=7.5, color="#333", ha="left")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.085, wspace=0.03)
    return fig


def label_overlaps(fig) -> list[tuple[str, str]]:
    """Kembalikan pasangan label (gid 'label-XXX') yang bounding box-nya bertumpuk."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    out = []
    for ax in fig.axes:
        items = [(t.get_gid(), t.get_window_extent(r)) for t in ax.texts if (t.get_gid() or "").startswith("label-")]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if items[i][1].overlaps(items[j][1]):
                    out.append((items[i][0], items[j][0]))
    return out
