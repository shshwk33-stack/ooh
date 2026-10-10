"""Build a standalone local HTML helper. No uploaded source data are included."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

root = Path(__file__).resolve().parents[1]
template = (root / "tools/boundary_helper/page.html").read_text()
core = (root / "tools/boundary_helper/core.js").read_text()
assert template.count("/*__BOUNDARY_CORE__*/") == 1
html = template.replace("/*__BOUNDARY_CORE__*/", core)
instructions = """마포구 경계 파일 준비

1. 이 ZIP을 압축 해제하고 Mapo_boundary_helper.html을 Chrome 또는 Edge로 여세요.
2. 이미 받은 Emd_district_2023.zip도 압축 해제하세요.
3. 도구에서 같은 묶음의 .shp/.shx/.dbf/.prj 파일 네 개를 함께 선택하세요.
4. '마포구 ZIP 만들기'를 누르고 '완성된 마포구 ZIP 다운로드'를 누르세요.
5. 생성된 mapo_boundary_2023.zip을 대화에 업로드하세요.

파일은 본인 컴퓨터의 브라우저에서 처리됩니다. 설치·로그인·API 키가 필요하지 않습니다.
원본 자료는 이 도구에 포함되지 않습니다. 원본의 좌표·경계·속성값을 유지합니다.
2023/2024 경계 동일성과 자료 이용조건은 별도 검토사항입니다.
"""
target = root / "deliverables/Mapo_boundary_helper.zip"
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    for name, text in [
        ("Mapo_boundary_helper.html", html),
        ("사용방법.txt", instructions),
    ]:
        info = ZipInfo(name)
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, text.encode("utf-8"))
print(f"Created {target.name}: {target.stat().st_size} bytes; no source data embedded.")
