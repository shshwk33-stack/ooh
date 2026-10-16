"""Real external evidence must be entered; the app supplies no mock outcomes."""

import hashlib
import json
from datetime import date, datetime, timedelta
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from transit_ooh.field_validation import (
    evaluate_campaign,
    freeze_campaign,
    read_campaign,
)


def render():
    st.subheader("독립 현장 검증 · 모델 고정과 관측 결과 비교")
    st.info(
        "현장 관측은 아직 수행하지 않았습니다. 이 화면은 실제 관측을 위한 도구입니다. "
        "결과를 보기 전에 후보·점수·가중치·관측 일정을 고정하고, 별도로 수집한 통과 계수와 비교합니다."
    )
    freeze, evaluate = st.tabs(["1. 현장 관측 준비", "2. 수집 후 모델 평가"])
    with freeze:
        st.markdown(
            "검토한 **관측 지점 10곳 이상**의 CSV를 입력하세요. 필요한 열: "
            "`grid_id, longitude, latitude, static_score, mobility_score`. "
            "좌표는 실제 관측 지점이어야 하며 구역 중심을 자동으로 관측 지점으로 바꾸지 않습니다."
        )
        predictions = st.file_uploader(
            "고정할 실제 자료 기반 점수 CSV", type=["csv"], key="field_predictions"
        )
        a, b = st.columns(2)
        source = a.text_input("입력 자료 출처와 점수 산식", key="field_source")
        support = b.text_input("후보 공간 단위·버전", key="field_support")
        mapping = st.text_area(
            "후보 구역과 실제 관측 지점의 대응을 어떻게 검토했나요?",
            key="field_mapping",
        )
        independent = st.text_area(
            "모델과 독립적으로 관측할 방법·점수 비공개 절차", key="field_independence"
        )
        kind = a.selectbox(
            "점수 입력 자료 분류",
            ["estimated", "public_observed", "mixed_observed_estimated"],
            key="field_kind",
        )
        target = b.selectbox(
            "독립 관측 대상",
            ["manual_vehicle_passages", "manual_pedestrian_passages"],
            format_func=lambda x: (
                "차량 직접 통과 계수"
                if x == "manual_vehicle_passages"
                else "보행자 직접 통과 계수"
            ),
            key="field_target",
        )
        training_end = a.date_input(
            "모델에 사용한 마지막 자료 날짜",
            value=date(2024, 12, 31),
            key="field_training_end",
        )
        alpha = b.slider("고정할 Mobility 비중 (%)", 0, 100, 50, key="field_alpha")
        tomorrow = datetime.now(ZoneInfo("Asia/Seoul")).date() + timedelta(days=1)
        dates = st.text_input(
            "관측 예정일 · 쉼표로 구분, 5일 이상",
            placeholder=f"{tomorrow.isoformat()}, ...",
            key="field_dates",
        )
        time = a.text_input(
            "모든 지점의 관측 시작 시각 (한국시간)", value="12:00", key="field_time"
        )
        duration = b.number_input(
            "지점당 관측 시간 (분)", 1, 120, 15, key="field_duration"
        )
        st.caption(
            "모든 후보를 동일 날짜·시간에 관측하는 균형 설계입니다. 10곳·5일은 도구의 최소 조건이며 검정력 보장은 아닙니다. "
            "인력·계절·입력 연도와 현장 시점의 차이를 연구 설계에서 검토하세요."
        )
        if st.button("점수·일정 고정 패키지 만들기", key="field_freeze"):
            try:
                if predictions is None:
                    raise ValueError("검토한 점수 파일이 필요합니다")
                raw = predictions.getvalue()
                scores = pd.read_csv(BytesIO(raw), dtype={"grid_id": str})
                meta = {
                    "spatial_support_id": support,
                    "training_end_date": training_end.isoformat(),
                    "prediction_source": source,
                    "prediction_observation_type": kind,
                    "input_sha256": hashlib.sha256(raw).hexdigest(),
                    "target": target,
                    "site_mapping_review": mapping,
                    "independence_plan": independent,
                }
                package = freeze_campaign(
                    scores,
                    meta,
                    [x.strip() for x in dates.split(",") if x.strip()],
                    time,
                    int(duration),
                    alpha / 100,
                )
                st.session_state["field_frozen_package"] = package
                st.success(
                    "고정 패키지를 만들었습니다. 관측자에게는 observations_BLIND.csv만 전달하세요."
                )
            except (ValueError, KeyError, TypeError) as exc:
                st.error(f"고정 실패: {exc}")
        if "field_frozen_package" in st.session_state:
            package = st.session_state["field_frozen_package"]
            protocol, _, _ = read_campaign(package)
            st.caption(
                f"다운로드 대상은 {protocol['frozen_at_utc']}에 고정한 패키지입니다. 위 설정 변경은 다시 만들기를 눌러야 반영됩니다."
            )
            st.download_button(
                "고정 프로토콜 + 관측자용 CSV 다운로드",
                package,
                "Transit_OOH_Field_Campaign.zip",
                "application/zip",
                key="field_download",
            )
    with evaluate:
        campaign = st.file_uploader(
            "관측 전에 고정한 캠페인 ZIP", type=["zip"], key="field_campaign"
        )
        observations = st.file_uploader(
            "실제 계수를 입력한 observations_BLIND.csv",
            type=["csv"],
            key="field_observations",
        )
        declared = st.checkbox(
            "실제로 관측한 계수이며 모델 입력이나 예측값을 정답으로 옮기지 않았음을 확인",
            key="field_attestation",
        )
        st.caption(
            "독립 수집 여부는 사용자 선언이며 앱이 인증하지 않습니다. 결측·미래 관측·일정 변경·중복 세션은 평가를 중단합니다. "
            "현장 계수는 광고를 본 사람 수가 아닙니다."
        )
        input_key = (
            hashlib.sha256(campaign.getvalue() + observations.getvalue()).hexdigest()
            if campaign is not None and observations is not None and declared
            else None
        )
        if st.button("고정된 Model A/B/C 평가", key="field_evaluate"):
            try:
                if campaign is None or observations is None or not declared:
                    raise ValueError("캠페인·실제 관측 파일과 수집 확인이 필요합니다")
                obs = pd.read_csv(
                    BytesIO(observations.getvalue()),
                    dtype={"grid_id": str, "observer_id": str},
                )
                with st.spinner("동일 날짜·지점 재표집으로 모델 차이를 비교 중…"):
                    result = evaluate_campaign(campaign.getvalue(), obs)
                st.session_state["field_evaluated"] = (input_key, result)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                st.session_state.pop("field_evaluated", None)
                st.error(f"평가 중단: {exc}")
        saved = st.session_state.get("field_evaluated")
        if saved is not None and input_key is not None and saved[0] == input_key:
            result = saved[1]
            st.dataframe(result["model_metrics"], hide_index=True)
            st.dataframe(result["paired_differences"], hide_index=True)
            st.caption(
                "C−A가 주 비교입니다. paired_days는 선정한 지점을 고정하고 날짜를, crossed는 지점과 날짜를 각각 함께 재표집합니다. "
                "반복 관측 행 수를 독립 지점 수로 세지 않습니다. 구간은 소표본·조건부 분석이며 자동 성능 향상 판정은 하지 않습니다."
            )
            buffer = BytesIO()
            with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
                for name, value in result.items():
                    if isinstance(value, pd.DataFrame):
                        archive.writestr(
                            name + ".csv", value.to_csv(index=False).encode("utf-8-sig")
                        )
                    else:
                        archive.writestr(
                            name + ".json",
                            json.dumps(value, ensure_ascii=False, indent=2),
                        )
            st.download_button(
                "현장 검증 결과·재표집 기록 ZIP",
                buffer.getvalue(),
                "Transit_OOH_Field_Results.zip",
                "application/zip",
                key="field_results",
            )
