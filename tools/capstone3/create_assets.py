"""Render presentation figures from received files; no fabricated research values."""
from pathlib import Path
import json
import zipfile

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables/capstone3/assets"
OUT.mkdir(parents=True, exist_ok=True)
ATTACHMENTS = Path("/workspace/attachments")
font_manager.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams.update({"font.family": "Noto Sans CJK JP", "axes.unicode_minus": False})

def source(name):
    matches = list(ATTACHMENTS.glob(f"*/{name}"))
    assert len(matches) == 1, (name, matches)
    return matches[0]

def read_shapefile(name, encoding):
    p = source(name)
    with zipfile.ZipFile(p) as z:
        shp = next(n for n in z.namelist() if n.endswith(".shp"))
    return gpd.read_file(f"zip://{p}!{shp}", encoding=encoding)

roads = read_shapefile("seoul_link_lev5.5_2024.zip", "cp949")
boundary = read_shapefile("mapo_boundary_2023.zip", "utf-8")
mapo = roads[roads.sigungu_id.astype(str).str.replace(r"\.0$", "", regex=True).eq("11140")].copy()
assert len(mapo) == 408 and len(boundary) == 16
assert roads.crs == boundary.crs

fig, ax = plt.subplots(figsize=(11, 6.5), dpi=240)
fig.patch.set_facecolor("#F0F5F7"); ax.set_facecolor("#F0F5F7")
colors = ["#E0ECEF", "#D7E8EA", "#E7F0F0", "#DCE9F0"]
boundary.plot(ax=ax, color=[colors[i % len(colors)] for i in range(len(boundary))], edgecolor="#A4B9C4", linewidth=.7)
mapo.plot(ax=ax, color="#178EAA", linewidth=1.15, alpha=.92)
for _, row in boundary.iterrows():
    if row["name"] in {"상암동", "성산2동", "연남동", "서교동", "합정동", "공덕동", "용강동"}:
        pt = row.geometry.representative_point()
        ax.text(pt.x, pt.y, row["name"], ha="center", va="center", fontsize=10, color="#193A50", bbox={"boxstyle":"round,pad=.22", "fc":"#FFFFFF", "ec":"none", "alpha":.90})
xmin,ymin,xmax,ymax = boundary.total_bounds
ax.set_xlim(xmin-250,xmax+250);ax.set_ylim(ymin-300,ymax+350)
ax.plot([xmin+300,xmin+1300],[ymin+70,ymin+70],color="#193A50",lw=2.5)
ax.text(xmin+800,ymin+150,"1 km",ha="center",fontsize=9,color="#193A50")
ax.annotate("N",xy=(xmax-350,ymax-650),xytext=(xmax-350,ymax-1000),ha="center",color="#193A50",fontsize=10,arrowprops={"arrowstyle":"-|>","color":"#193A50"})
ax.set_axis_off();fig.subplots_adjust(0,0,1,1)
fig.savefig(OUT/"mapo_reference_map.png",facecolor=fig.get_facecolor(),bbox_inches="tight",pad_inches=.02)
plt.close(fig)

fig, ax=plt.subplots(figsize=(8,8),dpi=230)
fig.patch.set_alpha(0);ax.set_facecolor("none")
mapo.plot(ax=ax,color="#41D1C8",linewidth=1.75,alpha=.92)
ax.set_axis_off();ax.margins(.025);fig.subplots_adjust(0,0,1,1)
fig.savefig(OUT/"mapo_cover_network.png",transparent=True,bbox_inches="tight",pad_inches=.03)
plt.close(fig)

fig,ax=plt.subplots(figsize=(4,3),dpi=200)
roads.plot(ax=ax,color="#B2C4D0",linewidth=.35)
mapo.plot(ax=ax,color="#087F91",linewidth=.9)
ax.set_axis_off();fig.subplots_adjust(0,0,1,1)
fig.savefig(OUT/"seoul_locator.png",transparent=True,bbox_inches="tight",pad_inches=0)
plt.close(fig)

(OUT/"map_evidence.json").write_text(json.dumps({
    "source":"Korea Transport Institute / KTDB View-T, user-provided downloads",
    "road_network_year":2024,"boundary_year":2023,
    "seoul_links":len(roads),"mapo_provider_assigned_links":len(mapo),"mapo_dongs":len(boundary),
    "district_filter":"provider sigungu_id=11140",
    "map_semantics":"Reference overlay only. Cross-year boundary equivalence not verified; no scoring or GPS route inferred."
},ensure_ascii=False,indent=2),encoding="utf-8")
print("Rendered three maps using verified provider-assigned 408 links and 16 reference polygons.")
