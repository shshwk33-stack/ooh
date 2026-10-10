# Transit OOH · View-T 고도화 인수 보고서

검증일: 2026-10-10. 캡스톤디자인2 / 산업공학회 대학생 경진대회.

**기존 GPS·Mobility/Spatial·GIS 연구 코드를 유지한 확장 구현을 완료하고 실행했다. View-T 공식 실자료 확보와 실제 국내 밀크런 GPS·독립 결과지표의 외부 실증은 미완료다.** View-T의 API/승인 절차는 환경 프록시 차단 때문에 확인하지 못했다. 이 상태를 성공으로 표시하거나 합성 자료로 대체하지 않았다.

## 구현과 미완료 범위

| 요청 | 구현·실행한 내용 | 범위/남은 사항 |
|---|---|---|
| View-T 세 도구 연동 | 인구 O/D, 차량 대표경로, 인구 통행구간의 Excel·CSV 어댑터, 원본 열 매핑 | 프로젝트 표준 계약. 공식 원본 형식/실자료/API는 미확보 |
| 자치구 선택 | 마포구 기본, 서울 25개 자치구 전환, 업로드 구역 코드 일치 검사 | 예제 위치는 자치구 중심 부근의 합성 거점. 공식 경계의 포함 여부 인증은 없음 |
| 가상 밀크런 | 입력 경로의 방향별 인접관계에 따른 거점 순회, 반복 회차·가정 속도·정차 조정 | 구역 중심 간 개략선. 도로 최단경로/실측 배송차량 GPS 아님 |
| 가중치 | 기본 50:50, 기존 60:40, 사용자 0~100%; 점수·지도·순위·Top-5/10·안정성 재계산 | 60:40 포함 어느 값도 최적이라고 검증하지 않음 |
| 시공간 정합성 | 자치구·공간 코드 버전·단위·조사연도·기간·시간대·POI 유효기간·누락/중복 검사 | 서로 다른 공간 단위의 자동 재배분은 하지 않음 |
| A/B/C 비교 | Spearman/Kendall, Top-5/10 중복률, 가중치별 순위, paired-day Bootstrap, 시간 holdout | 순위 변화/안정성은 광고효과 정확도 향상이 아님 |
| GIS UI | 자치구·자료·날짜/시간·가중치·모델·밀크런 조작, 출처 표시, CSV/Excel 다운로드 | AppTest와 HTTP 실행 확인. 브라우저 WebGL 스크린샷 검증은 미실행 |
| 도로 속도·화물차·전체 네트워크 | 확보에 필요한 필드와 결합 조건 문서화 | 공식 제공 여부 미확인, 별도 어댑터 미구현. 미확인 차종을 화물차로 가정하지 않음 |

세부 계약과 실제 막힌 URL: [VIEWT_DATA_GUIDE.md](VIEWT_DATA_GUIDE.md). 현재 필요한 것은 확인되지 않은 임의의 API 키가 아니라 **동기간의 공식 파일과 공간 코드 대응표·출처/단위 정의** 또는 공식 API 문서/이용승인이다. 정확한 신청 하위 경로는 확인하지 못했음을 명시한다.

## 실제 산출된 연구 결과

### GPS 엔진 — 합성 물리 정차 검증

실행 `20261010T083355097582Z_seed42`. 6대×6일, GPS 4,167점, GT 248개 물리 정차, 탐지 214개, TP 214 / FP 0 / FN 34. **F1 0.9264**, precision 1.0000, recall 0.8629, 매칭된 정차시간 MAE 8.69초. 실제 배송 목적 분류나 서울 실증 수치가 아니다.

이전 쉬운 합성 경로의 F1 0.9885와 직접적인 성능 향상 비교를 하지 않는다. 이번 기본 경로는 짧은 배송과 긴 신호 정차를 포함해 난도가 달라졌다. 경로 생성 seed까지 분리한 72회 paired 비교 결과:

