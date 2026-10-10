"""Research-first GIS interface. Public observations are never mixed into the demo."""

from pathlib import Path
import json
import pandas as pd
import streamlit as st
import pydeck as pdk
from transit_ooh.io import load_config
from transit_ooh.synthetic import generate
from transit_ooh.pipeline import analyze
from transit_ooh.scoring import score
from transit_ooh.stops import evaluate_stops

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(
    page_title="Transit OOH · Research Lab", page_icon="◈", layout="wide"
)
st.markdown(
    """<style>
.stApp {background:#f6f8fc;} h1,h2,h3{color:#142e4c;}
[data-testid="stMetric"]{background:white;border:1px solid #e1e8f0;border-radius:12px;padding:18px;}
.block-container{padding-top:2rem;} .eyebrow{color:#317e91;letter-spacing:.14em;font-size:.78rem;font-weight:700;}
</style>""",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="eyebrow">MOBILITY × SPATIAL CONTEXT · RESEARCH WORKBENCH</div>',
    unsafe_allow_html=True,
)
st.title("Transit OOH 위치가치 연구")
st.caption(
    "배송활동이 후보지 선정과 안정성에 주는 정보 · 캡스톤디자인2 / 산업공학회 연구"
)


@st.cache_data(show_spinner=False)
def load_demo(grid_size, radius, min_seconds):
    cfg = load_config(ROOT / "configs/default.yaml")
    cfg.update(
        grid_size_m=grid_size, stop_radius_m=radius, min_stop_seconds=min_seconds
    )
    gps, truth, ctx, meta, _ = generate(seed=cfg["seed"], **cfg["synthetic"])
    a = analyze(gps, cfg, ctx, meta)
    m, _ = evaluate_stops(a.stops, truth)
    return a, truth, meta, m


def table(name):
    p = ROOT / "reports/tables" / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


with st.sidebar:
    st.header("분석 설정")
    mode = st.radio("자료 구분", ["합성 GT 연구 데모", "실제 공개 자료 · 별도 분석"])
    st.caption("실측 자료와 합성 데모는 서로 결합하지 않습니다.")

if mode == "실제 공개 자료 · 별도 분석":
    st.info(
        "public_observed · 공개 배송 이벤트/방문지와 공간자료의 기술통계입니다. 연속 차량 GPS·정차시간·광고효과의 실증 결과가 아닙니다."
    )
    p = ROOT / "reports/runs/public_summary.json"
    if p.exists():
        summary = json.loads(p.read_text())
        a, b, c = st.columns(3)
        a.metric("Amazon 실제 경로", f"{summary.get('amazon', {}).get('routes', 0):,}")
        b.metric("LaDe 실제 이벤트", f"{summary.get('lade', {}).get('rows', 0):,}")
        c.metric(
            "서울 OSM amenity node",
            f"{summary.get('osm', {}).get('amenity_nodes', 0):,}",
        )
        for key, label in [
            ("amazon", "Amazon · 2018 미국 배송 방문지"),
            ("lade", "LaDe · 중국 Jilin 기사 작업 이벤트"),
            ("osm", "OpenStreetMap · 현재 서울 지도 스냅샷"),
        ]:
            with st.expander(label, expanded=True):
                st.json(summary.get(key, {}))
                if summary.get(key, {}).get("status") != "analyzed":
                    st.warning("이번 실행에서는 원본을 확보·분석하지 못했습니다.")
                    continue
                file = {
                    "amazon": "public_amazon_station_summary",
                    "lade": "public_lade_event_summary",
                    "osm": "public_osm_amenity_summary",
                }[key]
                d = table(file)
                st.dataframe(d, hide_index=True)
                if len(d):
                    st.download_button(
                        f"{label} 요약 다운로드",
                        d.to_csv(index=False),
                        file_name=file + "_public_observed.csv",
                        mime="text/csv",
                    )
        osm = table("public_osm_grid_counts")
        if len(osm) and summary.get("osm", {}).get("status") == "analyzed":
            st.subheader("서울 실제 POI 분포 · 공간자료만 표시")
            st.caption(
                "© OpenStreetMap contributors · ODbL-1.0 · node amenity만 포함. 유동인구/완전한 상권 목록이 아닙니다."
            )
            layer = pdk.Layer(
                "ScatterplotLayer",
                osm,
                get_position="[longitude, latitude]",
                get_radius="poi_nodes * 3 + 10",
                get_fill_color=[40, 140, 150, 180],
                pickable=True,
            )
            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=pdk.ViewState(
                        latitude=37.566, longitude=126.978, zoom=14
                    ),
                    map_style=None,
                    tooltip={"text": "POI nodes: {poi_nodes}\npublic_observed · ODbL"},
                )
            )
    else:
        st.warning(
            "실측 기술통계가 아직 없습니다. README의 public-analysis 절차를 실행하세요. 합성 결과로 대체하지 않습니다."
        )
    st.stop()

