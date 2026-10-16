"""Acquired View-T population context, distinct from synthetic decision experiments."""

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from transit_ooh.viewt_boundary import choropleth, load_boundary
from transit_ooh.viewt_population import combine_inflow_batches, load_population

LOCAL = Path(__file__).resolve().parents[1] / "data/processed/viewt_population"


def render():
    st.subheader("View-T 공식 인구자료 · 마포구")
    st.info(
        "실제 확보한 기관 집계·추정 자료입니다. 통행 횟수이며 고유 인원·보행자 수·광고 노출 인원이 아닙니다."
    )
    if not (LOCAL / "manifest.json").is_file():
        st.warning("검증한 인구 파일이 아직 없습니다. 자료 수집·변환 후 표시합니다.")
        return
    try:
        datasets = load_population(LOCAL)
        scope = st.selectbox(
            "분석 범위",
            ["마포구 동별 유입", "마포구 전체 유입", "마포구 내 동 사이 O/D"],
            key="population_scope",
        )
        candidates = [
            d
            for d in datasets
            if (
                (
                    scope == "마포구 동별 유입"
                    and d[2]["kind"] == "inflow"
                    and d[2]["destination_unit"] == "dong"
                )
                or (
                    scope == "마포구 전체 유입"
                    and d[2]["kind"] == "inflow"
                    and d[2]["destination_unit"] == "sigungu"
                )
                or (scope == "마포구 내 동 사이 O/D" and d[2]["kind"] == "od")
            )
        ]
        if not candidates:
            st.warning("이 범위의 자료를 아직 확보하지 않았습니다.")
            return
        periods = {}
        for d in candidates:
            meta = d[2]
            key = (
                meta["requested_start"],
                meta["requested_end"],
                meta["requested_days"],
            )
            label = f"{key[0]} ~ {key[1]} · 요청 {key[2]}일"
            periods.setdefault(label, []).append(d)
        period = st.selectbox("확보한 기간", list(periods), key="population_period")
        selected = periods[period]
        meta = selected[0][2]
        frame = (
            combine_inflow_batches(selected)
            if meta["kind"] == "inflow"
            else selected[0][1].copy()
        )
    except (ValueError, KeyError, OSError) as exc:
        st.error(f"인구 자료 검사 실패: {exc}")
        return

    include_internal = True
    if meta["kind"] == "inflow":
        include_internal = st.checkbox(
            "마포구 내부 이동 포함", value=True, key="population_internal"
        )
    else:
        st.caption("현재 범위는 마포구 내부의 서로 다른 동 사이 이동입니다.")
    if meta["kind"] == "inflow" and not include_internal:
        frame = frame[~frame.within_mapo].copy()
    if frame.empty:
        st.warning("이 조건으로 반환된 행이 없습니다. 결측을 0으로 대신하지 않습니다.")
        return
    days = meta["requested_days"]
    total = float(frame.period_trips.sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("반환된 O/D 관계", f"{len(frame):,}개")
    c2.metric("기간 통행량 합계", f"{total:,.0f}")
    c3.metric("요청일수로 나눈 하루 평균", f"{total / days:,.1f}")
    st.caption(
        "누적 통행 횟수입니다. 같은 사람이 여러 번 이동할 수 있습니다. 원본의 총계·하루 평균·면적당 값은 서로 더하지 않습니다."
    )
    st.caption(
        f"기준연도 {meta['year']} | 요청일 {days}일 | 출발·도착 시간 0~23시 | 성별·연령·체류특성 전체. 원자료의 날짜별 완전성은 별도 확인 대상입니다."
    )

    if scope == "마포구 전체 유입":
        display = frame[["origin_name", "period_trips"]].copy()
        display["평균 통행량"] = display.period_trips / days
        st.subheader("출발지역별 반환 통행량 · 상위 15개")
        st.bar_chart(
            display.nlargest(15, "평균 통행량").set_index("origin_name")[
                ["평균 통행량"]
            ],
            horizontal=True,
        )
    else:
        points = frame.groupby(
            ["destination_id", "destination_name"], as_index=False
        ).agg(
            period_trips=("period_trips", "sum"),
            latitude=("destination_latitude", "first"),
            longitude=("destination_longitude", "first"),
        )
        points["daily_mean"] = points.period_trips / days
        points["name"] = points.destination_name.str.replace(
            "서울특별시 마포구 ", "", regex=False
        )
        points["radius"] = (
            70 + 330 * (points.daily_mean / points.daily_mean.max()) ** 0.5
        )
        layers = [
            pdk.Layer(
                "ScatterplotLayer",
                points,
                get_position="[longitude, latitude]",
                get_radius="radius",
                get_fill_color=[17, 130, 163, 190],
                pickable=True,
            )
        ]
        boundary_dir = LOCAL.parent / "viewt_boundaries"
        if (boundary_dir / "metadata.json").exists() and st.checkbox(
            "2024년 공식 동 경계 표시", value=True, key="population_boundaries"
        ):
            try:
                boundary, _ = load_boundary(boundary_dir)
                colored = choropleth(boundary, points, meta["year"])
                layers.insert(
                    0,
                    pdk.Layer(
                        "GeoJsonLayer",
                        colored,
                        get_fill_color="properties.color",
                        get_line_color=[70, 95, 120, 220],
                        line_width_min_pixels=1,
                        pickable=True,
                    ),
                )
                st.caption(
                    "2024년 View-T 공식 웹 지도 경계 · 인구자료와 16개 동 코드·명칭 일치. 정밀 도로 배분용으로 검증된 경계는 아닙니다."
                )
            except (ValueError, KeyError, OSError) as exc:
                st.warning(f"동 경계 표시 중단: {exc}")
        if meta["kind"] == "od":
            arcs = frame.copy()
            arcs["name"] = arcs.origin_name + " → " + arcs.destination_name
            arcs["daily_mean"] = arcs.period_trips / days
            layers.insert(
                0,
                pdk.Layer(
                    "ArcLayer",
                    arcs,
                    get_source_position="[origin_longitude, origin_latitude]",
                    get_target_position="[destination_longitude, destination_latitude]",
                    get_source_color=[20, 150, 170, 100],
                    get_target_color=[235, 110, 45, 100],
                    get_width=2,
                    pickable=True,
                ),
            )
        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(
                    latitude=points.latitude.mean(),
                    longitude=points.longitude.mean(),
                    zoom=12,
                ),
                map_style=None,
                tooltip={"text": "{name}\n하루 평균 통행: {daily_mean}"},
            )
        )
        st.caption(
            "점은 기관이 제공한 구역 대표 위치입니다. 연결선은 O/D 관계이며 실제 이동경로나 도로 형상이 아닙니다."
        )
        st.subheader("동별 반환 통행량 비교")
        st.bar_chart(
            points.sort_values("daily_mean", ascending=False).set_index("name")[
                ["daily_mean"]
            ],
            horizontal=True,
        )
        st.caption(
            "위치가치 점수나 모델 성능 순위가 아닙니다. 구 내 동 사이 O/D는 같은 동 내부 이동을 제외합니다."
        )
    st.dataframe(frame.sort_values("period_trips", ascending=False), hide_index=True)
    st.warning(
        "기간 합계를 날짜별 표본으로 복제하지 않습니다. 현재 화면에는 일별 Bootstrap이나 통합 위치가치 점수를 적용하지 않습니다. 도로 링크·행정동의 공간 대응과 교통자료의 평일 정의 확인 후 모델 결합을 검토합니다."
    )
    a, b = st.columns(2)
    a.download_button(
        "현재 조건 CSV",
        frame.to_csv(index=False).encode("utf-8-sig"),
        "viewt_population_selected.csv",
        "text/csv",
    )
    b.download_button(
        "출처·요청 조건 JSON",
        json.dumps(
            {
                "datasets": [d[2] for d in selected],
                "include_mapo_internal": include_internal,
                "filtered_rows": len(frame),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "viewt_population_selection.json",
        "application/json",
    )
    report = LOCAL.parent / "viewt_acquired_report"
    summary_file = report / "summary.json"
    if summary_file.is_file():
        summary = json.loads(summary_file.read_text())
        hashes = summary.get("source_manifests_sha256", {})
        inputs = [
            LOCAL / "manifest.json",
            LOCAL.parent / "viewt_vehicle_paths/metadata.json",
        ]
        current = all(
            p.is_file()
            and hashes.get(str(p.relative_to(LOCAL.parents[2])))
            == hashlib.sha256(p.read_bytes()).hexdigest()
            for p in inputs
        )
        daily_file = report / "daily_stability_summary.json"
        if daily_file.is_file():
            daily = json.loads(daily_file.read_text())
            daily_current = (
                daily.get("source_manifest_sha256")
                == hashlib.sha256(inputs[0].read_bytes()).hexdigest()
            )
            artifacts = daily.get("artifacts_sha256", {})
            daily_current = (
                daily_current
                and bool(artifacts)
                and all(
                    Path(name).name == name
                    and (report / name).is_file()
                    and hashlib.sha256((report / name).read_bytes()).hexdigest()
                    == digest
                    for name, digest in artifacts.items()
                )
            )
            if daily_current:
                st.subheader("실제 날짜별 조회에 기반한 유입 순위 안정성")
                st.caption(
                    f"별도 분석: {daily['sample_start']}~{daily['sample_end']}의 {daily['days']}일 · 마포구 내부 포함 전체 유입. 위쪽 기간·내부 이동 필터와 별개입니다."
                )
                if daily.get("missing_dates"):
                    st.warning(
                        f"계획 {len(daily['planned_dates'])}일 중 {daily['days']}일 확보. 미확보 날짜: {', '.join(daily['missing_dates'])}. 서버의 빈 결과를 0으로 바꾸지 않고 해당 날짜를 제외했습니다."
                    )
                a, b, c = st.columns(3)
                a.metric(
                    "전반·후반 순위 상관",
                    f"{daily['first_half_last_half_spearman']:.3f}",
                )
                b.metric(
                    "전반·후반 Top-5 중복",
                    f"{daily['first_half_last_half_top_k_overlap']['5']:.0%}",
                )
                c.metric(
                    "전반·후반 Top-10 중복",
                    f"{daily['first_half_last_half_top_k_overlap']['10']:.0%}",
                )
                method = st.selectbox(
                    "재표집 단위",
                    ["week", "day"],
                    format_func=lambda x: (
                        "한 주씩 재추출 (주 내 변동 보존)"
                        if x == "week"
                        else "하루씩 재추출"
                    ),
                    key="population_bootstrap_method",
                )
                stability = pd.read_csv(report / "population_rank_stability.csv")
                st.dataframe(
                    stability[stability.method.eq(method)].sort_values(
                        "mean_reported_trips", ascending=False
                    ),
                    hide_index=True,
                )
                st.image(str(report / "population_top5_stability.png"))
                st.caption(
                    "12월 4개 주에 한정한 통행량 순위의 조건부 안정성입니다. 독립적인 정확도·광고 효과 검증이 아니며, 계절 대표성이나 통합 모델 성능을 입증하지 않습니다."
                )
            else:
                current = False
                st.caption(
                    "일별 안정성 결과의 입력 또는 결과 파일이 바뀌었습니다. 보고서를 다시 생성하세요."
                )
        if current:
            contents = BytesIO()
            with zipfile.ZipFile(contents, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(report.iterdir()):
                    if path.is_file() and path.suffix in {
                        ".csv",
                        ".png",
                        ".svg",
                        ".json",
                    }:
                        archive.write(path, path.name)
            st.download_button(
                "확보 자료 연구 그래프·결과표 ZIP",
                contents.getvalue(),
                "Transit_OOH_ViewT_Acquired_Report.zip",
                "application/zip",
            )
            st.caption(
                "ZIP은 전체 확보 자료의 요약입니다. 현재 화면 필터와 별개이며 지도·인구·경로의 자료 성격과 제한을 함께 확인하세요."
            )
