"""Build a compact review ZIP from Git-indexed research files, without raw GPS."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
listed = subprocess.run(
    ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
).stdout.split("\0")
allowed_roots = {
    "src",
    "app",
    "tests",
    "scripts",
    "configs",
    "docs",
    "reports",
    "examples",
    "reference",
    ".github",
}
root_files = {
    "README.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".gitignore",
    ".gitattributes",
    "Transit_OOH_Codex_통합마스터지시서.md",
}
latest = json.loads((ROOT / "reports/runs/latest.json").read_text())["run_id"]
paths = []
for name in listed:
    if not name:
        continue
    p = Path(name)
    if p.parts[0] not in allowed_roots and name not in root_files:
        continue
    if p.parts[0] == "reference" and p.suffix not in {".ipynb", ".txt", ".md"}:
        continue
    if len(p.parts) > 3 and p.parts[:2] == ("reports", "runs") and p.parts[2] != latest:
        continue
    paths.append(p)
readme = """Transit OOH View-T 검수 패키지

먼저 docs/DELIVERY_REPORT.md와 docs/VIEWT_DATA_GUIDE.md를 읽으세요.
View-T 실제 데이터/API는 미확보이며 examples/viewt와 reports/viewt는 synthetic입니다.
기존 실제 공개자료 결과는 별도 관측 단위의 기술통계입니다.

포함: 코드, 의존성 lock, 테스트, 현재 연구 결과, 발표 그래프, 출처, 원본 노트북,
마스터 지시서, 제공된 외부 리뷰 텍스트. 원본 발표 PPTX/PDF/DOCX, 과거 실행별 중복 표,
개별 실제 위치 기록, API 키, 가상환경은 제외했습니다. 전체 참고자료는 GitHub 작업 브랜치 ZIP에 있습니다.
ZIP_MANIFEST.json은 포함 파일의 SHA-256입니다. 코드 실행은 README.md를 따르세요.
"""
out = ROOT / "deliverables/Transit_OOH_ViewT_review.zip"
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    hashes = {}
    for p in sorted(paths):
        data = (ROOT / p).read_bytes()
        hashes[str(p)] = hashlib.sha256(data).hexdigest()
        z.writestr(str(p), data)
    z.writestr("START_REVIEW_HERE.txt", readme)
    z.writestr("ZIP_MANIFEST.json", json.dumps(hashes, ensure_ascii=False, indent=2))
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for name, expected in json.loads(z.read("ZIP_MANIFEST.json")).items():
        assert hashlib.sha256(z.read(name)).hexdigest() == expected
print(
    json.dumps(
        {
            "path": str(out.relative_to(ROOT)),
            "files": len(paths),
            "bytes": out.stat().st_size,
            "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        },
        indent=2,
    )
)
