"""Small runnable code/review ZIP; institution originals and credentials excluded."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / "deliverables/Transit_OOH_Model_Audit_Package.zip"
    files = [
        root / name for name in ["README.md", "pyproject.toml", "uv.lock", ".gitignore"]
    ]
    allowed = {
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
    }
    for folder in [
        "src",
        "app",
        "tests",
        "scripts",
        "configs",
        "examples",
        "docs",
        "reports/model_audit",
    ]:
        files += [
            p
            for p in (root / folder).rglob("*")
            if p.is_file() and p.suffix in allowed and "__pycache__" not in p.parts
        ]
    files += [
        root / "reports/runs/model_finalization_tests.xml",
        root / "reports/runs/model_finalization_validation.json",
    ]
    # Include the independent extraction check when it has been performed.
    for name in ["model_package_tests.xml", "model_package_smoke.json"]:
        evidence = root / "reports/runs" / name
        if evidence.is_file():
            files.append(evidence)
    # The legacy regression tests execute this preserved synthetic PoC. Include
    # their input unchanged so the standalone ZIP runs the same comparisons.
    notebooks = sorted((root / "reference").glob("*.ipynb"))
    if len(notebooks) != 1:
        raise ValueError("Expected one preserved PoC notebook for regression tests")
    files += notebooks
    files = sorted(set(files))
    for file in files:
        if not file.is_file():
            raise FileNotFoundError(f"Required release artifact missing: {file.name}")
    manifest = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for p in files:
            archive.write(p, str(p.relative_to(root)))
        archive.writestr(
            "PACKAGE_README.txt",
            "Transit OOH 모델 고도화 검수 패키지\n\n먼저 docs/MODEL_AUDIT_REPORT.md를 읽으세요.\n설치: bash scripts/setup.sh\n앱: bash scripts/run.sh streamlit run app/streamlit_app.py\n테스트: bash scripts/run.sh pytest\n\n코드·설정·테스트·고정 의존성·합성 예제·새 연구 그림/표를 포함합니다.\n기존 비교 검사의 입력인 원본 합성 PoC 노트북도 포함합니다.\n기관 원본·개별 O/D·인증키·과거 전체 보고서·발표 원본은 포함하지 않습니다.\n공식자료 화면은 별도 수집/입력 후 사용하고 자료가 없으면 입력 대기로 표시됩니다.\n실제 통합 모델 우월성과 광고효과의 독립 실증은 미완료입니다.\nREADME의 과거 보고서/발표 링크는 GitHub 전체 저장소에서 열 수 있습니다.\n",
        )
        archive.writestr(
            "PACKAGE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
    with ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt review archive")
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
