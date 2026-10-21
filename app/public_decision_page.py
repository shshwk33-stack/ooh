"""Public aggregate decision study: portable, inspectable, and fieldwork-free."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from transit_ooh.public_decision import (
    compare_portfolios,
    nominal_scores,
    portfolio_metrics,
    top_indices,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/public_decision"
MODE = "공개자료 · 강건한 후보 선정"


def _artifact_paths(manifest):
    paths = []
    for relative, expected in manifest["artifacts_sha256"].items():
        path = (REPORT / relative).resolve()
        if not path.is_relative_to(REPORT.resolve()):
            raise ValueError("결과 목록에 연구 폴더 밖의 경로가 있습니다.")
        paths.append((relative, path, expected))
    return paths


@st.cache_data(show_spinner=False)
def _load(signature):
    """The signature includes artifact metadata, so edits invalidate this cache."""
    manifest = json.loads((REPORT / "summary.json").read_text())
    tables = {}
    for relative, path, expected in _artifact_paths(manifest):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(
                "결과 파일이 기록된 해시와 다릅니다. 연구 결과를 다시 생성하세요."
            )
        if relative.startswith("tables/") and path.suffix == ".csv":
            tables[path.stem] = pd.read_csv(
                path, dtype={"grid_id": str, "seoul_dong_id": str}
            )
    return manifest, tables


def _load_current():
    path = REPORT / "summary.json"
    raw = path.read_bytes()
    manifest = json.loads(raw)
    signature = (
        hashlib.sha256(raw).hexdigest(),
        tuple(
            (relative, p.stat().st_mtime_ns, p.stat().st_size)
            for relative, p, _ in _artifact_paths(manifest)
        ),
    )
    return _load(signature)


@st.cache_data(show_spinner=False)
def _decision(features, k, low, high):
    return compare_portfolios(features, int(k), float(low), float(high))


def _csv(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")


def _figure(name):
    path = REPORT / "figures" / f"{name}.png"
    if path.is_file():
        st.image(str(path), use_container_width=True)


def _table(tables, name):
    if name in tables:
        st.dataframe(tables[name], hide_index=True, use_container_width=True)


def _source_notes(summary, tables):
    with st.expander("어떤 자료를 연결했고, 어디까지 해석할 수 있나요?"):
        st.markdown(
            "서울시 [점포 OA-22172](https://data.seoul.go.kr/dataList/OA-22172/S/1/datasetView.do), "
            "[추정매출 OA-22175](https://data.seoul.go.kr/dataList/OA-22175/S/1/datasetView.do), "
            "[한국교통연구원 KTDB View-T](https://viewt.ktdb.go.kr/cong/map/page.do). "
            "서울시 자료는 공공누리 1유형으로 출처를 표시합니다."
        )
        st.write(
            "원본 도로망에 기관이 부여한 행정동 코드와 상권자료의 코드·명칭·연도를 검사하여 연결합니다. "
            "보유 도로의 길이 가중 맥락이며 정밀 경계로 도로를 분할한 공식 동별 교통량은 아닙니다. "
            "점포는 재고, 교통은 연평균 맥락으로 서로 다른 측정량입니다."
        )
        st.write(
            "실제 확보한 공식 집계·추정 자료를 사용합니다. 실제 배송 GPS, 정차시간, 반복방문, "
            "고유 광고 노출 인원이나 광고 전환율을 측정한 결과로 해석하지 않습니다. "
            "과거 자료의 현재 수정본을 사용한 회고적 연구입니다."
        )
        st.caption(
            "인구의 월~금 조건과 도로의 평일 조건이 같은지 확인되기 전에는 이 축소형 점수에 "
            "인구를 합치지 않습니다. 기존 인구·GPS·가상경로 분석은 다른 화면에 유지합니다."
        )
        _table(tables, "coverage_and_crosswalk")
        if summary.get("sources"):
            st.json(summary["sources"], expanded=False)


def _live(features):
    a, b, c = st.columns([1, 2, 1])
    k = a.selectbox("선택할 후보 수", [3, 5, 10], index=1, key="public_k")
    alpha = b.slider("현재 차량 맥락 비중 (%)", 0, 100, 50, key="public_alpha") / 100
    method = c.selectbox(
        "현재 점수 정규화",
        ["minmax", "log1p_minmax", "percentile"],
        key="public_normalization",
    )
    st.caption(
        "minmax: 후보의 최소·최대 기준 · log1p_minmax: 큰 값의 영향을 줄인 뒤 비교 · "
        "percentile: 값의 크기 대신 순위로 비교. 세 방식 중 검증된 최적 방식은 없습니다."
    )
    low, high = st.slider(
        "강건한 선택에서 고려할 차량 비중 범위 (%)",
        0,
        100,
        (0, 100),
        key="public_weight_range",
    )
    st.caption(
        "현재 점수는 선택한 비중과 정규화로 갱신됩니다. 강건 선택은 4개 점포 분기·분기평균, "
        "차종/도로 범위 4종, 정규화 3종과 고려 범위의 모든 가중치를 검토합니다. "
        "가중치 양 끝을 검사하는 것은 선형 가중합 후회의 볼록성에 따른 계산입니다."
    )
    study = _decision(features, k, low / 100, high / 100)
    solver, matrix = study["solver"], study["matrix"]
    current = nominal_scores(features, alpha, method)
    selected = np.asarray(solver["selected"], dtype=int)
    chosen = set(features.iloc[selected].grid_id)
    available = [
        column
        for column in [
            "grid_id",
            "name",
            "longitude",
            "latitude",
            "stores_mean",
            "traffic_all_local",
        ]
        if column in features
    ]
    display = features[available].merge(current, on="grid_id", validate="one_to_one")
    display["현재 순위"] = (
        display.integrated_score.round(14)
        .rank(ascending=False, method="min")
        .astype(int)
    )
    display["강건 선택"] = display.grid_id.isin(chosen)
    display["현재 Top-K"] = display.index.isin(top_indices(display.integrated_score, k))

    if {"longitude", "latitude"} <= set(display) and display[
        ["longitude", "latitude"]
    ].notna().all().all():
        map_data = display.copy()
        map_data["color"] = map_data.integrated_score.map(
            lambda value: [
                int(215 - 195 * value),
                int(235 - 115 * value),
                int(245 - 85 * value),
                220,
            ]
        )
        map_data["outline"] = map_data["강건 선택"].map(
            lambda value: [235, 115, 25, 255] if value else [255, 255, 255, 140]
        )
        map_data["radius"] = 85 + 230 * map_data.integrated_score
        map_data["score_display"] = map_data.integrated_score.map(
            lambda value: f"{value:.3f}"
        )
        map_data["robust_selected"] = map_data["강건 선택"].map(
            {True: "포함", False: "미포함"}
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            map_data,
            get_position="[longitude, latitude]",
            get_radius="radius",
            get_fill_color="color",
            get_line_color="outline",
            stroked=True,
            line_width_min_pixels=3,
            pickable=True,
        )
        labels = pdk.Layer(
            "TextLayer",
            map_data,
            get_position="[longitude, latitude]",
            get_text="name",
            get_size=13,
            get_color=[35, 55, 75, 255],
            get_pixel_offset=[12, 0],
            get_text_anchor=pdk.types.String("start"),
            font_family=pdk.types.String("Noto Sans CJK KR, sans-serif"),
            character_set=pdk.types.String("auto"),
        )
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer, labels],
                map_provider="carto",
                map_style="light",
                initial_view_state=pdk.ViewState(
                    latitude=float(map_data.latitude.mean()),
                    longitude=float(map_data.longitude.mean()),
                    zoom=12,
                ),
                tooltip={
                    "text": "{name}\n현재 점수: {score_display}\n강건 선택: {robust_selected}"
                },
            )
        )
        st.caption(
            "원 크기·색 농도: 현재 점수 · 주황 테두리: 강건 선택. "
            "좌표는 행정동 표시용이며 실제 배송 거점·정차 위치가 아닙니다."
        )
    else:
        st.caption(
            "검사한 지도 표시 좌표가 없어 지도는 표시하지 않고 후보 표로 제공합니다."
        )

    st.write("**강건하게 선택한 후보:** " + ", ".join(features.iloc[selected]["name"]))
    st.caption(
        f"완전 탐색 {solver['combinations_evaluated']:,}개 조합 · "
        f"같은 최소 최악 손실을 갖는 조합 {solver['optimal_sets']:,}개 · "
        f"최악 손실 {solver['worst_regret']:.4f}"
    )
    if solver["optimal_sets"] > 1:
        st.write(
            "**모든 최적 조합의 공통 후보:** "
            + ", ".join(features.iloc[solver["necessary"]]["name"])
        )
        st.caption(
            "동점 중 대표 조합은 코드 순서로 정합니다. 그 순서가 실무적으로 더 우수하다는 뜻은 아닙니다."
        )
        if "optimal_combinations" in solver:
            optimal_combinations = np.asarray(solver["optimal_combinations"], dtype=int)
        else:
            equal = np.isclose(
                solver["all_worst_regrets"], solver["worst_regret"], rtol=0, atol=1e-12
            )
            optimal_combinations = np.asarray(solver["all_combinations"])[equal]
        optima = pd.DataFrame(
            [
                {"조합": i + 1, "후보": ", ".join(features.iloc[indices]["name"])}
                for i, indices in enumerate(optimal_combinations)
            ]
        )
        with st.expander("동점인 최적 조합 확인"):
            st.dataframe(optima.head(20), hide_index=True, use_container_width=True)
            if len(optima) > 20:
                st.caption("화면은 처음 20개 조합입니다. 전체 조합은 CSV로 제공합니다.")
            st.download_button(
                "모든 최적 조합 CSV",
                _csv(optima),
                "public_all_optimal_sets.csv",
                "text/csv",
            )

    ranked = display.sort_values(["현재 순위", "grid_id"])
    st.dataframe(ranked, hide_index=True, use_container_width=True)
    custom = top_indices(current.integrated_score, k)
    comparison = pd.concat(
        [
            study["comparison"],
            pd.DataFrame(
                [
                    {
                        "model": "C_custom",
                        "k": k,
                        "weight_low": low / 100,
                        "weight_high": high / 100,
                        "selected_ids": ";".join(features.iloc[custom].grid_id),
                        "selected_names": ";".join(features.iloc[custom]["name"]),
                        **portfolio_metrics(matrix, custom),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    st.bar_chart(comparison.set_index("model")[["worst_regret"]])
    st.caption(
        "A=점포 단독, B=차량 맥락 단독, C50/C60=기본 min–max의 고정 비중, "
        "C_custom=현재 설정, R=강건 선택입니다. 손실은 각 가정에서 최선인 K개 집합과의 "
        "평균 점수 차이입니다. 광고효과 손실률이나 경험적 실패확률은 아닙니다."
    )
    left, right = st.columns(2)
    left.download_button(
        "현재 후보 점수 CSV",
        _csv(ranked),
        "public_current_candidate_scores.csv",
        "text/csv",
    )
    right.download_button(
        "현재 강건 선택 비교 CSV",
        _csv(comparison),
        "public_current_portfolio_comparison.csv",
        "text/csv",
    )


def _experiment(summary, tables):
    st.caption(
        "아래는 현재 슬라이더와 별개인 고정된 사후 재현 실험입니다. "
        "2025년 거래 자료는 탐색적 보조 검사이며 사전등록이나 미래 예측 검증이 아닙니다. "
        "후보 선정 계산에는 2025년 거래 값을 넣지 않습니다."
    )
    st.subheader("같은 수의 후보를 선택한 모델 비교")
    _table(tables, "portfolio_comparison")
    _figure("ACQUIRED_worst_regret")
    if "price_of_robustness" in tables:
        st.subheader("강건함을 얻기 위해 기본 점수에서 포기한 정도")
        st.caption(
            "최악의 조건에 대비하면 기본 50:50 조건의 점수를 일부 포기할 수 있습니다. "
            "그 차이는 정규화된 의사결정 점수이며 금전 손실이나 광고효과 감소율은 아닙니다."
        )
        _table(tables, "price_of_robustness")
        _figure("ACQUIRED_price_of_robustness")
    st.write("**주 실험의 모든 최적 조합**")
    _table(tables, "all_optimal_sets")
    st.subheader("선정에 쓰지 않은 조건에서 확인")
    _table(tables, "held_out_quarter_specification")
    _figure("ACQUIRED_held_out_specification")
    with st.expander("도로 범위·정규화 정의를 제외한 검사"):
        st.caption(
            "R은 해당 정의를 빼고 선정한 뒤 제외한 정의에서 평가합니다. A/B/C는 고정 기준선입니다. 미래 예측 정확도 검증과는 구분합니다."
        )
        _table(tables, "held_out_definition_specification")
    st.subheader("2025년 추정 거래 맥락과의 관련성")
    st.info(
        "카드사 기반 추정 거래 자료입니다. 광고효과의 정답이나 완전히 독립된 현장 관측은 아닙니다. "
        "1분기를 주 기준으로 두고 다른 분기도 모두 공개합니다."
    )
    _table(tables, "external_context_association")
    _figure("ACQUIRED_external_tradeoff")
    with st.expander("동점 대안·보고 업종 범위까지 확인"):
        _table(tables, "external_context_all_optima")
        count = summary.get("common_transaction_industries")
        if count is not None:
            st.caption(
                f"모든 후보·분기에 공통으로 보고된 {count}개 업종으로 제한한 보조 검사입니다. 누락 업종은 0으로 채우지 않습니다."
            )
        _table(tables, "external_context_common_sectors")
    with st.expander("가중치별 순위·Top-K 중복률"):
        _table(tables, "weight_sensitivity")
    if "portfolio_comparison" in tables:
        st.download_button(
            "고정 연구 결과표 CSV",
            _csv(tables["portfolio_comparison"]),
            "ACQUIRED_public_portfolio_comparison.csv",
            "text/csv",
        )


def render():
    st.subheader("공개자료 연구 · 강건한 후보 지역 선정")
    st.info(
        "공식 집계·추정 자료를 이용한 의사결정 연구입니다. 현장관측 없이 후보 행정동을 사전 선별합니다."
    )
    if not (REPORT / "summary.json").is_file():
        st.warning(
            "아직 공개자료 연구 결과가 없습니다. 수집·분석 스크립트를 실행하거나 연구 패키지의 reports/public_decision 폴더를 준비하세요."
        )
        return
    try:
        summary, tables = _load_current()
        features = (
            tables["candidate_features"].sort_values("grid_id").reset_index(drop=True)
        )
        if len(features) < 10 or features.grid_id.duplicated().any():
            raise ValueError("비교 가능한 고유 후보 10곳 이상이 필요합니다.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"연구 결과 검사 실패: {exc}")
        return
    total = len(tables.get("coverage_and_crosswalk", features))
    a, b, c, d = st.columns(4)
    a.metric("연구 지역", "서울 마포구")
    b.metric("비교 가능한 후보", f"{len(features)} / {total}개 동")
    c.metric(
        "동 코드가 확인된 도로", f"{summary.get('network_links_matched', '미기록')}개"
    )
    d.metric(
        "입력 / 보조 확인 자료",
        f"{summary.get('year_inputs', '미기록')} / {summary.get('year_external_context', '미기록')}년",
    )
    excluded = summary.get("excluded", [])
    if excluded:
        names = ", ".join(
            str(row.get("name", row.get("grid_id", ""))) for row in excluded
        )
        st.warning(
            f"{names}: 보유 자료의 비교 가능한 도로 맥락이 없어 제외했습니다. 실제 교통량이 0이라는 뜻은 아닙니다."
        )
    st.caption(
        "A: 보고된 전체 점포의 분기 평균 재고 · B: 고속도로·도시고속도로·연결로를 제외한 보유 도로의 "
        "길이 가중 차량 맥락 · C: 두 성분의 가중합. 인구가 포함된 기존 전체 Spatial 모델과 구분한 축소형 모델입니다."
    )
    _source_notes(summary, tables)
    live, experiment = st.tabs(["내 선호로 후보 비교", "고정 연구 실험·외부 맥락"])
    try:
        with live:
            _live(features)
        with experiment:
            _experiment(summary, tables)
    except (ValueError, KeyError, TypeError) as exc:
        st.error(f"후보 비교를 계산하지 못했습니다: {exc}")
