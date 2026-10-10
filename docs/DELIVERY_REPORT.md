# Transit OOH 최종 인수 보고서

검증일: 2026-10-10. 대상: 정보통신공학 캡스톤디자인2 / 산업공학회 대학생 경진대회.

**P0–P7의 실행 가능한 분석·실험·보고서·GIS 소프트웨어를 구현하고 검증했다. 실제 연속 배송차량 GPS와 동기간 공간정보를 결합한 외부 실증은 아직 완료하지 못했다.** 이 차이를 데이터·화면·보고서에 명시했다. 원본 발표자료의 과거 주장과 이번에 직접 실행한 결과를 구분한다.

## 인수 체크리스트

| 항목 | 상태 | 근거 |
|---|---|---|
| 1차·2차 자료의 목표 보존 | 완료 | [자료 감사](SOURCE_AUDIT.md); PDF/PPTX 각 12쪽, DOCX·노트북 전체 분석 |
| 원본 PoC 감사·이상 사례 재현 | 완료 | 원본 4개 ZIP 바이트 일치, [원본 무결성](../reports/runs/reference_integrity.json); 깨끗한 커널 14/14셀 성공; 165→190분 편향 재현 |
| 공개 실측 데이터 획득 | 일부 완료 | LaDe-D Jilin, Amazon 평가 경로·순서, 서울 OSM 확보. 연속 차량 GPS 미확보 |
| 데이터 출처·합성/실측 구분 | 완료 | [출처](DATA_SOURCES.md), [데이터 계약](DATA_CONTRACT.md); 서로 다른 도시·기간·관측단위의 자료 분리 |
| GPS/정차/격자 알고리즘 검증 | 완료, 합성 GT 범위 | 실제 시간차, UTM 미터격자, 연결 중단, 1:1 episode 평가, 시간 보존 테스트 |
| Static/Mobility/Integrated 비교 | 완료, 합성 동일 후보군 | 기본 64개 후보, 고정 레거시 별도 비교; 외부 예측력 개선 미입증 |
| 민감도·강건성 | 완료 | 57개 표본설계 조건, 11개 가중치, 9개 탐지 설정, 5개 격자/경계 조건, ablation·placebo·bootstrap·holdout |
| 연구용 표·그림 자동 산출 | 완료 | CSV 28개, PNG 10개 + 동일 그림 SVG 10개, 실행별 표·manifest·GeoJSON |
| Streamlit 실제 구동 | 완료 | 서버 health/root HTTP 200, 실제 AppTest 화면·격자·가중치·자료 전환 통과 |
| 자동 테스트·재현 | 완료 | **38 passed, 1 xfailed, 0 failed**; 원본 오류만 strict xfail; 독립 환경 smoke 통과 |
| 입증하지 못한 주장·차기 검증 | 명시 완료 | 광고효과·외부 타당성·최적 가중치·계절 일반화는 미검증 |

## 실제 실행 결과

최종 전체 실행: `20261010T023347713830Z_seed42`. [자동 실험보고서](../reports/RESEARCH_RESULTS.md), [manifest](../reports/runs/20261010T023347713830Z_seed42/manifest.json).

### 합성 GT 연구

6대 × 6일, GPS 6,094점, 정답 정차 216개. 탐지 219개 중 TP 215, FP 4, FN 1. Precision 0.9817, recall 0.9954, **F1 0.9885**. 매칭된 정차의 시간 MAE **15.77초**, 전체 정차시간 오차 −49.5분. 매칭 실패가 MAE에서 제외되므로 F1과 함께 봐야 한다.

정적모델과 통합모델의 Spearman은 0.4016, Top-5 overlap은 0.2였다. 이것은 가중치에 따라 후보가 달라지는 결과이며 통합모델의 정확도 향상이 아니다. 차량 cluster bootstrap 100회에서 선정확률 0.8 이상인 후보는 2개였다. 합성 차량이 6대뿐이므로 도시 전체의 모집단 신뢰구간으로 해석할 수 없다.

위치 노이즈 표준편차 15m에서 F1은 30초 수집 시 약 0.22, 120초 수집 시 약 0.44로 낮아졌다. 300초 주기는 최대 연결 간격 180초를 초과해 탐지를 놓쳤다. 현 탐지기가 모든 GPS 환경에서 강건하다고 주장할 수 없다. 이러한 실패도 [강건성 표](../reports/tables/robustness.csv)와 [그림](../reports/figures/noise_sampling_robustness.png)에 포함했다.

### 실제 공개 자료 연구

- **LaDe-D Jilin:** 31,415개 기사 배송 이벤트, 57명, 163개 기록일. 제공 AOI 키의 356개 후보를 분석했다. 인접 월 Top-10 overlap 0.2–0.9, 기사 bootstrap 200회에서 선정확률 0.8 이상인 후보 0개. 이는 관측 패널의 기간·기사 구성 민감성이다. 작업 수를 차량 방문횟수나 체류시간으로 해석하지 않는다.
- **Amazon LMRRC:** 실제 파일 3,052개 경로, 433,231개 방문지 레코드(배송지 430,179개), 18개 station. 방문순서 coverage 1.0. 제공자가 교란한 방문지 좌표이며 도착시각·정차시간·연속 GPS는 없다. 카탈로그의 3,072개와 배포 파일 차이를 그대로 기록했다.
- **서울 OSM:** 현재 작은 bbox의 amenity node 601개, 29종, 200m 격자 12개. © OpenStreetMap contributors, ODbL-1.0. 건물·way·relation 전체를 수집한 POI 조사나 유동인구 자료가 아니다.

