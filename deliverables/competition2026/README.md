# 익명 경진대회 발표자료

제출 파일: **Transit_OOH_Competition_Anonymous.pdf** (표지 포함 15쪽).
수정 원본: Transit_OOH_Competition_Anonymous.pptx. PPTX를 LibreOffice로 실제 변환했습니다.

자료·모델·실험은 reports/public_decision의 검증된 결과만 사용했습니다. 광고효과·실제 배송 운행·예측 정확도를 입증한 자료로 해석하지 않습니다.

## 재생성

LibreOffice와 Noto Sans CJK KR 글꼴이 필요합니다. 아래 명령은 연구 의존성을 변경하지 않고 발표 제작 도구를 추가해 실행합니다.

```bash
uv run --frozen --with python-pptx==1.0.2 --with Pillow==12.3.0 python scripts/build_competition_slides.py
```

assets의 익명 실제 대시보드 캡처를 사용합니다. 수정 가능한 PPTX는 Noto Sans CJK KR 글꼴이 없으면 대체 글꼴로 표시될 수 있으므로 제출은 고정 PDF를 권합니다.

## 제출 전 팀에서 확인할 것

- 참가신청서·지도교수 추천서·연구윤리서약서의 실제 작성·서명 상태
- 협업 관련 내용은 사용자가 별도로 작성합니다.
- 최종 편집 후 학교·교수·학번·개인 계정·파일 경로·QR 등 익명성 재검사
- 발표 신청 페이지의 정확한 최종 마감·접수 완료 여부

이 폴더의 코드·검수 메모·미리보기는 PDF 본문이 아닌 별도 검토 파일입니다. 제출처에 별도 요구가 없는 한 PDF와 공식 별첨만 제출합니다.
