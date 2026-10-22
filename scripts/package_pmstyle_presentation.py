"""Package the checked PM-style deck, editable sources and aggregate evidence.

This is a presentation/review package, not a replacement for the full app
package. Institutional raw data, private reference decks and keys are excluded.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "deliverables/competition2026_pmstyle"
OUTPUT = ROOT / "deliverables/Transit_OOH_PMstyle_Presentation_Package.zip"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    validation = json.loads((DECK / "presentation_validation.json").read_text())
    if validation["pdf_pages"] != 15 or validation["visual_review"] != "completed":
        raise ValueError("Final 15-page visual review must be completed first")
    for suffix in ("pptx", "pdf"):
        path = DECK / f"Transit_OOH_PMstyle_Anonymous.{suffix}"
        if sha256(path) != validation[f"{suffix}_sha256"]:
            raise ValueError(f"Deck changed after validation: {suffix}")
    report = ROOT / "reports/public_decision"
    if sha256(report / "summary.json") != validation["source_report_sha256"]:
        raise ValueError("Study source changed after presentation validation")
    summary = json.loads((report / "summary.json").read_text())
    for relative, expected in summary["artifacts_sha256"].items():
        path = (report / relative).resolve()
        if not path.is_relative_to(report) or sha256(path) != expected:
            raise ValueError(f"Study artifact changed: {relative}")

    paths = [p for p in DECK.rglob("*") if p.is_file() and not p.name.startswith(".")]
    paths += [p for p in report.rglob("*") if p.is_file()]
    paths += [
        ROOT / relative
        for relative in (
            "scripts/build_pmstyle_slides.py",
            "scripts/pmstyle_figures.py",
            "scripts/build_competition_slides.py",
            "scripts/package_pmstyle_presentation.py",
            "docs/PM_STYLE_DESIGN_BRIEF.md",
            "docs/PM_STYLE_CONTENT_REVIEW.md",
            "docs/PUBLIC_DATA_RESEARCH_REPORT.md",
        )
    ]
    paths = sorted(set(paths))
    records = [
        {
            "path": p.relative_to(ROOT).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
        }
        for p in paths
    ]
    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "purpose": "Presentation, editable build sources and aggregate research evidence",
        "submission_file": "deliverables/competition2026_pmstyle/Transit_OOH_PMstyle_Anonymous.pdf",
        "not_included": [
            "institutional raw data",
            "private reference decks",
            "API keys",
            "full application source",
        ],
        "files": records,
    }
    instructions = """Transit OOH · PM 스타일 발표자료

제출할 파일: deliverables/competition2026_pmstyle/Transit_OOH_PMstyle_Anonymous.pdf
편집할 파일: 같은 폴더의 PPTX. 전체 15쪽이며 본문·표·도형을 편집할 수 있습니다.
그래프·수식·앱 캡처는 이미지이고 생성 소스·SVG가 함께 있습니다.
발표 대본: 같은 폴더의 발표대본.md (계획상 7분30초, 실제 낭독 미측정).
전체 미리보기: Contact_Sheet.png / 쪽별 미리보기: previews/.

이 ZIP은 편집·검수용입니다. 심사 제출은 위 익명 PDF를 사용합니다.
최종 내용을 편집했다면 다시 PDF로 변환하고 익명성·쪽수·겹침을 확인하세요.

재생성은 압축을 푼 루트에서 다음 순서로 실행합니다.
  pip install -r deliverables/competition2026_pmstyle/requirements-presentation.txt
  python scripts/pmstyle_figures.py
  python scripts/build_pmstyle_slides.py
LibreOffice(soffice), Noto Sans CJK KR 글꼴이 별도 필요합니다.
빌드 후 visual_review=pending으로 초기화됩니다. 새 결과를 다시 시각 검토하세요.

reports/public_decision/은 기존 집계 연구의 표·그림·해시 근거입니다.
발표 편집 중 연구 설정·결과를 새로 바꾸거나 유리한 값만 선택하지 않았습니다.
실제 배송 GPS·광고효과·노출·매출 개선을 입증한 자료는 아닙니다.
앱 전체 코드가 필요하면 GitHub 저장소의 동일 커밋을 받으세요.
원본 PM 발표와 기관 원자료·인증키는 포함하지 않습니다.
"""
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("읽어주세요.txt", instructions)
        archive.writestr(
            "MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
        for path, record in zip(paths, records, strict=True):
            archive.write(path, record["path"])
    with ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise ValueError("Package CRC validation failed")
        for record in records:
            content = archive.read(record["path"])
            if hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise ValueError(f"Packaged file hash differs: {record['path']}")
    result = {
        "file": OUTPUT.name,
        "bytes": OUTPUT.stat().st_size,
        "sha256": sha256(OUTPUT),
        "files_verified": len(records),
        "crc_verified": True,
    }
    OUTPUT.with_suffix(".validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
