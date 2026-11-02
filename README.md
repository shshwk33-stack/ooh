# TRANSIT ATLAS

**Transit OOH Analytics** — 배송차량 이동특성과 도시 공간정보를 결합한 위치가치 분석 대시보드 UI.

현재 고도화는 **Phase 0 진단 + Phase 1 데이터 처리 기반**까지 진행했습니다. 기존 UI를 유지하면서 2013년 공개 경계(서울 25구·423동)를 검증하고 마포구·16개 행정동을 추출하는 Python 파이프라인을 추가했습니다. 배송차량 GPS는 별도 합성 검증자료이며, 실측 M/S/V·Bootstrap이나 대시보드 데이터 연결은 아직 수행하지 않았습니다.

```sh
python -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r requirements-analysis.txt
.venv-analysis/bin/python scripts/run_phase1.py --output research_data/runs/phase1
.venv-analysis/bin/python -m unittest discover -s pipeline/tests -v
```

Windows에서는 `.venv-analysis/bin/python`을 `.venv-analysis\Scripts\python.exe`로 바꾸세요. [연구 파이프라인 실행·재현 방법](docs/research/README.md), [구현 진단](docs/research/PHASE0_DIAGNOSIS.md), [공개자료 출처](docs/research/PUBLIC_DATA_RESEARCH.md), [실행 결과와 후속 자료](docs/research/PHASE1_REPORT.md)를 참고하세요.

기존 UI만 설치 없이 실행하려면 [실행용 ZIP](https://github.com/shshwk33-stack/ooh/raw/refs/heads/transit-atlas-download/downloads/TRANSIT_ATLAS_RUN.zip)의 압축을 풀고 `TRANSIT_ATLAS.html`을 Chrome/Edge에서 여세요. Python 연구 파이프라인은 위 명령으로 별도 실행합니다.

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
```

[1536×1024 레퍼런스 화면](dashboard/docs/dashboard-1536.png) · [1440px 화면](dashboard/docs/dashboard-1440.png) · [실행 및 전체 설명](dashboard/README.md) · [기존 프로젝트 영향 보고](dashboard/docs/IMPACT_REPORT.md)

가중치에 따른 점수·순위·KPI가 공통 DEMO 샘플에서 갱신됩니다. 기존 화면 수치는 DEMO이며, 지도는 직접 제작한 디자인용 개념도입니다. 새 Python 파이프라인은 분리되어 있으며 기존 UI·API·데이터베이스와 연결하지 않았습니다.

기존 앱과 연구 코드는 루트 `src/`, `tests/`, `public/`에 보존했습니다. 기존 화면은 `npm run dev:legacy`, 기존 빌드는 `npm run build:legacy`로 실행합니다. 새 화면은 `dist-dashboard/`에 빌드되므로 기존 `dist/`도 덮어쓰지 않습니다.

이전 README는 [보존본](dashboard/docs/LEGACY_README.md)에 있습니다. 기존 연구 자료 맥락은 [PROJECT_CONTEXT](docs/PROJECT_CONTEXT.md)를 참고하세요.
