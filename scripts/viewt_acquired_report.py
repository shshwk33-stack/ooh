"""Private, reproducible summaries of acquired 2024 View-T files; no performance claim."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager

from transit_ooh.viewt_population import (
    aggregation_check,
    combine_inflow_batches,
    load_population,
)
from transit_ooh.viewt_routes import load_routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", default="data/processed/viewt_population")
    parser.add_argument("--routes", default="data/processed/viewt_vehicle_paths")
    parser.add_argument("--output", default="data/processed/viewt_acquired_report")
    args = parser.parse_args()
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.exists():
        font_manager.fontManager.addfont(font)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 180,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
            "axes.unicode_minus": False,
        }
    )
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    datasets = load_population(args.population)
    annual = [
        d
        for d in datasets
        if d[2]["kind"] == "inflow" and d[2]["requested_days"] == 262
    ]
    district = next(d for d in annual if d[2]["destination_unit"] == "sigungu")
    dong_sources = [d for d in annual if d[2]["destination_unit"] == "dong"]
    dongs = combine_inflow_batches(dong_sources)
    reference = {
        k: v for k, v in district[2]["request"].items() if k not in ["zone", "zoneType"]
    }
    if any(
        {k: v for k, v in d[2]["request"].items() if k not in ["zone", "zoneType"]}
        != reference
        for d in dong_sources
    ):
        raise ValueError(
            "Aggregation check requires identical non-spatial query conditions"
        )
    check = aggregation_check(district[1], dongs)
    if check["destination_dong_count"] != 16 or check["max_origin_difference"] != 0:
        raise ValueError("Mapo destination aggregation did not reconcile")
    table = dongs.groupby(["destination_id", "destination_name"], as_index=False).agg(
        period_trips=("period_trips", "sum"),
        latitude=("destination_latitude", "first"),
        longitude=("destination_longitude", "first"),
    )
    external = dongs[~dongs.within_mapo].groupby("destination_id").period_trips.sum()
    table["external_period_trips"] = table.destination_id.map(external)
    if table.external_period_trips.isna().any():
        raise ValueError("Missing external-origin rows")
    table["internal_period_trips"] = table.period_trips - table.external_period_trips
    table["daily_mean"] = table.period_trips / 262
    table["name"] = table.destination_name.str.replace(
        "서울특별시 마포구 ", "", regex=False
    )
    table = table.sort_values("daily_mean", ascending=False)
    table.to_csv(
        out / "dong_inflow_2024_weekdays.csv", index=False, encoding="utf-8-sig"
    )
    od = next(
        d for d in datasets if d[2]["kind"] == "od" and d[2]["requested_days"] == 262
    )[1]
    od.to_csv(
        out / "mapo_directed_od_2024_weekdays.csv", index=False, encoding="utf-8-sig"
    )
    _route_table, geo, route_meta = load_routes(args.routes)
    pd.DataFrame(route_meta["summaries"]).to_csv(
        out / "route_geometry_checks.csv", index=False, encoding="utf-8-sig"
    )
    foot = "출처: KTDB View-T | 2024년 월~금 262일 요청 · 집계/추정 통행 | 광고 노출·고유 인원·모델 정확도 아님"

    def save(fig, name):
        fig.text(0.02, 0.015, foot, fontsize=8, color="#5b6470")
        fig.tight_layout(rect=[0, 0.055, 1, 1])
        for ext in ["png", "svg"]:
            fig.savefig(out / (name + "." + ext), facecolor="white")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 7))
    t = table.iloc[::-1]
    ax.barh(
        t.name,
        t.external_period_trips / 262 / 1000,
        color="#14859c",
        label="마포구 외부에서 출발",
    )
    ax.barh(
        t.name,
        t.internal_period_trips / 262 / 1000,
        left=t.external_period_trips / 262 / 1000,
        color="#f0a33a",
        label="마포구 내부에서 출발",
    )
    ax.set(
        title="마포구 16개 동별 유입 통행 비교",
        xlabel="요청일수로 나눈 평균 통행량 (천 통행/일)",
    )
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.15)
    ax.set_axisbelow(True)
    save(fig, "dong_inflow")
    order = sorted(table.destination_id)
    matrix = (
        od.pivot(
            index="origin_id", columns="destination_id", values="period_trips"
        ).reindex(index=order, columns=order)
        / 262
    )
    names = table.set_index("destination_id").name
    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.colormaps["YlGnBu"].copy()
    cmap.set_bad("#eeeeee")
    im = ax.imshow(np.ma.masked_invalid(matrix.to_numpy()), cmap=cmap)
    ax.set_xticks(range(16), [names[k] for k in order], rotation=55, ha="right")
    ax.set_yticks(range(16), [names[k] for k in order])
    ax.set(
        title="마포구 내 동 사이 O/D · 회색 대각선은 미제공",
        xlabel="도착 동",
        ylabel="출발 동",
    )
    fig.colorbar(im, ax=ax, label="평균 통행/일", shrink=0.75)
    save(fig, "directed_od")
    fig, ax = plt.subplots(figsize=(7, 6))
    a = district[1].set_index("origin_id").period_trips.sort_index() / 262
    b = dongs.groupby("origin_id").period_trips.sum().reindex(a.index) / 262
    ax.scatter(a, b, color="#14859c", s=20, alpha=0.6)
    limit = max(a.max(), b.max())
    ax.plot([0, limit], [0, limit], color="#e99d35", linestyle="--")
    ax.set(
        title="구 전체 조회와 16개 동 합계의 일관성",
        xlabel="구 전체 조회 (통행/요청일)",
        ylabel="16개 동 합계 (통행/요청일)",
    )
    ax.text(
        0.05,
        0.92,
        "252개 출발지역 · 기간 합계 차이 0\n동일 출처 집계 검사이며 독립 정확도 검증 아님",
        transform=ax.transAxes,
        fontsize=9,
    )
    save(fig, "aggregation_consistency")
    fig, ax = plt.subplots(figsize=(9, 7))
    colors = {
        "11140740_11140680": "#14859c",
        "11140680_11140770": "#e68d35",
        "11140770_11140740": "#8058a4",
    }
    labels = {
        "11140740_11140680": "상암 → 합정",
        "11140680_11140770": "합정 → 공덕",
        "11140770_11140740": "공덕 → 상암",
    }
    seen = set()
    for feature in geo["features"]:
        props = feature["properties"]
        if props["rank"] != 1:
            continue
        g = feature["geometry"]
        lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        for line in lines:
            xy = np.array(line)
            ax.plot(
                xy[:, 0],
                xy[:, 1],
                color=colors[props["leg"]],
                linewidth=2,
                label=labels[props["leg"]] if props["leg"] not in seen else None,
            )
            seen.add(props["leg"])
    ax.legend()
    ax.set_aspect(1 / np.cos(np.radians(37.55)))
    ax.set(
        title="가상 순회 검토용 · 구간별 이용비율 1위 대표경로",
        xlabel="경도",
        ylabel="위도",
    )
    ax.text(
        0.01,
        0.01,
        "각 링크 형상만 표시 · 구간 사이 연결과 배송 접근 미검증\n실제 밀크런 GPS 아님",
        transform=ax.transAxes,
        fontsize=9,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )
    save(fig, "representative_paths")
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "authentication": "official SUCCESS verified separately",
        "population_dataset_count": len(datasets),
        "dong_od_rows": len(dongs),
        "directed_od_rows": len(od),
        "aggregation_check": check,
        "requested_weekdays": 262,
        "external_period_trips": float(table.external_period_trips.sum()),
        "internal_period_trips": float(table.internal_period_trips.sum()),
        "route_count": route_meta["route_count"],
        "route_unique_links": route_meta["unique_links"],
        "route_geometry_max_gap_m": max(
            s["max_nearest_endpoint_gap_m"] for s in route_meta["summaries"]
        ),
        "routes_with_gap_over_10m": sum(
            s["gaps_over_10m"] > 0 for s in route_meta["summaries"]
        ),
        "source_manifests_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(args.population) / "manifest.json",
                Path(args.routes) / "metadata.json",
            ]
        },
        "independent_validation": "not available; these checks establish schema and same-source consistency only",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "datasets": len(datasets),
                "dong_od_rows": len(dongs),
                "plots": 4,
                "output": str(out),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
