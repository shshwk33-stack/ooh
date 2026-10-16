"""Provider route alternatives supporting, but not validating, a hypothetical cycle."""

import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from transit_ooh.route_context import summarize_route_context
from transit_ooh.viewt_roads import load_context
from transit_ooh.viewt_routes import load_routes

LOCAL = Path(__file__).resolve().parents[1] / "data/processed/viewt_vehicle_paths"
LEGS = [
    ("11140740_11140680", "상암 → 합정"),
    ("11140680_11140770", "합정 → 공덕"),
    ("11140770_11140740", "공덕 → 상암"),
]


def render():
    st.subheader("View-T 공식 차량경로 · 가상 순회 참고")
    st.info(
        "기관이 제공한 대표경로와 이용비율입니다. 특정 배송차량 GPS나 실측 밀크런 운행기록이 아닙니다."
    )
    if not (LOCAL / "metadata.json").is_file():
        st.warning("검증한 차량경로 파일이 아직 없습니다.")
        return
    try:
        frame, geo, meta = load_routes(LOCAL)
    except (ValueError, KeyError, OSError) as exc:
        st.error(f"경로 검사 실패: {exc}")
        return
    st.caption(
        "2024년 · 평일 · 종일 · 전체 차량. 상암·합정·공덕은 예시 거점이며 실제 배송 계약지나 확정 정차 위치가 아닙니다."
    )
    selected = {}
    columns = st.columns(3)
    for column, (leg, title) in zip(columns, LEGS, strict=True):
        selected[leg] = column.selectbox(
            title,
            sorted(frame.loc[frame.leg.eq(leg), "rank"].unique()),
            key="official_route_" + leg,
            format_func=lambda x: f"대표경로 {x}위",
        )
    rows = frame[frame.apply(lambda r: r["rank"] == selected[r.leg], axis=1)].copy()
    colors = {
        leg: color
        for (leg, _), color in zip(
            LEGS,
            [[17, 130, 163, 230], [235, 110, 45, 230], [118, 80, 170, 230]],
            strict=True,
        )
    }
    features = [
        f
        for f in geo["features"]
        if f["properties"]["rank"] == selected[f["properties"]["leg"]]
    ]
    for f in features:
        props = f["properties"]
        props["color"] = colors[props["leg"]]
        props["leg_name"] = dict(LEGS)[props["leg"]]
    st.pydeck_chart(
        pdk.Deck(
            layers=[
                pdk.Layer(
                    "GeoJsonLayer",
                    {"type": "FeatureCollection", "features": features},
                    get_line_color="properties.color",
                    line_width_min_pixels=4,
                    pickable=True,
                )
            ],
            initial_view_state=pdk.ViewState(
                latitude=37.555, longitude=126.913, zoom=12
            ),
            map_style=None,
            tooltip={
                "text": "{leg_name}\n{road_name}\n이용비율: {share_percent}%\n구간 내 순서: {sequence}"
            },
        )
    )
    summary = pd.DataFrame(meta["summaries"])
    summary = summary[summary.apply(lambda r: r["rank"] == selected[r.leg], axis=1)]
    st.dataframe(summary, hide_index=True)
    st.warning(
        "각 도로를 원래 형상대로 표시하며 도로 사이 빈틈을 임의로 연결하지 않습니다. 구간 사이 연결·방향·회전제한·배송 접근 가능성은 미검증입니다. 이용비율을 차량 대수나 광고 노출량으로 바꾸지 않습니다."
    )
    st.caption(
        "max_nearest_endpoint_gap_m은 연속 순서 링크 사이 가장 가까운 끝점 거리입니다. 10m 기준은 형상 점검용이며 주행 가능성을 보증하지 않습니다."
    )
    if summary.gaps_over_10m.gt(0).any():
        st.warning(
            "선택한 대표경로에 10m를 넘는 링크 끝점 간격이 있습니다. 경로를 연속 GPS처럼 사용하지 마세요."
        )
    st.dataframe(rows, hide_index=True)
    road_dir = LOCAL.parent / "viewt_official_roads"
    if (road_dir / "metadata.json").exists():
        st.subheader("동일 도로망의 교통량·속도 연결")
        try:
            roads, _ = load_context(road_dir)
            context = summarize_route_context(frame, geo, meta, roads)
            st.dataframe(context, hide_index=True)
            st.caption(
                "길이 가중 교통량 = Σ(링크 길이×교통량)/Σ길이. 경로 주변의 교통 맥락이며 차량 수 합계가 아닙니다. "
                "시간 대리지표 = Σ(지도에서 계산한 링크 길이/연평균 속도). "
                "연평균 속도의 역수는 실측 평균 소요시간과 같지 않습니다. 트럭·신호·정차·구간 연결 시간도 포함하지 않습니다."
            )
            incomplete = context.status.ne("complete_context").sum()
            if incomplete:
                st.warning(
                    f"{incomplete}개 경로는 교통량·속도가 완전하지 않아 시간 등 일부 지표를 미산출했습니다. 빈칸을 0으로 계산하지 않습니다."
                )
            st.download_button(
                "경로별 도로 맥락 CSV",
                context.to_csv(index=False).encode("utf-8-sig"),
                "viewt_route_context.csv",
                "text/csv",
            )
        except (ValueError, KeyError, OSError) as exc:
            st.warning(f"도로 맥락 결합 중단: {exc}")
    a, b = st.columns(2)
    a.download_button(
        "선택 경로 CSV",
        rows.to_csv(index=False).encode("utf-8-sig"),
        "viewt_selected_vehicle_paths.csv",
        "text/csv",
    )
    b.download_button(
        "출처·경로 검사 JSON",
        json.dumps(meta, ensure_ascii=False, indent=2),
        "viewt_vehicle_paths_metadata.json",
        "application/json",
    )
