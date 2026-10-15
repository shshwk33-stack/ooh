"""Provider annual averages: explicit real-file context, no synthetic score fallback."""

import json
from pathlib import Path

import pydeck as pdk
import streamlit as st

from transit_ooh.viewt_roads import combine_roads, load_context, read_official_excel

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "data/processed/viewt_official_roads"


def render():
    st.subheader("View-T 공식 도로자료 · 연평균 일")
    st.info(
        "실제 제공파일의 추정교통량·집계 평균속도입니다. 배송 GPS나 광고 노출 인원으로 해석하지 않습니다."
    )
    choices = ["Excel 직접 업로드"]
    if (LOCAL / "metadata.json").is_file():
        choices.insert(0, "저장된 공식 도로자료")
    source = st.sidebar.radio(
        "공식 도로자료 입력", choices, key="official_roads_source"
    )
    geometry = None
    try:
        if source == "저장된 공식 도로자료":
            context, geometry = load_context(LOCAL)
        else:
            st.caption(
                "View-T에서 받은 TrafficVolume(LINK).xlsx와 AverageSpeed(LINK).xlsx를 그대로 선택하세요. 전체 차종·연평균 일 형식을 지원합니다."
            )
            traffic = st.file_uploader(
                "추정교통량 Excel", type=["xlsx"], key="road_traffic"
            )
            speed = st.file_uploader("평균속도 Excel", type=["xlsx"], key="road_speed")
            if traffic is None or speed is None:
                st.warning(
                    "두 공식 파일을 기다리고 있습니다. 합성 자료로 대신 채우지 않습니다."
                )
                return
            context = combine_roads(
                read_official_excel(traffic.getvalue(), "traffic"),
                read_official_excel(speed.getvalue(), "speed"),
            )
    except (ValueError, KeyError, OSError) as exc:
        st.error(f"공식 파일 검사 실패: {exc}")
        return
    table, meta = context.table, context.metadata
    c1, c2, c3 = st.columns(3)
    c1.metric("동일 도로 번호", f"{len(table):,}개")
    c2.metric("기준연도", str(meta["year"]))
    c3.metric("기간·집계", f"{meta['day_type']} · 연평균 일")
    st.caption(
        f"지역: {meta['district']} | 주요도로망 Level 5.5 | 출처: 한국교통연구원 KTDB View-T"
    )
    labels = {
        "전체 차량 (대/일)": "all_vehicles_per_day",
        "트럭 (대/일)": "trucks_per_day",
        "승용차 (대/일)": "cars_per_day",
        "버스 (대/일)": "buses_per_day",
        "평균속도 (km/h)": "speed_kmh",
    }
    label = st.selectbox("표시 지표", list(labels), key="official_road_metric")
    metric = labels[label]
    if geometry is not None:
        maximum = max(float(table[metric].max()), 1.0)
        for feature in geometry["features"]:
            value = float(feature["properties"][metric])
            t = value / maximum
            feature["properties"]["color"] = [
                int(30 + 210 * t),
                int(130 - 60 * t),
                int(170 - 110 * t),
                220,
            ]
            feature["properties"]["map_value"] = value
        positions = []
        for feature in geometry["features"]:
            g = feature["geometry"]
            lines = (
                [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
            )
            positions.extend(point for line in lines for point in line)
        view = pdk.ViewState(
            longitude=sum(p[0] for p in positions) / len(positions),
            latitude=sum(p[1] for p in positions) / len(positions),
            zoom=12,
        )
        layer = pdk.Layer(
            "GeoJsonLayer",
            geometry,
            stroked=True,
            filled=False,
            get_line_color="properties.color",
            line_width_min_pixels=3,
            pickable=True,
        )
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                map_style=None,
                tooltip={
                    "text": "{road_name}\n도로 번호: {link_id}\n선택 지표: {map_value}"
                },
            )
        )
        st.caption(
            f"{meta['year']}년 도로 형상과 같은 도로 번호로 연결했습니다. 색은 선택 지표의 크기이며 위치가치 점수가 아닙니다. 2023년 경계는 중첩하지 않았습니다."
        )
    else:
        st.caption(
            "이 입력에는 검토한 도로 형상이 없어 표로 표시합니다. 지도 연결은 동일 연도 도로망으로 별도 검증해야 합니다."
        )
    st.subheader("도로별 값 확인")
    st.dataframe(
        table.sort_values([metric, "link_id"], ascending=[False, True]), hide_index=True
    )
    st.warning(
        "현재 연평균 자료에는 실제 일별 표본과 시간대별 값이 없습니다. 일 단위 Bootstrap·시간대 분석·GPS 정차시간·통합 위치가치는 산출하지 않습니다. 인구·시설정보와 공통 공간 단위가 준비되면 기존 모델에 연결합니다."
    )
    a, b = st.columns(2)
    a.download_button(
        "검사한 도로표 CSV",
        table.to_csv(index=False).encode("utf-8-sig"),
        "viewt_roads_annual_context.csv",
        "text/csv",
    )
    b.download_button(
        "출처·집계조건 JSON",
        json.dumps(meta, ensure_ascii=False, indent=2),
        "viewt_roads_metadata.json",
        "application/json",
    )