| 조건 | anchor 평균 F1 | robust 평균 F1 |
|---|---:|---:|
| 5m 노이즈, 정확도 제공 | 0.893 | 0.908 |
| 15m 상관 노이즈, 정확도 제공 | 0.545 | 0.848 |
| 35m 상관 노이즈, 정확도 누락 | 0.100 | 0.244 |
| 35m 상관 노이즈, 정확도 과신 | 0.100 | 0.244 |

**정확도를 모르는 큰 노이즈에서는 여전히 실패한다.** 합성 노이즈 분포의 개선을 실차 강건성으로 일반화하지 않는다. 300초 표본에서도 일부 정차를 탐지하지만 짧은 정차는 놓친다.

근거: [GPS 보고서](../reports/RESEARCH_RESULTS.md), [72회 원표](../reports/tables/detector_benchmark.csv), [비교 그래프](../reports/revision/heldout_detector_comparison.png).

### 마포구 파일 연동 예제 — 전부 synthetic

2025-10-01~14, 16개 가상 후보. 인구·차량 통행·POI 모두 합성이다. 기본 50:50에서 A(Spatial)–C(Integrated) Spearman **0.5794**, Top-5 중복률 **0.60**, Top-10 **0.70**. 200회 paired-day Bootstrap에서 Top-5 선정확률 80% 이상인 후보는 **4개**다. 이 값은 시스템 기능과 조건부 안정성을 보여주며 실제 최적 입지의 증거가 아니다.

근거: [마포구 예제 결과](../reports/viewt/RESULTS.md), [표 10종](../reports/viewt/tables/), [발표용 PNG/SVG 4쌍](../reports/viewt/figures/), [입력·코드·산출물 해시](../reports/viewt/manifest.json).

GPS 합성·공개자료 29개 최신 CSV, 기존 공개 자료 그림을 포함한 PNG/SVG 10쌍, 추가 held-out 비교 그림 1쌍과 요약표도 제공한다. 서로 다른 연구의 순위나 표본수를 합치지 않는다.

### 기존 실제 공개 자료 — 유지, 별도 분석

LaDe Jilin 기사 작업 이벤트 31,415건·57명, Amazon 방문지/순서 3,052경로, 서울 일부 OSM amenity node 601개를 기존 관측 단위대로 유지했다. 국내 마포구 합성 예제와 교차 결합하지 않았다. LaDe는 차량 연속 GPS가 아니고 Amazon은 도착시각·실측 체류시간이 없으며 OSM은 인구 이동량이 아니다. 출처·다운로드 코드·원본 체크섬은 [DATA_SOURCES.md](DATA_SOURCES.md)를 참조한다. 실제 원본/개별 위치 기록과 인증키는 Git·검수 ZIP에 포함하지 않는다.

## 리뷰 반영과 검사 증거

