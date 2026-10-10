# 검수용 다운로드

[Transit_OOH_ViewT_review.zip](Transit_OOH_ViewT_review.zip)을 다운로드해 검수 모델에 올리세요. GitHub 파일 화면의 **Download raw file**도 사용할 수 있습니다.

코드·테스트·현재 연구 결과·그래프·출처·마스터 지시서·원본 노트북·제공된 리뷰를 포함합니다. 큰 발표자료와 개별 실측 원본, API 키, 가상환경은 제외했습니다. ZIP 안 `START_REVIEW_HERE.txt`에 범위, `ZIP_MANIFEST.json`에 파일별 해시가 있습니다.

전체 프로젝트와 원본 발표자료는 저장소 `feat/transit-ooh-research` 브랜치의 **Code → Download ZIP**으로 받을 수 있습니다. View-T 실제 자료 확보는 아직 완료되지 않았고 마포구 예제는 합성입니다.

2026-10-11(한국시간) 공식 사이트 재조사에 따른 최신 [다운로드·신청 안내](../docs/VIEWT_DOWNLOAD_CHECKLIST.md)와 [복사용 신청문](VIEWT_DATA_REQUEST.txt)을 추가했습니다. 기존 검수 ZIP은 2026-10-10 코드·실험 산출물이며 이 후속 안내는 포함하지 않습니다. 재조사 기록: [공식 화면·API 확인 결과](../reports/runs/viewt_official_reconnaissance.json). 평균일·경로 이용비율 원본의 전용 어댑터는 아직 미구현입니다.

**큰 읍면동 지도 전달:** [마포구 경계 추출 도구 ZIP](Mapo_boundary_helper.zip)을 압축 해제하고 HTML을 열어, 기존 읍면동 원본의 SHP/SHX/DBF/PRJ 네 파일을 선택하세요. 생성된 `mapo_boundary_2023.zip`만 전달하면 됩니다. 파일은 사용자 브라우저에서 처리되며 이 도구에는 기관 원자료가 들어 있지 않습니다. [지원 범위·검증 안내](../tools/boundary_helper/README.md).

검수 요청 예시:

> DELIVERY_REPORT와 VIEWT_DATA_GUIDE를 먼저 읽고, 실측/추정/합성 구분, 시공간 조인 차단, 인구 O/D 중복 집계 방지, 모델별 가중치와 Bootstrap/holdout의 실제 구현, 68개 테스트 및 10개 변이 검사의 실효성, 실제 실행 결과의 출처와 연구 주장 한계를 검토해 주세요. 실행하지 않은 검사는 실행했다고 표현하지 말아 주세요.
