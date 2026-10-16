"""Interactive district-scale aggregate-data workbench."""

import json
from io import BytesIO

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from transit_ooh.viewt import (
    DISTRICTS,
    Bundle,
    analyze_bundle,
    demo_bundle,
    milk_run,
    read_bundle,
    validate_bundle,
    workbook,
)


@st.cache_data(show_spinner=False)
def demo_bytes(district):
    return workbook(demo_bundle(district))


@st.cache_data(show_spinner=False)
def compute(payload, alpha, hours, dates, population_weight, bootstrap_unit):
    return analyze_bundle(
        read_bundle(payload),
        alpha,
        hours,
        dates,
        bootstrap_n=100,
        population_weight=population_weight,
        bootstrap_unit=bootstrap_unit,
    )


def render():
    with st.sidebar:
        district = st.selectbox("연구 자치구", list(DISTRICTS), key="viewt_district")
        source = st.radio(
            "View-T 입력",
            ["합성 지역 데모 · View-T 미수집", "Excel·CSV 업로드"],
            key="viewt_source",
        )
        weight = st.slider("Mobility 가중치 (%)", 0, 100, 50, 1, key="viewt_weight")
        st.caption(f"Spatial {100 - weight}% · 기준 50:50 / 기존 가정 60:40")
        population_weight = st.slider(
            "Spatial 안에서 인구통행 비중 (%)",
            0,
            100,
            70,
            5,
            key="viewt_population_weight",
        )
        st.caption(
            f"POI {100 - population_weight}% · 70:30도 검증된 최적값이 아닌 연구 가정입니다."
        )
        bootstrap_unit = st.selectbox(
            "재표집 단위",
            ["day", "week"],
            format_func=lambda x: (
                "날짜별" if x == "day" else "주별 · 주 안의 날짜를 함께 추출"
            ),
            key="viewt_bootstrap_unit",
        )
    if source.startswith("합성"):
        payload = demo_bytes(district)
        bundle = read_bundle(payload)
        st.warning(
            "SYNTHETIC · View-T 실자료가 아닙니다. 선택 자치구 중심 부근의 가상 거점·통행량·POI로 기능을 검증합니다."
        )
    else:
        st.info(
            "파일 메타데이터는 사용자가 선언한 출처입니다. 이 앱은 공식 API 인증이나 파일 진위 확인을 수행하지 않습니다."
        )
        with st.expander("준비할 파일 · 공급자 열 이름 매핑", expanded=True):
            st.write(
                "Excel: metadata / candidates / vehicle_paths / poi / population_segments 또는 population_od 시트. CSV: 같은 이름의 CSV 파일들과 metadata.json을 함께 선택하세요. 공급자 원본 형식과 이 프로젝트 형식은 다를 수 있습니다."
            )
            files = st.file_uploader(
                "Excel 1개 또는 CSV·metadata.json 묶음",
                type=["xlsx", "csv", "json"],
                accept_multiple_files=True,
            )
            mapping_text = st.text_area(
                "선택: 열 이름 대응 JSON (표 이름 → 원본 열 이름 → 표준 열 이름)",
                value="{}",
                key="viewt_mapping",
            )
            encoding = st.selectbox("CSV 문자 인코딩", ["utf-8-sig", "cp949"])
        if not files:
            st.download_button(
                "합성 예시 Excel · 형식 확인용",
                demo_bytes(district),
                "viewt_SYNTHETIC_example.xlsx",
            )
            st.warning(
                "업로드 대기 중입니다. 공식 데이터 미확보 상태를 합성 결과로 대체하지 않습니다."
            )
            return
        try:
            if len(files) == 1 and files[0].name.endswith(".xlsx"):
                sheets = pd.read_excel(
                    BytesIO(files[0].getvalue()), sheet_name=None, dtype=object
                )
                metadata = json.loads(str(sheets.pop("metadata").iloc[0]["json"]))
            else:
                named = {f.name: f for f in files}
                if len(named) != len(files):
                    raise ValueError("Duplicate file names")
                metadata = json.loads(named.pop("metadata.json").getvalue())
                if any(not name.endswith(".csv") for name in named):
                    raise ValueError(
                        "CSV bundle only accepts metadata.json and named CSV tables"
                    )
                sheets = {
                    name[:-4]: pd.read_csv(
                        BytesIO(f.getvalue()), dtype=object, encoding=encoding
                    )
                    for name, f in named.items()
                }
            mapping = json.loads(mapping_text)
            sheets = {
                name: d.rename(columns=mapping.get(name, {}))
                for name, d in sheets.items()
            }
            if any(d.columns.duplicated().any() for d in sheets.values()):
                raise ValueError("Column mapping produced duplicate fields")
            bundle = validate_bundle(Bundle(sheets, metadata))
            if bundle.metadata["district_code"] != DISTRICTS[district][0]:
                raise ValueError("선택 자치구와 파일 자치구 코드가 다릅니다")
            payload = workbook(bundle)
        except (ValueError, KeyError, TypeError, OSError) as e:
            st.error(f"입력 검증 실패: {e}")
            return
        st.success(
            f"구조·공간 키·기간·시간대·단위 검사 통과 · 입력 분류: {bundle.observation_type}"
        )
    with st.sidebar:
        hours = st.multiselect(
            "분석 시간대 (Asia/Seoul)",
            bundle.metadata["hours"],
            default=bundle.metadata["hours"],
            key="viewt_hours",
        )
        all_dates = sorted(bundle.tables["vehicle_paths"].date.unique())
        dates = st.multiselect(
            "분석 날짜", all_dates, default=all_dates, key="viewt_dates"
        )
        basemap = st.checkbox("온라인 배경지도 (CARTO / OSM)", value=True)
    if not hours or not dates:
        st.info("분석할 날짜와 시간대를 한 개 이상 선택하세요.")
        return
    with st.spinner("동일 후보군 점수·순위·일 단위 Bootstrap 계산 중…"):
        try:
            result = compute(
                payload,
                weight / 100,
                tuple(hours),
                tuple(dates),
                population_weight / 100,
                bootstrap_unit,
            )
        except (ValueError, KeyError, TypeError) as exc:
            st.error(f"분석 조건 검사 실패: {exc}")
            return
    scores = result["scores"].sort_values(
        ["integrated_score", "grid_id"], ascending=[False, True]
    )
    stability = result["selection_stability"]
    a, b, c, d = st.columns(4)
    a.metric("분석 후보", len(scores))
    b.metric("관측/시나리오 일수", len(dates))
    c.metric("Mobility : Spatial", f"{weight} : {100 - weight}")
    d.metric(
        "Top-5 재표집 선정빈도 ≥80%",
        int((stability.top5_probability >= 0.8).sum())
        if not stability.empty
        else "미산출",
    )
    st.caption(
        "Model A: Spatial · B: 차량 통행량 대리지표 · C: 가중 통합 | 인구 통행은 광고 노출 인원이 아닙니다. GPS 정차시간·반복 방문은 이 모드에서 측정하지 않습니다."
    )
    map_tab, rank_tab, sensitivity_tab, source_tab = st.tabs(
        [
            "GIS · 가상 밀크런",
            "후보지 · 모델 비교",
            "민감도 · 선정 안정성",
            "출처 · 다운로드",
        ]
    )
    with map_tab:
        left, right = st.columns([3, 1])
        with right:
            model = st.selectbox("지도 표시 모델", ["integrated", "static", "mobility"])
            heatmap = st.checkbox("밀도 히트맵 표시", value=True)
            hubs = st.multiselect(
                "순회 거점 (선택 순서)",
                scores.grid_id.tolist(),
                default=scores.head(4).grid_id.tolist(),
                format_func=lambda z: scores.set_index("grid_id").loc[z, "name"],
            )
            cycles = st.number_input("반복 회차", 1, 10, 2)
            speed = st.slider("가정 속도 (km/h)", 5, 50, 20)
            dwell = st.slider("거점별 가정 정차 (분)", 0, 30, 5)
        plotted = scores.copy()
        value = plotted[model + "_score"]
        plotted["color"] = [
            [int(45 + 195 * x), int(140 - 80 * x), int(185 - 130 * x), 210]
            for x in value
        ]
        plotted["map_score"] = value.round(4)
        layers = []
        if heatmap:
            layers.append(
                pdk.Layer(
                    "HeatmapLayer",
                    plotted,
                    get_position="[longitude, latitude]",
                    get_weight=model + "_score",
                    radius_pixels=60,
                    intensity=1,
                    threshold=0.03,
                )
            )
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                plotted,
                get_position="[longitude, latitude]",
                get_fill_color="color",
                get_radius=80,
                pickable=True,
            )
        )
        route = pd.DataFrame()
        try:
            route_bundle = Bundle(
                {
                    k: v[v.date.isin(dates)].copy() if "date" in v else v
                    for k, v in bundle.tables.items()
                },
                bundle.metadata,
            )
            route = milk_run(route_bundle, hubs, hours, int(cycles), speed, dwell)
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    route,
                    get_path="path",
                    get_color=[26, 66, 105, 210],
                    width_min_pixels=3,
                    pickable=False,
                )
            )
        except ValueError as e:
            st.warning(str(e))
        with left:
            st.pydeck_chart(
                pdk.Deck(
                    layers=layers,
                    initial_view_state=pdk.ViewState(
                        longitude=float(scores.longitude.mean()),
                        latitude=float(scores.latitude.mean()),
                        zoom=12.8,
                    ),
                    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                    if basemap
                    else None,
                    tooltip={
                        "text": "{name}\nScore: {map_score}\n{input_observation_type}"
                    },
                )
            )
            st.caption(
                "© CARTO / OpenStreetMap contributors. 가상 경로는 구역 중심을 연결한 개략선입니다. 실제 도로·운행 궤적이 아니며, 업로드 경로의 방향별 연결만 사용합니다."
            )
        if not route.empty:
            st.write(
                f"가상 순회: {len(route)}개 구역 연결 · 예상 이동 {(route.travel_seconds.sum() / 60):.1f}분 + 가정 정차 {route.assumed_dwell_seconds.sum() / 60:.0f}분 · {route.observation_type.iloc[0]}"
            )
            st.download_button(
                "가상 밀크런 CSV",
                route.to_csv(index=False).encode("utf-8-sig"),
                "milk_run_assumed.csv",
            )
        hourly = (
            bundle.tables["population_segments"]
            if bundle.metadata["population_basis"] == "segments"
            else bundle.tables["population_od"]
        )
        hourly = (
            hourly[hourly.date.isin(dates) & hourly.hour.isin(hours)]
            .groupby("hour")
            .population_flow.sum()
        )
        st.bar_chart(hourly.rename("인구 통행량 · 합계 (노출 인원 아님)"))
    with rank_tab:
        k = st.radio(
            "후보 목록",
            sorted({min(5, len(scores)), min(10, len(scores)), len(scores)}),
            horizontal=True,
            format_func=lambda x: f"Top-{x}",
        )
        cols = [
            "grid_id",
            "name",
            "integrated_rank",
            "integrated_score",
            "static_score",
            "mobility_score",
            "population",
            "vehicle_flow",
            "poi_count",
            "input_observation_type",
        ]
        st.dataframe(scores[cols].head(k), hide_index=True)
        st.write("50:50 · 기존 60:40 · 사용자 선택의 순위")
        ranks = result["weight_ranks"]
        selected = ranks[
            np.isclose(ranks.mobility_weight, 0.5)
            | np.isclose(ranks.mobility_weight, 0.6)
            | np.isclose(ranks.mobility_weight, weight / 100)
        ]
        st.dataframe(
            selected.pivot(
                index="grid_id", columns="mobility_weight", values="integrated_rank"
            )
        )
        st.dataframe(result["model_comparison"], hide_index=True)
        st.caption(
            "순위상관·중복률은 모델 간 의사결정의 차이입니다. 제안 모델의 정확도 향상이나 60:40의 최적성을 뜻하지 않습니다."
        )
    with sensitivity_tab:
        st.subheader("가중치를 바꿔도 유지되는 후보")
        st.caption(
            "두 점수가 교차하는 가중치를 계산해 0~100% 전체 구간을 검사합니다. "
            "5% 간격 표에서 놓칠 수 있는 좁은 순위 변화도 포함합니다. "
            "weight_share는 가중치 구간의 비율이며 관측 확률이 아닙니다."
        )
        robust = result["robust_candidates"]
        st.dataframe(robust.sort_values(["worst_regret", "grid_id"]), hide_index=True)
        st.caption(
            "worst_regret: 가중치가 달라졌을 때 1위와 벌어질 수 있는 최대 점수 차이. "
            "necessary/possible_share: 동점을 고려한 Top-K 포함 범위. "
            "Pareto 후보는 두 점수가 모두 다른 후보에 뒤지지는 않는 후보입니다."
        )
        with st.expander("순위가 바뀌는 정확한 가중치 구간"):
            st.dataframe(result["weight_intervals"], hide_index=True)
        with st.expander("정규화 방식·Spatial 내부 비중을 바꿔도 결과가 유지되나요?"):
            st.dataframe(result["specification_comparison"], hide_index=True)
            st.dataframe(result["feature_diagnostics"], hide_index=True)
            st.caption(
                "minmax · log1p_minmax · percentile과 인구/POI 비중 0·30·50·70·100%를 비교합니다. "
                "같은 후보군의 순위가 얼마나 달라지는지 보는 분석이며 결과가 좋은 설정을 정답에 맞춰 선택하지 않습니다. "
                "상수 특성에는 판별력을 부여하지 않습니다."
            )
        w = result["weight_sensitivity"]
        st.line_chart(
            w.pivot(index="mobility_weight", columns="top_k", values="top_k_overlap")
        )
        st.caption(
            "현재 가중치의 Top-K와 비교한 중복률 · 동점은 grid_id 순으로 결정합니다."
        )
        st.line_chart(
            result["weight_ranks"].pivot(
                index="mobility_weight", columns="grid_id", values="integrated_rank"
            )
        )
        if stability.empty:
            st.warning(
                "Bootstrap은 선택한 단위의 묶음이 3개 이상 필요합니다. 현재 선택 구간에서는 미산출입니다."
            )
        else:
            st.dataframe(
                stability.sort_values("top5_probability", ascending=False),
                hide_index=True,
            )
        st.dataframe(result["temporal_holdout"], hide_index=True)
        st.caption(
            "Bootstrap: 인구·차량을 같은 날짜/주 묶음으로 함께 복원 추출, 정규화·POI 고정. "
            "주별 방식은 주 안의 상관을 보존하지만 주 사이 상관과 계절성까지 보장하지 않습니다. "
            "현재 확보·선택 표본에 조건부인 안정성이며 시간 holdout도 독립 광고효과 검증은 아닙니다."
        )
    with source_tab:
        st.json(bundle.metadata)
        st.write(
            "공식 도로·인구·차량경로 자료는 각각의 공식자료 화면에서 확인하세요. "
            "이 화면은 공통 공간·기간 단위가 검증된 입력 묶음의 의사결정 실험입니다. "
            "현재 기본 예제는 합성이며, 확보한 공식 자료를 자동으로 혼합하지 않습니다."
        )
        for name, frame in result.items():
            export = frame.assign(
                input_observation_type=bundle.observation_type,
                current_mobility_weight=weight / 100,
                selected_hours=",".join(map(str, hours)),
                selected_dates=",".join(dates),
            )
            st.download_button(
                name + " CSV",
                export.to_csv(index=False).encode("utf-8-sig"),
                f"{name}_{bundle.observation_type}.csv",
                key="viewt_download_" + name,
            )
        st.download_button(
            "입력 Excel 보존", payload, f"input_{bundle.observation_type}.xlsx"
        )