| 항목 | 결과/수정 | 근거 |
|---|---|---|
| 외부 Parquet timestamp | ns/us/ms/s에서 경과시간 계산 일관성 | test_revision.py |
| 단일 GPS spike | 고립된 이상점 제거 뒤 간격 재계산, 다음 정상점 보존 | 같은 위치 600초 정차/방문 1회 회귀검사 |
| 노이즈·드문 관측 | anchor 비교 보존, median 중심/정확도 범위의 robust 탐지, 적응형 간격 상한 | 57조건 + held-out 72조건 |
| 통계 테스트 | 훈련 정규화 재사용, 실제 복원추출/순열, UTC 대신 현지 시간, IoU 경계, 비교 기준 분리 | [pytest XML](../reports/runs/tests.xml) |
| 전체 pytest | **68 passed, 1 xfailed, 0 failed** | 원본 점 수×5분 오류만 strict xfail |
| 의도적 연구 오류 삽입 | **선언한 10개 모두 검출**, import/수집 오류로 통과시킨 사례 없음 | [mutation_checks.json](../reports/runs/mutation_checks.json) |
| 수치 재현·산출물 무결성 | 최종/직전 실행 표 29개 정확 일치(run_id 제외), 현재 소스 및 산출물 해시 일치 | [revision_reproducibility.json](../reports/runs/revision_reproducibility.json) |
| 새 환경 | 독립 venv 설치→GPS quick→View-T→AppTest 통과, 48.38초 | [clean_smoke.json](../reports/runs/clean_smoke.json) |
| 서버 | health/root 모두 HTTP 200, 앱 조작 검사는 별도 AppTest 통과 | [server_check.json](../reports/runs/server_check.json) |
| 정적 검사 | Ruff E4/E7/E9/F/I/UP/B/RUF, format 통과 | pyproject.toml / CI |
| 시각 검수 | 모델 기여도 범례 중첩 개선, 노이즈 heatmap 공백 개선, 주요 PNG 직접 확인 | reports/figures 및 reports/viewt/figures |
| 원본 감사 | 165분 스케줄 합계를 상수 대신 원본 add_stop 호출 AST에서 계산 | scripts/audit_legacy.py |

변이 검사는 선택한 과학적 계약 10개에 대한 결과이며 전체 프로그램의 100% 변이 커버리지를 뜻하지 않는다. 기존 결과·실패는 실행 ID별 표에 보존한다. `reproducibility.json` 등 과거 검사 파일은 그 파일에 적힌 실행 범위의 역사적 증거이며 이번 모든 수정의 재현 검사로 재사용하지 않는다.

## 실행과 검수

```bash
bash scripts/setup.sh
bash scripts/run.sh transit-ooh research
bash scripts/run.sh python scripts/revision_summary.py
bash scripts/run.sh transit-ooh viewt --demo --weight 0.5
bash scripts/run.sh pytest -q --junitxml=reports/runs/tests.xml
bash scripts/run.sh python scripts/mutation_checks.py
bash scripts/run.sh python scripts/clean_smoke.py
bash scripts/run.sh ruff check src app tests scripts
bash scripts/run.sh streamlit run app/streamlit_app.py
```

`research`는 최신 산출물을 다시 쓰며 원본 없는 공개 자료는 not_acquired로 기록한다. 전체 소스·참고자료는 GitHub 작업 브랜치 ZIP, 검수에 필요한 코드·테스트·결과 중심 묶음은 `deliverables/Transit_OOH_ViewT_review.zip`로 제공한다. 검수 ZIP은 큰 발표 PPTX/PDF/DOCX와 실제 원본 데이터를 제외하며 원본 노트북·마스터 지시서·리뷰 텍스트는 포함한다.

클라우드 설정은 `cloud-environment-onboarding:setup`에 따라 설치·기동 지침과 검증 내용을 **초안**으로 저장했다. 원래 main이 ZIP만 가진 버전이면 작업 브랜치 소스가 없으므로 환경 게시 시 저장소 ref도 검토해야 한다. 초안 저장은 환경 게시나 새 작업의 복원 검증이 아니다.

## 미완료 사항

- View-T 공식 페이지/API/승인 절차 확인, 실제 파일 획득 및 그 파일에 대한 원본 형식 어댑터 검증.
- 동기간·공통 공간구역의 실제 마포구 인구/교통/POI 결합 실증.
- 실제 도로 네트워크·화물차 구분을 이용한 도로 경로 분석.
- 동의받은 밀크런 차량 GPS와 독립 현장 관측으로 외부 타당성 검증.
- 최적 가중치, 실제 광고 노출/주목도/성과, 계절·지역 일반화 검증.

[독립 검증 설계](VALIDATION_DESIGN.md)에 점수와 별개로 관측할 기준·표본 분리·군집 불확실성·해석 한계를 구체화했다. 외부 자료가 없다는 이유로 이 항목들의 결과를 만들어 넣지 않았다.
