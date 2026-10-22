# PM 스타일 · 익명 경진대회 발표자료

제출용: **Transit_OOH_PMstyle_Anonymous.pdf** (표지 포함 15쪽).
수정용: **Transit_OOH_PMstyle_Anonymous.pptx**.

사용자가 제공한 PM 발표자료의 흰 배경·회색/주황 제목·청록색 강조·2열 논문형 배치·모서리 장식만 참고했습니다. 참고자료의 연구 내용·실험 결과·로고·소속·인물 사진은 복사하지 않았습니다. 원본의 이미지형 텍스트를 재사용하지 않고 제목·본문·도형을 편집 가능하게 만들었습니다.

이전 1·2·3차의 배송 이동데이터 활용 동기와 개발 흐름을 복원하고 최신 실제 공개자료 연구를 반영했습니다. 과거 합성 PoC·계획 수치와 확인되지 않은 시장규모는 현재 실증 성과로 쓰지 않았습니다. 2025 추정 거래 검사는 탐색적·회고적이며 실제 광고효과 검증이 아닙니다.

재생성: 먼저 python scripts/pmstyle_figures.py, 다음 python scripts/build_pmstyle_slides.py. 발표 제작에 python-pptx, pandas, numpy, matplotlib, Pillow, PyMuPDF, LibreOffice, Noto Sans CJK KR 글꼴이 필요합니다. 연구 앱 의존성은 바꾸지 않았습니다. PDF는 실제 PPTX를 LibreOffice로 변환했습니다. 글꼴이 없는 PC의 PPT 표시 차이를 피하려면 제출은 PDF를 사용하세요.

협업 관련 내용은 사용자가 별도로 작성합니다. 최종 편집 후 소속·인명·로고·문서 속성과 제출 별첨을 다시 확인하세요. 참고문헌의 공공기관·논문 저자는 소속 표시와 구분합니다.

## 파일

- [편집용 PPTX](Transit_OOH_PMstyle_Anonymous.pptx)
- [제출용 익명 PDF](Transit_OOH_PMstyle_Anonymous.pdf): 15쪽, 약 1.4MB
- [전체 미리보기](Contact_Sheet.png)
- [발표 대본](발표대본.md): 계획상 본문 7분 30초, 실제 낭독 미측정
- [편집·검수용 전체 ZIP](../Transit_OOH_PMstyle_Presentation_Package.zip)

제목·본문·표·도형은 편집할 수 있습니다. 그래프·수식·앱 화면은 이미지이며, 그래프의 SVG와 생성 코드를 함께 제공합니다. 앱 화면은 실제 공개자료를 읽고 조작한 결과입니다. 캡처 환경에서 외부 배경지도 요청이 차단되어 좌표점과 한글 동명 중심으로 표시됩니다. 슬라이더 0·50·100%와 CSV 15행의 점수는 실제 앱에서 대조했습니다.

`presentation_validation.json`은 15쪽·익명성·화면 경계·변환 누락·텍스트 겹침 검사와 최종 시각 검토를 기록합니다. `dashboard_validation.json`은 이번 화면 검증 기록입니다. 기존 연구 전체 자동검사 **205 passed / 1 xfailed**는 2026-10-21 기록이며, 발표 편집 과정에서 새 연구 성능으로 계산한 수치가 아닙니다.

발표 제작의 Python 버전은 `requirements-presentation.txt`에 기록했습니다. 전체 코드·앱은 동일 Git 커밋의 저장소에서 받으세요. ZIP에는 발표 재생성 코드와 집계 결과 근거를 넣고 기관 원본·참고 PM 원본·API 키는 넣지 않았습니다.