with st.sidebar:
    size = st.selectbox("미터 격자 크기", [100, 200, 400], index=1)
    radius = st.slider("정차 반경 (m)", 10, 80, 30, 5)
    minimum = st.selectbox("최소 정차시간 (초)", [60, 120, 300], index=1)
    alpha = st.slider("이동정보 가중치 α", 0.0, 1.0, 0.6, 0.05)
    model = st.selectbox("지도 점수", ["Integrated", "Static-only", "Mobility-only"])
    st.caption(
        "EPSG:32652 · UTC 저장 / Asia/Seoul 표시\n최대 연결 간격 180초 · GT와 독립 탐지"
    )
with st.spinner("합성 시나리오 분석 중…"):
    analysis, truth, meta, metrics = load_demo(size, radius, minimum)
scores, _ = score(analysis.features, alpha, analysis.normalizer)
scores = scores.merge(analysis.grid.cells(scores.grid_id), on="grid_id")
scores["observation_type"] = "synthetic"
scores["score_type"] = "assumed_decision_index"
scores["source"] = "synthetic_schedule_v1 + synthetic_independent_spatial_field"
scores["mobility_weight"] = alpha
st.warning(
    "SYNTHETIC · 이 화면의 GPS·인구·POI는 모두 합성 데이터입니다. 점수는 상대적 의사결정 지표이며 실제 광고효과나 국내 배송 실증 결과가 아닙니다."
)
st.caption(
    f"지역: 서울 좌표 범위의 모의 영역 | 기간: {analysis.gps.timestamp.min().tz_convert('Asia/Seoul').date()}–{analysis.gps.timestamp.max().tz_convert('Asia/Seoul').date()} | 관측 단위: synthetic_vehicle_gps | seed=42"
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("동일 비교 후보", len(scores))
c2.metric("합성 GPS 관측", f"{len(analysis.gps):,}")
c3.metric("정차 Episode F1", f"{metrics['f1']:.3f}")
c4.metric(
    "정차시간 MAE",
    f"{metrics['matched_duration_mae_seconds']:.1f}초"
    if metrics["matched_duration_mae_seconds"] is not None
    else "매칭 없음",
)
research_tab, map_tab, compare_tab, stress_tab = st.tabs(
    ["연구 근거", "GIS 탐색", "후보 비교·다운로드", "민감도·실패 조건"]
)

with research_tab:
    st.subheader("무엇을 검증했는가")
    st.write(
        "정답이 알려진 합성 시나리오에서 정차 탐지를 검증하고, 같은 후보군에 세 모델을 적용해 선정 결과와 안정성을 비교합니다. 순위 변화는 정확도 향상의 증거가 아닙니다."
    )
    left, right = st.columns(2)
    with left:
        st.markdown("**평가모델**")
        st.latex(r"M=(z(T_{move})+z(T_{stop})+z(V))/3")
        st.latex(r"S=0.7z(P)+0.3z(POI),\quad I=\alpha M+(1-\alpha)S")
        st.caption(
            "z: 같은 후보군 min–max. 가중치는 가정이며 최적값이 아닙니다. 반복방문은 중복계상 진단을 위해 기본식에서 제외했습니다."
        )
        st.dataframe(
            table("model_comparison").drop(columns=["run_id"], errors="ignore"),
            hide_index=True,
        )
    with right:
        st.markdown("**정차 탐지 검증**")
        st.json(metrics)
        st.caption(
            "1:1 시간 IoU≥0.5 매칭. MAE는 매칭된 episode만 포함합니다. 미탐·오탐은 F1에 반영됩니다. 배송 정차와 긴 신호정차는 목적 정보 없이 구분할 수 없습니다."
        )
    st.info(
        "아래 보고서의 실험표는 기본 설정으로 실행한 고정 결과입니다. 왼쪽 설정 변경은 현재 지도·후보 점수·정차 검증에 적용되며 전체 강건성 실험을 다시 실행하지 않습니다."
    )
    report = ROOT / "reports/RESEARCH_RESULTS.md"
    if report.exists():
        st.download_button(
            "전체 실험보고서 다운로드",
            report.read_text(),
            file_name="RESEARCH_RESULTS.md",
            mime="text/markdown",
        )

with map_tab:
    st.subheader("이동경로 · 정차 · 격자 점수")
    vehicles = st.multiselect(
        "강조할 차량",
        sorted(analysis.gps.vehicle_id.unique()),
        default=sorted(analysis.gps.vehicle_id.unique())[:2],
    )
    st.caption(
        "경로는 선택 차량, 격자 점수는 전체 차량입니다. 배경 타일 없이 실제 좌표 배치로 표시하며 도로 맵매칭은 하지 않습니다."
    )
    col = {
        "Integrated": "integrated_score",
        "Static-only": "static_score",
        "Mobility-only": "mobility_score",
    }[model]
    mapdata = scores.copy()
    mapdata["color"] = [
        [int(40 + 210 * x), int(170 - 110 * x), int(185 - 135 * x), 165]
        for x in mapdata[col].fillna(0)
    ]
    mapdata["display_score"] = mapdata[col].round(4)
    layers = [
        pdk.Layer(
            "PolygonLayer",
            mapdata,
            get_polygon="polygon",
            get_fill_color="color",
            get_line_color=[235, 240, 250],
            line_width_min_pixels=1,
            pickable=True,
        )
    ]
    paths = []
    for v, g in analysis.gps[analysis.gps.vehicle_id.isin(vehicles)].groupby(
        "vehicle_id"
    ):
        segment = (~g.interval_valid).cumsum()
        for _, part in g.groupby(segment):
            if len(part) > 1:
                paths.append(
                    {
                        "path": part[["longitude", "latitude"]].to_numpy().tolist(),
                        "vehicle_id": v,
                    }
                )
    if paths:
        layers.append(
            pdk.Layer(
                "PathLayer",
                paths,
                get_path="path",
                get_color=[33, 72, 124],
                width_min_pixels=2,
                pickable=True,
            )
        )
    stopdata = analysis.stops[analysis.stops.vehicle_id.isin(vehicles)].copy()
    stopdata["dwell_minutes"] = stopdata.dwell_seconds / 60
    if len(stopdata):
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                stopdata,
                get_position="[longitude,latitude]",
                get_radius=12,
                get_fill_color=[220, 92, 51],
                pickable=True,
            )
        )
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            map_style=None,
            initial_view_state=pdk.ViewState(
                latitude=float(analysis.gps.latitude.mean()),
                longitude=float(analysis.gps.longitude.mean()),
                zoom=13.5,
            ),
            tooltip={
                "text": "Grid: {grid_id}\nScore: {display_score}\nVehicle: {vehicle_id}\nSYNTHETIC"
            },
        )
    )
    hourly = (
        analysis.detail.groupby("hour")[["moving_seconds", "stop_seconds"]].sum() / 60
    )
    st.subheader("시간대별 차량 활동 (Asia/Seoul, 분)")
    st.bar_chart(hourly)

