# 연구 데이터 구역

- `sources/`: 확보된 자료의 출처·좌표·해시 계약. 원천 파일은 기존 `public/data/`에서 읽기만 한다.
- `synthetic/`: 개발용 합성 입력. 실측 배송차량 운행기록이 아니다.
- `templates/`: 향후 실측 자료를 넣을 입력 스키마.
- `runs/`: 로컬 실행 결과(버전관리 제외). 다른 실행은 새 출력 폴더를 사용한다.
- `private/`: 향후 사용자가 제공하는 민감 원천자료(버전관리 제외).

계약상 분류는 OBSERVED_GPS / PUBLIC_AGGREGATE / ESTIMATED / SYNTHETIC / DERIVED다. 분류 라벨만으로 실측의 진위가 검증되는 것은 아니다. 파생 결과에는 입력 해시와 부모 출처를 기록한다.

2013 서울 경계는 PUBLIC_AGGREGATE 계열의 `administrative_boundary`다. 교통·인구 집계 관측값이 아닌 실제 지리 형상이며, 최신 행정경계나 공식 면적 통계로 취급하지 않는다.
