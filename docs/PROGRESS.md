# 진행 기록

## P0 진행 중
- 패키지 4개 원본 보존, PDF/PPTX 12쪽씩 이미지 열람, DOCX 전체·IPYNB 전체 소스/저장 출력 확인.
- SOURCE_AUDIT.md와 RESEARCH_PROTOCOL.md 작성.
- Python 패키지 구조 및 uv.lock 생성, `UV_CACHE_DIR=/workspace/.cache/uv uv sync` 성공.
- 공개 데이터 공식 문서 조사 중. 일부 도메인은 프록시 403으로 접근 실패. 성공으로 간주하지 않음.
- 다음: 깨끗한 커널 원본 재실행, 실제 데이터 확보, 분석엔진·자동 테스트.

## P0–P4 완료 및 P5–P7 진행
- 깨끗한 커널 원본 14셀 성공. 165→190분, MOVE 8점 오분류, 시드별 순위 변화 재현.
- 자료 출처·CRS·timezone·관측단위 계약, metric grid·episode·구간 시간보존·정규화·3개 모델·레거시 구현.
- 원본 회귀 xfail 1개와 일반 엔진 테스트 30개 실행 성공. NumPy 2.5/Pandas 2.3 조합 경고를 진단해 NumPy<2.4로 고정한 후 경고 제거.
- sparse sampling에서 빈 활동표의 dtype 때문에 순위 상관이 실패한 문제 수정 및 회귀 테스트 추가.
- 실제 LaDe Jilin 31,415행 전체·Amazon 3,052경로·OSM node601개 확보. 라벨/지리/기간을 구분해 기술통계 및 실제 AOI 월별/기사bootstrap 추가.
- 전체 합성 연구: GPS6094, GT216, 탐지219, TP215/FP4/FN1. 57강건성·11가중치·9탐지기·5격자조건, 100 bootstrap/100 placebo 실행.
- Streamlit 실제 AppTest 초기 화면 및 격자/가중치/실측 전환 성공. AppTest 상대 경로 해석 변경에 따른 테스트 경로 오류 수정.
- 다음: 최종 문서·클린 환경 smoke·전체 테스트·서버 HTTP 검증·Git 전달 정리. 아직 연속 실배송차량 GPS/독립 광고 라벨은 미확보이며 통합 실측 외부 검증은 보류.

## P5–P7 최종 검증 완료 (2026-10-10)

- 전체 연구 실행 `20261010T023347713830Z_seed42` 완료. CSV 28개, PNG/SVG 각각 10개, 자동 연구보고서·GeoJSON·해시 manifest 생성. 공개 자료 표도 실행별 보존.
- 이전 실행과 합성 수치표 19개 완전 일치; 코드/설정/lock/앱 21개 hash와 결과물 검증.
- 최종 pytest **38 passed, 1 xfailed, 0 failed**. xfail은 보존된 원본의 점 수×5분 오류만 해당.
- 새 venv·원본/Git 없는 임시 디렉터리에서 설치부터 연구/그림/앱까지 smoke 통과 (33.08초).
- 서버 HTTP health/root 200 및 AppTest 설정 변경·실측/합성 전환 통과.
- 원본이 없는 새 실행에서 예전 공개 결과표가 남는 문제를 차단하고 회귀 테스트 추가.
- 레거시 기준 가중치는 고정하고 새 모델의 설정 가중치가 bootstrap/holdout/ablation/placebo에 일관되게 전달되도록 검증.
- 원본 PDF/PPTX/DOCX/IPYNB 4개 모두 업로드 ZIP과 바이트 일치 확인.
- 인수보고서 `docs/DELIVERY_REPORT.md` 작성. 설치/시작 절차를 클라우드 환경 설정 초안에 저장. 게시·새 작업 복원은 미검증.
- 코드·보고서·참고자료의 로컬 Git 정리 및 전달 ZIP 생성으로 마무리. 실제 원본·개별 위치 가공자료·캐시·비밀값은 제외.
- 다음 연구는 자료 수집이 전제: 실제 연속 차량 GPS, 동기간 공간 맥락, 독립 평가 라벨. 현재 결과를 광고효과/실측 통합모델 검증으로 확대하지 않는다.

## View-T·외부 리뷰 반영 (2026-10-10 후속 작업)

기존 엔진을 보존하면서 타임스탬프/고립 spike/현지 시간/정규화 검사를 보강했다. 마포구 기본의 CSV·Excel 연동, 50:50·60:40·사용자 가중치, 모델 비교·paired-day Bootstrap·가상 밀크런·GIS UI를 구현했다. pytest 68 통과/원본 1 xfail, 연구 오류 변이 10/10 검출, 독립 새 환경 smoke 통과. View-T 실자료/API/승인 경로는 프록시 차단으로 확인하지 못했다. 최신 범위와 증거는 DELIVERY_REPORT.md에 정리했다.
