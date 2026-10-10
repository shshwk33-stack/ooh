# 데이터 출처·접근·권리와 관측단위

확인일: 2026-10-10 (Asia/Seoul). 실제 응답·해시는 `reports/runs/public_acquisition.json`, 원본별 `data/raw/*.provenance.json`에 있다. 원본은 Git 제외. 이 문서의 표본수는 실제 내려받은 파일을 읽은 값이다.

| 자료 / 제공기관 | 공식 출처 | 지역·기간·관측단위 | 실제 필드·상태 | 적용과 제한 |
|---|---|---|---|---|
| LaDe-D / Cainiao-AI | [데이터카드](https://huggingface.co/datasets/Cainiao-AI/LaDe-D), [공식 코드/설명](https://github.com/wenhaomin/LaDe), [원문](https://arxiv.org/abs/2306.10675) | 중국 Jilin, 문서상 2022; 실제 ds 0512–1028, 163개 기록일; 기사별 배송 이벤트 | **Jilin 전체 Parquet 31,415행·57명 확보**, 2,271,457 bytes. order_id, courier_id, city, region_id, aoi_id/type, lng/lat, accept/delivery_time, 해당 시점 근처 GPS·gps_time, ds | PDA 기사 위치이지 차량 유형이 알려진 연속 GPS가 아니다. 작업 접수→완료 시간은 정차시간이 아니다. AOI 키 집계·월별 순위·기사 bootstrap만 실측 분석 |
| Amazon LMRRC / Amazon·MIT | [AWS 공식 카탈로그](https://github.com/awslabs/open-data-registry/blob/main/datasets/amazon-last-mile-challenges.yaml), [공식 구조 문서](https://github.com/MIT-CAVE/rc-cli/blob/main/templates/data_structures.md), [배포 버킷](https://amazon-last-mile-challenges.s3.amazonaws.com/almrrc2021/Readme.txt) | 미국 2018 평가 경로, 실제 2018-06-01–10-02; 방문지·방문순서 | **평가 JSON 3,052경로·433,231방문지(Station 3,052, Dropoff 430,179), 18 station 확보**. routes 37,777,768 bytes, actual_sequences 4,625,218 bytes. lat/lng(WGS84), zone_id, departure_time_utc, stop type·순서 | 연속 GPS/도착시각/정차시간 없음. planned_service_time이 있더라도 계획값이지 실측이 아님. 제공자 교란 좌표. 공식 카탈로그 설명의 evaluation 3,072와 실제 파일 3,052가 달라 **파일 수치 우선**, 누락분을 생성하지 않음 |
| OpenStreetMap contributors | [공식 map API](https://www.openstreetmap.org/api/0.6/map?bbox=126.975,37.563,126.982,37.568), [저작권](https://www.openstreetmap.org/copyright) | 서울 bbox [126.975,37.563,126.982,37.568], 현재 지도 스냅샷 | **OSM XML 2,885,346 bytes 확보, bbox 내부 amenity node 601개·29종·200m 격자 12개**. node lat/lon, amenity, last edit | node만 사용하고 건물/way/relation amenity는 제외. 완전한 POI 조사·유동인구가 아니다. 수정일은 시설 관측 유효기간이 아니다. 서울 공간 기술통계로 분리 |
| 서울 생활인구 / 서울특별시 | [공식 공개 페이지 OA-14991](https://data.seoul.go.kr/dataList/OA-14991/S/1/datasetView.do) | 서울, 시간대·지역별 생활인구. 데이터셋별 집계구/행정동 지지영역 구분 필요 | 페이지 접근·메타데이터 확인. 실제 원자료 다운로드 **미실행**. 페이지에 Sheet/Open API 제공, sheet 최대 1,000건 안내 | 현재 키 없음. API 본 호출/격자 정합성 미검증. 생활인구 추정치를 실제 광고 노출량으로 해석하지 않음 |
| 소상공인시장진흥공단 상가(상권)정보 | [공식 파일 데이터](https://www.data.go.kr/data/15083033/fileData.do) | 전국, 확인한 페이지 기준 2026-06-30 분기 자료 | 상호/업종/주소/경위도 제공 확인. 페이지 접근 성공, 전체 파일 **미수집** | 현재 배송 GPS와 동기간/동영역 통합 실증 불가. 인증된 API와 파일 다운로드는 별도 절차. 아직 요청량/개별 API 쿼터 실증하지 않음 |
| 카카오 Local | [공식 개발 문서](https://developers.kakao.com/docs/latest/ko/local/dev-guide) | 요청 지역 현재 장소검색·좌표변환 | REST API 키 요구 확인. 키 미설정, API 호출 **미실행** | 검색 결과는 완전한 POI 모집단이 아님. 앱별 쿼터/저장·재배포·상업 이용 조건을 확인하지 않아 벌크 수집에 사용하지 않음 |
| Synthetic schedule v1 / 본 프로젝트 | `src/transit_ooh/synthetic.py` | 서울 좌표 범위, 2026-09-21부터 6일; 가상 차량 GPS와 정답 스케줄 | 기본 seed42, 공간필드 독립 seed20260921, 모두 **synthetic** | 알고리즘 검증용. 실제 배송·인구·POI·광고성과 아님 |

## 라이선스와 원문 확인

1. **LaDe 표기 충돌:** Hugging Face YAML에는 `apache-2.0`, 실제 논문 §1와 Appendix C.6에는 **CC BY-NC 4.0 / 비상업 이용**이라고 적혀 있다. 공식 README는 research purposes를 명시한다. 이번 비상업 연구 목적의 로컬 분석은 더 제한적인 조건을 적용했다. 원본 재배포·상업화는 제공자 확인 전 보류하고 Git에 넣지 않는다. 가명화되었다고 재식별을 시도하지 않는다.
2. LaDe 논문 §3.1 및 Appendix C.4 원문을 확인했다. 제공자는 기사/패키지 ID 익명화와 좌표 교란, 위치 정확도 10m 제한을 설명한다. 이것은 **제공자 설명**이며 이 표본의 실제 오차분포를 독립적으로 측정한 것이 아니다. 좌표 datum과 offset 없는 시각의 timezone은 확보한 문서에서 확정하지 못했다. 따라서 서울 좌표/UTC로 강제 변환하지 않는다.
3. Amazon 배포처 `License.txt`를 읽었으며 **CC BY-NC 4.0**, Amazon copyright/attribution을 따른다. 카탈로그의 논문 DOI는 배포처가 제시한 식별자이며 이번 보고서에서 읽지 않은 해당 논문 결과를 인용하지 않는다.
4. OSM 응답이 명시한 **ODbL**, © OpenStreetMap contributors를 데이터표·화면·그래프에 표시한다. 파생 데이터베이스 공유 의무 등은 실제 배포형태에 따라 검토해야 한다.
5. 서울 생활인구 공개 페이지에는 **공공누리 1유형(출처표시, 상업적 이용·변경 가능)**, 소상공인 파일 페이지에는 **무료 / 이용허락범위 제한 없음**이 표시되었다. 개별 API 키·쿼터·파일 이용조건까지 모두 검증했다고 주장하지 않는다.

확인한 학술 원문: Wu et al., *LaDe: The First Comprehensive Last-mile Delivery Dataset from Industry*, [arXiv:2306.10675](https://arxiv.org/abs/2306.10675), 23쪽 PDF. 원문에서 데이터 수집·관측단위·익명화·배포조건을 확인했다. 기존 발표자료의 산업규모, 광고성과 수치, 기타 논문의 원문 미확인 주장은 새로운 결과의 근거로 재사용하지 않았다.

## 접근 이력과 재현

- 초기 일부 사이트는 프록시 403. 필요한 도메인을 환경 설정 초안에 추가했다. 후속 실제 요청에서 접근 성공을 확인했다. 저장 자체가 게시/새 환경 복원을 증명하지는 않는다.
- LaDe 최초 파일 다운로드는 리디렉션 CDN `us.aws.cdn.hf.co` 차단. 도메인 추가 후 전체 파일 다운로드 성공, 배포처 LFS SHA-256 `ed0296b83d84f739bb91ab3d3cf1a430cf71e3793e25ddf50f88aa3ef34b51fc` 일치. 공식 preview 100행도 보존하되 최종 분석은 전체 Jilin 분할을 사용한다.
- Overpass는 HTTP 406. 요청을 성공으로 취급하지 않고 **OSM 공식 map API의 작은 bbox**로 수정해 성공했다. 두 원본/coverage가 같다고 가정하지 않았다.
- Amazon SHA-256는 HTTPS로 최초 확보한 파일에서 기록한 재현성 pin이다. 제공자의 독립 전자서명이라고 주장하지 않는다. 인증서·패키지 검증을 끄지 않았다.
- `fetch-public`은 최대 크기·TLS·SHA 검증을 수행하고 일치하는 캐시를 재사용한다. OSM 원본을 갱신하려면 기존 스냅샷과 sidecar를 별도로 보존한 뒤 새로 수집한다. live 지도는 미래에 달라질 수 있다.

## 아직 필요한 자료

국내 배송차량 **연속** GPS(동의·차종·주기·좌표계·시간대·익명화 조건 포함), 같은 시기/영역 공간 맥락, 입력과 독립된 평가 라벨. 이 자료 없이는 통합모델의 실측 외부 타당성과 광고효과를 검증할 수 없다. 키 값은 채팅/공개 코드에 넣지 않고 안전한 환경 설정을 사용한다. 현재 확보한 공개 자료 분석에는 별도 API 키가 필요하지 않다.
