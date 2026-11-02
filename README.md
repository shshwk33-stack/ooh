# TRANSIT ATLAS

**Transit OOH Analytics** — 배송차량 이동특성과 도시 공간정보를 결합한 위치가치 분석 대시보드 UI.

현재 **Phase 1 처리 결과가 대시보드에 연결**되어 있습니다. 기본 화면에서 실제 마포구·16개 행정동 경계, 합성 GPS 72개와 행정동별 공간집계, 자료 품질·출처·처리 이력을 확인합니다. 차량·날짜·시간대와 선택 행정동을 바꾸면 지도·KPI·표·상세가 함께 갱신됩니다. 기존 가중치 기능은 상단의 ‘예시 점수 비교’에 보존했습니다.

설치 없는 [연결형 대시보드 ZIP](https://github.com/shshwk33-stack/ooh/raw/refs/heads/transit-atlas-download/downloads/TRANSIT_ATLAS_CONNECTED_RUN.zip)을 내려받아 압축을 풀고 `TRANSIT_ATLAS_CONNECTED.html`을 Chrome/Edge에서 여세요. 코드·경계·GPS·폰트를 파일 안에 포함했으며 실행 서버는 필요하지 않습니다. [화면 연결 및 검증 보고](docs/research/DASHBOARD_INTEGRATION.md)를 참고하세요.

배송차량 GPS는 별도 합성 검증자료이며 실측 M/S/V·Bootstrap은 아직 산출하지 않았습니다. 다음 명령은 연결된 원본 처리 파이프라인을 재현합니다.

```sh
python -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r requirements-analysis.txt
.venv-analysis/bin/python scripts/run_phase1.py --output research_data/runs/phase1
.venv-analysis/bin/python -m unittest discover -s pipeline/tests -v
```

Windows에서는 `.venv-analysis/bin/python`을 `.venv-analysis\Scripts\python.exe`로 바꾸세요. [연구 파이프라인 실행·재현 방법](docs/research/README.md), [구현 진단](docs/research/PHASE0_DIAGNOSIS.md), [공개자료 출처](docs/research/PUBLIC_DATA_RESEARCH.md), [실행 결과와 후속 자료](docs/research/PHASE1_REPORT.md)를 참고하세요.

이전 UI 배포본은 [기존 실행용 ZIP](https://github.com/shshwk33-stack/ooh/raw/refs/heads/transit-atlas-download/downloads/TRANSIT_ATLAS_RUN.zip)에 보존되어 있습니다.

소스에서 개발 서버를 실행하려면:

```sh
npm ci
npm run dev
```

새 대시보드는 5180 포트에서 실행합니다. 기본 실행·빌드 진입점은 `dashboard/`입니다.

```sh
npm run build          # dist-dashboard/ 생성
npm run preview        # 운영용 빌드 확인 · 5181 포트
npm run test:dashboard # Chromium 화면·조작 검증 · 개발 서버 실행 필요
npm test               # 보존된 기존 점수 모델 테스트
npm run test:demo       # 별도 프런트엔드 DEMO 점수·순위 일관성
npm run test:connected  # 연결된 경계·합성 GPS·화면 조작 검증
```

[1536×1024 레퍼런스 화면](dashboard/docs/dashboard-1536.png) · [1440px 화면](dashboard/docs/dashboard-1440.png) · [실행 및 전체 설명](dashboard/README.md) · [기존 프로젝트 영향 보고](dashboard/docs/IMPACT_REPORT.md)

기본 워크스페이스는 검증된 파이프라인 결과를 읽습니다. 지도는 EPSG:5179 실제 공간 형상이며, 표시 GPS는 별도 SYNTHETIC 입력입니다. 예시 점수 비교 화면의 점수·순위·KPI와 개념도는 공통 DEMO 입력을 사용합니다. 두 화면을 실제 연구결과로 혼용하지 않습니다. 외부 API·DB는 연결하지 않았습니다.

기존 앱과 연구 코드는 루트 `src/`, `tests/`, `public/`에 보존했습니다. 기존 화면은 `npm run dev:legacy`, 기존 빌드는 `npm run build:legacy`로 실행합니다. 새 화면은 `dist-dashboard/`에 빌드되므로 기존 `dist/`도 덮어쓰지 않습니다.

이전 README는 [보존본](dashboard/docs/LEGACY_README.md)에 있습니다. 기존 연구 자료 맥락은 [PROJECT_CONTEXT](docs/PROJECT_CONTEXT.md)를 참고하세요.