실측 원본은 현재 `data/raw/`에 있으며 Git/전달 ZIP에서 제외한다. 공개 집계 결과와 다운로드 코드·출처·검증 해시는 포함한다. LaDe 라이선스 메타데이터 충돌은 [출처 문서](DATA_SOURCES.md)에 기록하고 더 제한적인 비상업 연구 조건으로 취급했다. 미래 OSM 다운로드는 이번 지도 스냅샷과 수치가 다를 수 있다.

## 검사 증거와 오류 수정

| 검사 | 실제 결과 | 기록 |
|---|---|---|
| 원본 깨끗한 커널 | 코드 14셀 성공, 저장된 NameError는 재현 안 됨 | [legacy_kernel.json](../reports/runs/legacy_kernel.json) |
| 전체 pytest | 38 통과, 원본 편향 회귀 1 예상 실패 | [tests.xml](../reports/runs/tests.xml) |
| 별도 venv, 원본·Git 없는 디렉터리 | 설치 → quick 실험 → 그림 → AppTest 성공, 33.08초 | [clean_smoke.json](../reports/runs/clean_smoke.json) |
| 수치 재현 | 이전 전체 실행의 합성 결과표 19개와 수치·열이 정확히 일치 | [reproducibility.json](../reports/runs/reproducibility.json) |
| 코드/출력 무결성 | 소스·설정·lock·앱 21개 hash, manifest 산출물 확인 | 최종 manifest 및 재현 기록 |
| 앱 서버 | health `ok`, root Streamlit HTML, 둘 다 HTTP 200 | [server_check.json](../reports/runs/server_check.json) |
| 정적 검사 | Ruff E9/F 및 format 검사 통과 | README 명령으로 재검사 가능 |
| 원격 GitHub Actions | 구성 파일 작성, 원격 실행은 미실행 | [ci.yml](../.github/workflows/ci.yml) |

수정한 문제: pandas/NumPy 버전 조합 경고를 호환 범위로 고정; 드문 샘플에서 빈 활동표 dtype 때문에 상관 계산이 실패하는 문제 수정; 앱 테스트의 경로 해석 수정; 현재 입력이 없는 공개 자료의 과거 결과표가 재사용되는 문제 차단; 새 모델 가중치가 bootstrap/holdout에도 적용되도록 일관성 보장; 고정 레거시 가중치는 별도 유지. 테스트를 삭제하거나 새로운 분석엔진의 실패를 xfail로 숨기지 않았다.

## 재현 명령

Linux/Python 3.12 및 uv 기준, 저장소 루트에서:

```bash
bash scripts/setup.sh
bash scripts/run.sh transit-ooh fetch-public
bash scripts/run.sh transit-ooh research
bash scripts/run.sh transit-ooh validate --gps data/synthetic/gps.parquet
bash scripts/run.sh pytest -q --junitxml=reports/runs/tests.xml
bash scripts/run.sh python scripts/clean_smoke.py
bash scripts/run.sh ruff check src app tests scripts --select E9,F
bash scripts/run.sh ruff format --check src app tests scripts
bash scripts/run.sh streamlit run app/streamlit_app.py --server.headless true --server.port 8501
```

`fetch-public` 없이 합성 연구와 앱을 실행할 수 있다. 이때 없는 실측 원본은 `not_acquired`로 기록하며 최신 폴더의 해당 자동 생성 결과를 제거한다. 전달된 실행별 표는 유지한다. 연구 결과의 source hash는 실행 당시 실제 코드를 식별한다. manifest의 Git HEAD는 초기 저장소 커밋이며 `git_dirty=true`는 실행 시 새 소스가 아직 커밋되지 않았음을 정직하게 기록한 것이다.

## GitHub 반영용 구성

새 Python 패키지, 고정 의존성, CLI, 과학 실험, Streamlit, 테스트/CI, 출처·연구·인수 문서, 원본 참고자료, 생성된 공개 집계·합성 연구 결과를 포함한다. `.env`, 비밀키, 실측 원본/가공 개별 자료, 가상환경·캐시·감사용 대용량 임시 파일은 제외한다. 로컬 `feat/transit-ooh-research` 브랜치로 정리하며 원격 push나 배포는 수행하지 않는다.

클라우드 설정 초안에는 검증한 `install_script`와 앱 기동·건강검사·기능검사 `start_skill`을 저장했다. 기존 네트워크 설정은 유지했다. 이 저장은 환경 게시나 새 작업에서의 복원 검증이 아니다. 환경 설정 화면에서 검토·저장 후 게시해야 다음 환경에 적용된다.

## 남은 외부 검증과 차기 실험

1. 동의받은 국내 배송 **차량**의 연속 GPS, 차종·수집 간격·좌표계·시각 기준과 독립 정차 라벨을 확보한다.
2. 동일 지역·기간·공간 지지영역의 인구/POI를 확보하고, 관측되지 않은 도시 운영량을 0으로 해석하지 않는다.
3. 입력 가중합과 독립된 전문가 블라인드 평가 또는 실제 노출/주목도 자료로 정적모델 대비 증분 설명력을 검증한다.
4. 미사용 기간·지역·계절로 재평가하고, 충분한 차량 cluster를 확보한다. 현재 결과를 보고 튜닝한 모델은 새 표본으로 검증한다.
5. 학회 신규성의 체계적 선행연구 검토와 원본 자료 재배포 권한 검토를 수행한다.

현재 지지되는 성과는 **작동하는 재현 분석 시스템, 합성 GT에 대한 검증과 실패조건, 실제 공개 배송자료의 관측단위에 맞춘 선정 안정성 분석**이다. 실제 광고효과나 통합모델의 외부 정확도 개선은 아직 지지되지 않는다.