with compare_tab:
    st.subheader("동일 후보군의 세 모델")
    columns = [
        "grid_id",
        "static_score",
        "mobility_score",
        "integrated_score",
        "legacy_integrated_score",
        "moving_seconds",
        "stop_seconds",
        "visit_frequency",
        "repeat_visits",
        "observation_type",
    ]
    ranked = scores.sort_values(
        ["integrated_score", "grid_id"], ascending=[False, True]
    )
    st.dataframe(ranked[columns], hide_index=True)
    chosen = st.multiselect(
        "비교할 후보", ranked.grid_id.tolist(), default=ranked.grid_id.head(5).tolist()
    )
    st.bar_chart(
        scores[scores.grid_id.isin(chosen)].set_index("grid_id")[
            ["static_score", "mobility_score", "integrated_score"]
        ]
    )
    st.download_button(
        "현재 후보 점수 CSV · synthetic",
        ranked.drop(columns="polygon").to_csv(index=False),
        file_name="candidate_scores_synthetic.csv",
        mime="text/csv",
    )
    st.caption(
        "최소값·최대값·가중치가 달라지면 점수도 달라집니다. 다른 실행의 점수를 절대적 가치로 비교하지 마세요."
    )

with stress_tab:
    st.subheader("기본 설정으로 실행한 민감도·강건성 결과")
    for name, title in [
        ("weight_sensitivity", "가중치 변화"),
        ("selection_stability", "차량 단위 bootstrap 선정확률"),
        ("holdout", "분리 검증과 미실행 항목"),
        ("robustness", "GPS 노이즈·표본주기·표본 규모"),
    ]:
        with st.expander(title, expanded=name == "weight_sensitivity"):
            d = table(name)
            if len(d):
                st.dataframe(d.drop(columns="run_id", errors="ignore"), hide_index=True)
            else:
                st.info(
                    "저장된 실험 결과가 없습니다. README의 research 명령으로 생성할 수 있습니다."
                )
    p = ROOT / "reports/figures/noise_sampling_robustness.png"
    if p.exists():
        st.image(str(p), caption="synthetic · 탐지 실패도 포함한 실험 결과")
st.caption(
    "Transit OOH Research Lab · 원본 자료, 데이터 출처, 코드·테스트와 실험 해시를 함께 보존합니다."
)
