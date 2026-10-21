"""Package reproducible public summaries and code; exclude provider originals."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / "deliverables/Transit_OOH_Public_Research_Package.zip"
    files = [root / p for p in ["README.md", "pyproject.toml", "uv.lock", ".gitignore"]]
    extensions = {
        ".py",
        ".sh",
        ".md",
        ".json",
        ".yaml",
        ".csv",
        ".xlsx",
        ".png",
        ".svg",
        ".xml",
        ".pptx",
        ".pdf",
    }
    for folder in [
        "src",
        "app",
        "tests",
        "scripts",
        "configs",
        "examples",
        "docs",
        "reports/public_decision",
        "reports/model_audit",
        "deliverables/competition2026",
        "deliverables/viewt_actual",
    ]:
        files.extend(
            p
            for p in (root / folder).rglob("*")
            if p.is_file()
            and p.suffix in extensions
            and "__pycache__" not in p.parts
            and "previews" not in p.parts
            and p.name != "Contact_Sheet.png"
        )
    for name in [
        "public_research_tests.xml",
        "public_research_validation.json",
        "public_independent_check.json",
        "public_package_tests.xml",
        "public_package_validation.json",
    ]:
        evidence = root / "reports/runs" / name
        if evidence.is_file():
            files.append(evidence)
    notebooks = list((root / "reference").glob("*.ipynb"))
    if len(notebooks) != 1:
        raise ValueError(
            "Require the preserved original synthetic PoC for regression checks"
        )
    files += notebooks
    required = [
        root / "reports/public_decision/summary.json",
        root / "docs/PUBLIC_DATA_RESEARCH_REPORT.md",
        root / "deliverables/competition2026/Transit_OOH_Competition_Anonymous.pdf",
    ]
    if any(not p.is_file() for p in required):
        raise ValueError("Study report and anonymous slides must be generated first")
    files = sorted(set(files))
    manifest = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as z:
        for path in files:
            z.write(path, str(path.relative_to(root)))
        z.writestr(
            "PACKAGE_README.txt",
            "Transit OOH 공개자료 연구·검수 패키지\n\n연구: docs/PUBLIC_DATA_RESEARCH_REPORT.md\n설치: bash scripts/setup.sh\n앱: bash scripts/run.sh streamlit run app/streamlit_app.py\n검사: bash scripts/run.sh pytest\n독립 조합 재계산: bash scripts/run.sh python scripts/check_public_portfolios.py\n\n실제 집계표로 새 후보선정 연구를 재현합니다. 기관 원본·개별 O/D·키는 포함하지 않습니다. 다른 실제 자료 화면은 별도 입력이 필요합니다. 과거 예비값 인지 후 회고적 재현이며 외부 사전등록·광고효과 검증이 아닙니다.\n\n경진대회 제출용 파일: deliverables/competition2026/Transit_OOH_Competition_Anonymous.pdf\n이 전체 검수 ZIP은 과거 코드·문서·합성 PoC도 포함합니다. 익명 심사에는 지정한 익명 PDF만 사용하세요. 별첨 서명과 팀 역할 사실 확인은 사용자가 마쳐야 합니다.\n",
        )
        z.writestr(
            "PACKAGE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
    with ZipFile(target) as z:
        if z.testzip() is not None:
            raise ValueError("Invalid package CRC")
    print(
        json.dumps(
            {
                "file": str(target.relative_to(root)),
                "bytes": target.stat().st_size,
                "files": len(files) + 2,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
