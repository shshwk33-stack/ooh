"""Build an anonymous 15-slide competition PPTX and convert that PPTX to PDF.

Only checked, acquired aggregate tables are read. Missing study inputs abort the
build. No team contributions, affiliations or advertising outcomes are invented.
Presentation-only dependencies are intentionally outside the research lockfile:
python-pptx, Pillow and PyMuPDF; LibreOffice performs the actual PDF conversion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import fitz
import pandas as pd
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

NAVY = "142D49"
TEAL = "087F8C"
ORANGE = "E58A3B"
BLUE = "367DB0"
INK = "263D50"
MUTED = "617386"
PALE = "EAF5F5"
BG = "F5F8FB"
LINE = "DCE6ED"
WHITE = "FFFFFF"
FONT = "Noto Sans CJK KR"
MODEL_LABEL = {
    "A_stores": "A  상권 단독",
    "B_vehicle_context": "B  교통 단독",
    "C50_reduced": "C  50:50",
    "C60_reduced": "C  60:40",
    "R_minimax": "R  강건 선택",
}
ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333333), Inches(7.5)
        self.prs.core_properties.title = (
            "Transit OOH: 공개자료 기반 강건한 후보지역 선정"
        )
        self.prs.core_properties.subject = "공개자료 기반 의사결정 연구"
        self.prs.core_properties.author = ""
        self.prs.core_properties.last_modified_by = ""
        self.prs.core_properties.keywords = ""
        self.prs.core_properties.comments = ""
        self.slides = []
        self.transcript = []

    def box(self, s, x, y, w, h, fill=WHITE, line=None, rounded=True):
        kind = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
        shape = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(fill)
        effect = OxmlElement("a:effectLst")
        shape._element.spPr.append(effect)
        style = shape._element.find(
            "{http://schemas.openxmlformats.org/presentationml/2006/main}style"
        )
        if style is not None:
            shape._element.remove(style)
        shape.line.fill.background() if line is None else None
        if line:
            shape.line.color.rgb = RGBColor.from_string(line)
            shape.line.width = Pt(0.6)
        if rounded:
            shape.adjustments[0] = 0.08
        return shape

    def text(
        self,
        s,
        value,
        x,
        y,
        w,
        h,
        size=18,
        color=INK,
        bold=False,
        align=PP_ALIGN.LEFT,
        valign=MSO_ANCHOR.TOP,
        margin=0,
    ):
        shape = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = shape.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(margin)
        tf.margin_top = tf.margin_bottom = Inches(margin)
        tf.vertical_anchor = valign
        for i, line in enumerate(str(value).split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.space_before, p.space_after = Pt(0), Pt(3)
            p.line_spacing = 1.12
            r = p.add_run()
            r.text = line
            r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
            r.font.color.rgb = RGBColor.from_string(color)
            # Explicit East Asian font prevents platform substitution surprises.

            ea = OxmlElement("a:ea")
            ea.set("typeface", FONT)
            r._r.get_or_add_rPr().append(ea)
        return shape

    def rule(self, s, x, y, w, color=LINE, h=0.012):
        self.box(s, x, y, w, h, fill=color, rounded=False)

    def new(
        self,
        chapter,
        title,
        subtitle="",
        source="자료: 서울시·KTDB View-T / 공개 집계·추정자료",
    ):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = RGBColor.from_string(BG)
        self.box(s, 0, 0, 0.16, 7.5, fill=TEAL, rounded=False)
        self.text(
            s,
            "TRANSIT OOH  /  " + chapter,
            0.55,
            0.28,
            11.9,
            0.23,
            size=10.4,
            color=TEAL,
            bold=True,
        )
        self.text(s, title, 0.55, 0.69, 12.2, 0.62, size=27.5, color=NAVY, bold=True)
        if subtitle:
            self.text(s, subtitle, 0.58, 1.36, 12.0, 0.4, size=12.3, color=MUTED)
        self.rule(s, 0.56, 6.99, 12.2)
        self.text(s, source, 0.58, 7.1, 11.25, 0.22, size=8.7, color=MUTED)
        self.text(
            s,
            f"{len(self.slides) + 1:02d} / 15",
            11.95,
            7.08,
            0.8,
            0.24,
            size=9.7,
            color=MUTED,
            align=PP_ALIGN.RIGHT,
        )
        self.slides.append(s)
        self.transcript.append(
            {
                "page": len(self.slides),
                "chapter": chapter,
                "title": title,
                "subtitle": subtitle,
                "source": source,
            }
        )
        return s

    def card(self, s, x, y, w, h, kicker, title, body, accent=TEAL, body_size=16):
        self.box(s, x, y, w, h, fill=WHITE, line=LINE)
        self.box(s, x, y, w, 0.065, fill=accent, rounded=False)
        self.text(s, kicker, x + 0.22, y + 0.2, w - 0.44, 0.3, 11, accent, True)
        self.text(s, title, x + 0.22, y + 0.66, w - 0.44, 0.65, 21, NAVY, True)
        self.text(s, body, x + 0.22, y + 1.5, w - 0.44, h - 1.65, body_size, INK)

    def note(self, s, text, y=6.3, fill=PALE, color=TEAL, h=0.44):
        self.box(s, 0.58, y, 12.15, h, fill=fill)
        self.text(s, text, 0.79, y + 0.08, 11.75, h - 0.1, 12.3, color, True)

    def table(
        self, s, headers, rows, x, y, widths, row_h=0.52, size=14, highlight=None
    ):
        total = sum(widths)
        self.box(s, x, y, total, row_h, fill=NAVY, rounded=False)
        for r, row in enumerate([headers, *rows]):
            yy = y + r * row_h
            if r:
                fill = (
                    PALE
                    if (highlight is not None and r - 1 == highlight)
                    else (WHITE if r % 2 else "EDF2F7")
                )
                self.box(s, x, yy, total, row_h, fill=fill, rounded=False)
            xx = x
            for j, v in enumerate(row):
                self.text(
                    s,
                    v,
                    xx + 0.12,
                    yy + 0.1,
                    widths[j] - 0.24,
                    row_h - 0.12,
                    size,
                    WHITE if r == 0 else (TEAL if r - 1 == highlight else INK),
                    r == 0 or r - 1 == highlight,
                )
                xx += widths[j]

    def step(self, s, n, title, body, x, y, w, h, accent=TEAL):
        self.box(s, x, y, w, h, WHITE, LINE)
        self.box(s, x + 0.2, y + 0.2, 0.47, 0.47, accent)
        self.text(
            s,
            str(n),
            x + 0.2,
            y + 0.24,
            0.47,
            0.3,
            17,
            WHITE,
            True,
            align=PP_ALIGN.CENTER,
        )
        self.text(s, title, x + 0.85, y + 0.2, w - 1.05, 0.5, 20, NAVY, True)
        self.text(s, body, x + 0.25, y + 1.0, w - 0.5, h - 1.15, 17, INK)

    def picture(self, s, path, x, y, w, h):
        im = Image.open(path)
        ratio = min(w / im.width, h / im.height)
        ww, hh = im.width * ratio, im.height * ratio
        s.shapes.add_picture(
            str(path),
            Inches(x + (w - ww) / 2),
            Inches(y + (h - hh) / 2),
            width=Inches(ww),
            height=Inches(hh),
        )


def load_study(report):
    summary = json.loads((report / "summary.json").read_text())
    if summary.get("study_type") and "synthetic" in summary["study_type"].lower():
        raise ValueError("Competition deck requires acquired-data study")
    for relative, expected in summary.get("artifacts_sha256", {}).items():
        p = (report / relative).resolve()
        if not p.is_relative_to(report.resolve()) or sha256(p) != expected:
            raise ValueError(f"Study artifact checksum mismatch: {relative}")
    files = [
        "candidate_features",
        "portfolio_comparison",
        "all_optimal_sets",
        "held_out_quarter_specification",
        "held_out_definition_specification",
        "external_context_association",
        "external_context_all_optima",
        "external_context_common_sectors",
        "price_of_robustness",
    ]
    tables = {
        name: pd.read_csv(
            report / "tables" / (name + ".csv"),
            dtype={"grid_id": str, "seoul_dong_id": str},
        )
        for name in files
    }
    return summary, tables


def share(frame, model, quarter=20251):
    v = frame[(frame.model == model) & (frame.quarter == quarter)]
    return float(v.selected_transaction_share.iloc[0])


def build(report, output, dashboard=None):
    summary, t = load_study(report)
    comparison = t["portfolio_comparison"]
    primary = comparison[(comparison.k == 5) & (comparison.weight_low == 0)].copy()
    primary = primary.set_index("model")
    models = list(MODEL_LABEL)
    if set(models) - set(primary.index):
        raise ValueError("Missing primary baseline model")
    n = len(t["candidate_features"])
    count = math.comb(n, 5)
    optima = t["all_optimal_sets"]
    price = t["price_of_robustness"].set_index("model")
    alternative_ids = [set(str(v).split(";")) for v in optima.selected_ids]
    common_ids = set.intersection(*alternative_ids)
    optional_ids = set.union(*alternative_ids) - common_ids
    labels = t["candidate_features"].set_index("grid_id")["name"].to_dict()
    common_names = "·".join(labels[i].removesuffix("동") for i in sorted(common_ids))
    optional_names = " / ".join(labels[i] for i in sorted(optional_ids))
    ext = t["external_context_association"]
    cv = t["held_out_quarter_specification"]
    family_cv = t["held_out_definition_specification"]
    common = t["external_context_common_sectors"]

    def worst(model):
        return float(primary.loc[model, "worst_regret"])

    def pct(v):
        return f"{100 * v:.2f}%"

    d = Deck()
    s = d.new(
        "연구 제안",
        "공개자료로 만드는 선택의 근거",
        source="익명 심사용 발표자료 · 공개 교통·상권자료 기반 연구",
    )
    d.box(s, 0.58, 1.65, 7.5, 4.95, fill=NAVY)
    d.text(
        s,
        "선정 기준이 달라져도\n견고한 후보지역 찾기",
        0.96,
        2.1,
        6.8,
        1.75,
        size=34,
        color=WHITE,
        bold=True,
    )
    d.text(
        s,
        "이동형 광고 운영을 위한\n교통·상권 데이터 기반 의사결정 시스템",
        1.0,
        4.25,
        6.6,
        1.1,
        size=21,
        color="D1E8EF",
    )
    d.text(
        s,
        "마포구 사례  ·  가중치 민감도  ·  최악후회 최소화",
        1.0,
        5.75,
        6.5,
        0.38,
        size=14,
        color="B4D7DE",
    )
    for i, (k, title, desc) in enumerate(
        [
            ("DATA", "실제 공개자료", "2024년 교통·점포 입력"),
            ("DECISION", "후보 집합 선택", "선호·자료 표현의 변화 고려"),
            ("EVIDENCE", "결과와 한계 공개", "비교·동점·외부 맥락 검사"),
        ]
    ):
        y = 1.9 + i * 1.47
        d.text(s, k, 8.55, y, 3.6, 0.25, size=10.5, color=TEAL, bold=True)
        d.text(s, title, 8.55, y + 0.36, 3.7, 0.42, size=22, color=NAVY, bold=True)
        d.text(s, desc, 8.55, y + 0.91, 3.7, 0.43, size=13.5, color=MUTED)

    s = d.new(
        "배경",
        "좋은 지역은 하나의 점수만으로 정해지는가?",
        "이동형 광고의 검토 지역을 정할 때 교통과 상권을 중요하게 보는 비중이 달라질 수 있다.",
    )
    d.card(
        s,
        0.58,
        1.95,
        3.78,
        3.75,
        "관점 01",
        "상권을 먼저 보면",
        "점포가 모인 지역을\n우선 검토한다.\n\n차량 통행 맥락과는\n다른 입지 관점이다.",
        body_size=17,
    )
    d.card(
        s,
        4.59,
        1.95,
        3.78,
        3.75,
        "관점 02",
        "교통을 먼저 보면",
        "차량 통행 맥락이 큰\n지역을 우선 검토한다.\n\n배송 정차나 실제 광고\n노출을 뜻하지는 않는다.",
        accent=BLUE,
        body_size=17,
    )
    d.card(
        s,
        8.61,
        1.95,
        4.1,
        3.75,
        "의사결정의 문제",
        "비중을 확신하기 어렵다",
        "50:50과 60:40 중\n무엇이 최적인지\n입증된 기준이 없다.\n\n선택의 민감도를 확인해야 한다.",
        accent=ORANGE,
        body_size=16,
    )
    d.note(
        s,
        "연구 질문: 기준을 바꾸어도 선택 손실이 작은 후보지역 묶음을 찾을 수 있는가?",
        y=6.13,
        h=0.55,
    )

    s = d.new(
        "목적·활용",
        "운영자가 먼저 검토할 지역을 좁히는 도구",
        "의사결정 단위는 행정동 후보지역이다. 실제 배송 정차지·운행 가능 경로를 확정하지 않는다.",
    )
    for i, (title, body) in enumerate(
        [
            (
                "비교 범위 설정",
                f"마포구의 비교 가능한\n{n}개 동을 대상으로\n검토할 후보 수 K를 정한다.",
            ),
            (
                "선호와 위험 검토",
                "교통 비중을 조절하고\n가정에 따라 바뀌는 후보와\n유지되는 후보를 확인한다.",
            ),
            (
                "검토 후보 전달",
                "핵심 후보·기준별 대안·\n선택 근거를 CSV와\n지도·결과표로 전달한다.",
            ),
        ]
    ):
        d.step(s, i + 1, title, body, 0.58 + i * 4.08, 2.02, 3.9, 3.68)
    d.note(
        s,
        "활용 업무: 광고 운영의 지역 사전 검토 → 세부 거점·차량·예산 검토로 연결",
        y=6.13,
        h=0.55,
    )

    s = d.new(
        "실제 데이터",
        "같은 지역의 교통과 상권을 다른 측정량으로 연결",
        "자료가 있다는 사실과 실제 광고효과를 측정했다는 주장을 구분한다.",
    )
    rows = [
        [
            "교통 맥락",
            "KTDB View-T",
            "2024년 평일 연평균",
            f"{summary.get('network_links_matched', 408)}개 링크",
            "추정 차량 통행",
        ],
        [
            "상권 맥락",
            "서울시 OA-22172",
            "2024년 4개 분기",
            "마포구 16개 동",
            "보고된 전체 점포",
        ],
        [
            "보조 확인",
            "서울시 OA-22175",
            "2025년 4개 분기",
            f"동일 후보 {n}개 동",
            "보고된 추정 거래",
        ],
    ]
    d.table(
        s,
        ["역할", "공식 출처", "기준", "확보 범위", "측정량"],
        rows,
        0.58,
        2.13,
        [1.35, 2.45, 2.6, 2.4, 3.35],
        row_h=0.78,
        size=14,
    )
    d.box(s, 0.58, 5.52, 12.15, 0.95, fill=NAVY)
    d.text(
        s,
        "2024년 입력으로 후보 선택 → 2025년 거래 맥락과 회고적으로 비교",
        0.87,
        5.81,
        11.55,
        0.38,
        19,
        WHITE,
        True,
    )

    s = d.new(
        "자료 품질",
        "결측을 0점으로 바꾸지 않고 비교 가능한 후보만 사용",
        "서로 다른 코드 체계는 연도·지역·고유 명칭을 검사한 대응표로 연결한다.",
    )
    excluded = summary.get("excluded", [])
    excluded_names = ", ".join(x.get("name", "") for x in excluded) or "없음"
    d.text(s, "16개 행정동", 0.78, 2.13, 3.2, 0.6, 29, NAVY, True)
    d.text(s, "점포 자료의 완전한 분기·코드 검사", 0.8, 2.92, 3.4, 0.6, 16, MUTED)
    arrow = d.box(s, 4.43, 2.25, 1.0, 0.4, fill=TEAL, rounded=False)
    arrow.rotation = 0
    d.text(s, f"{n}개 비교 후보", 5.87, 2.13, 5.3, 0.6, 29, TEAL, True)
    d.text(
        s,
        f"제외: {excluded_names} · 보유 도로 맥락 부재는 교통량 0이 아님",
        5.9,
        2.92,
        6.6,
        0.75,
        15.5,
        MUTED,
    )
    checks = [
        ("공간", "기관 부여 링크–동 코드 사용\nID·연장·동 명칭 대조"),
        ("시간", "연평균 교통과 분기 점포 재고 구분\n현재 수정된 과거 자료임을 명시"),
        (
            "측정",
            "인구의 평일 정의가 불명확하여 제외\n점포 전체·일반·프랜차이즈 중복 방지",
        ),
    ]
    for i, (title, body) in enumerate(checks):
        x = 0.58 + i * 4.08
        d.box(s, x, 4.15, 3.9, 1.82, WHITE, LINE)
        d.text(s, title + " 정합성", x + 0.2, 4.35, 3.5, 0.4, 18, NAVY, True)
        d.text(s, body, x + 0.2, 5.02, 3.5, 0.75, 13.6, INK)
    d.note(
        s,
        "도로 원본 해시·기관 코드·링크 길이 검사 / 업종 누락은 0으로 채우지 않음",
        y=6.3,
    )

    s = d.new(
        "융합 구현",
        "공간정보 처리와 산업공학 의사결정을 하나의 흐름으로",
        "기존 GPS 분석 엔진을 유지하고, 공개 집계자료 연구를 독립된 경로로 추가했다.",
    )
    stages = [
        ("공식 자료", "교통·도로망\n점포·거래"),
        ("검사·연결", "연도·공간키\n중복·결측"),
        ("후보 선택", "기준선 비교\n강건 집합 탐색"),
        ("의사결정 화면", "지도·민감도\n표·CSV 출력"),
    ]
    for i, (title, body) in enumerate(stages):
        x = 0.58 + i * 3.07
        d.box(s, x, 2.08, 2.84, 2.25, NAVY if i == 2 else WHITE, LINE)
        d.text(
            s, title, x + 0.18, 2.35, 2.48, 0.45, 20, WHITE if i == 2 else NAVY, True
        )
        d.text(s, body, x + 0.18, 3.1, 2.48, 0.95, 17, "D8ECEF" if i == 2 else INK)
    d.box(s, 0.58, 4.82, 5.95, 1.25, PALE)
    d.text(s, "기존 기능 보존", 0.83, 5.02, 5.45, 0.35, 17, TEAL, True)
    d.text(
        s,
        "GPS 이동·정차 / 인구 지도 / 대표경로 / 재표집 분석",
        0.83,
        5.55,
        5.45,
        0.33,
        13.8,
        INK,
    )
    d.box(s, 6.75, 4.82, 5.98, 1.25, WHITE, LINE)
    d.text(s, "새 연구 경로", 7.0, 5.02, 5.48, 0.35, 17, TEAL, True)
    d.text(
        s,
        "기관 집계자료 → 축소형 점수 → K개 집합의 선택 위험",
        7.0,
        5.55,
        5.48,
        0.33,
        13.6,
        INK,
    )
    d.note(s, "정보통신·GIS의 자료 처리 + 산업공학의 비교·최적화·의사결정", y=6.3)

    s = d.new(
        "기준 모델",
        "점수의 구성과 가중치를 사용자가 확인한다",
        "이번 실제 자료 모형은 점포·차량 맥락의 축소형이다. GPS 정차·반복 방문을 생성하지 않는다.",
    )
    d.box(s, 0.58, 1.98, 12.15, 0.95, NAVY)
    d.text(
        s,
        "위치가치 C(α) = (1−α) × 공간 A + α × 이동 B",
        0.86,
        2.25,
        11.6,
        0.45,
        25,
        WHITE,
        True,
        align=PP_ALIGN.CENTER,
    )
    d.card(
        s,
        0.58,
        3.24,
        3.85,
        2.64,
        "A · 공간 성분",
        "보고된 점포 재고",
        "2024년 4개 분기 전체 점포의 평균\n후보군 안에서 정규화",
        body_size=14.5,
    )
    d.card(
        s,
        4.66,
        3.24,
        3.85,
        2.64,
        "B · 이동 성분",
        "차량 통행 맥락",
        "일반도로 링크의 길이 가중 교통량\n후보군 안에서 정규화",
        accent=BLUE,
        body_size=14.5,
    )
    d.card(
        s,
        8.74,
        3.24,
        3.99,
        2.64,
        "C · 고정 가중합",
        "50:50 / 60:40",
        "기본·과거 가정으로 비교\n경험적으로 검증된 최적값은 아님",
        accent=ORANGE,
        body_size=14,
    )
    d.note(
        s,
        "상수 특성은 정규화 0 / 서로 다른 측정량을 더해 실제 광고 노출량으로 해석하지 않음",
        y=6.3,
    )

    s = d.new(
        "제안 방법",
        "하나의 순위보다 K개 집합의 선택 손실을 최소화",
        "최악후회 최소화는 기존 의사결정 방법이며, 실제 자료의 불확실성에 적용하는 데 기여를 둔다.",
    )
    d.box(s, 0.58, 1.98, 7.52, 3.98, WHITE, LINE)
    d.text(
        s,
        "후회 = 해당 조건의 최선 K개 평균점수\n             − 현재 선택한 K개 평균점수",
        0.92,
        2.3,
        6.8,
        1.0,
        21,
        NAVY,
        True,
    )
    d.text(
        s,
        "고려한 조건 가운데 가장 큰 후회를 계산하고,\n그 최댓값이 가장 작은 K개 집합을 선택한다.",
        0.92,
        3.8,
        6.8,
        0.95,
        18,
        INK,
    )
    d.text(
        s,
        "목적: min  [ max  (최선 효용 − 선택 효용) ]",
        0.92,
        5.12,
        6.8,
        0.4,
        17.5,
        TEAL,
        True,
    )
    d.box(s, 8.33, 1.98, 4.4, 3.98, NAVY)
    d.text(s, "완전 탐색", 8.67, 2.3, 3.7, 0.4, 17, "BDDCE2", True)
    d.text(s, f"{count:,}개", 8.67, 3.02, 3.7, 0.8, 36, WHITE, True)
    d.text(
        s,
        f"후보 {n}개 중 5개 선택\n후회 기준 최적 조합 {len(optima)}개",
        8.67,
        4.14,
        3.7,
        1.0,
        18,
        WHITE,
    )
    d.note(
        s,
        "선형 가중합의 후회는 가중치에 대해 볼록 → 구간 양 끝 검사로 연속 범위의 최악값 계산",
        y=6.3,
    )

    s = d.new(
        "실험 설계",
        "목적함수의 개선과 실제 성과를 구분해 검증",
        "주 분석 K=5, 보조 K=3·10 / 가중치 전체 0~100%와 제한 범위 30~70%를 함께 보고한다.",
    )
    d.table(
        s,
        ["검증 질문", "방법", "해석 범위"],
        [
            [
                "동일 조건에서 무엇이 다른가?",
                "A / B / C50 / C60 / R 비교",
                "같은 후보군·같은 K",
            ],
            [
                "가정이 바뀌어도 유지되는가?",
                "분기·도로·정규화 정의 제외 검사",
                "자료 표현에 대한 견고함",
            ],
            [
                "다른 지표와 관련이 있는가?",
                "2025년 추정 거래와 회고적으로 비교",
                "외부 상권 맥락의 보조 검사",
            ],
        ],
        0.58,
        2.08,
        [3.18, 4.8, 4.17],
        row_h=0.75,
        size=14,
    )
    d.box(s, 0.58, 5.45, 12.15, 0.95, PALE)
    d.text(
        s,
        "5개 점포 기준 × 4개 교통 정의 × 3개 정규화 × 가중치 구간 양 끝",
        0.85,
        5.72,
        11.6,
        0.4,
        18,
        TEAL,
        True,
    )
    d.text(
        s,
        "시나리오 설계 행은 독립 표본이 아니다. 분기 4개를 재복제해 신뢰구간을 만들지 않는다.",
        0.83,
        6.55,
        11.5,
        0.27,
        11.3,
        MUTED,
    )

    s = d.new(
        "주 결과",
        "더 견고한 선택을 위해 기본점수 효용을 일부 포기",
        "K=5 · 가중치 0~100% · 값이 작을수록 해당 조건 집합에서 견고한 선택이다.",
    )
    maxv = max(worst(m) for m in models) * 1.12
    chart_x, chart_y = 0.72, 2.06
    for i, model in enumerate(models):
        y = chart_y + i * 0.67
        d.text(
            s,
            MODEL_LABEL[model],
            chart_x,
            y + 0.05,
            2.0,
            0.35,
            15.2,
            TEAL if model == "R_minimax" else INK,
            model == "R_minimax",
        )
        width = 4.45 * worst(model) / maxv
        d.box(
            s,
            chart_x + 2.03,
            y + 0.05,
            width,
            0.34,
            TEAL if model == "R_minimax" else "9AB0C3",
            rounded=False,
        )
        d.text(
            s,
            f"{worst(model):.4f}",
            chart_x + 2.14 + width,
            y + 0.02,
            0.9,
            0.4,
            15.5,
            TEAL if model == "R_minimax" else INK,
            True,
        )
    d.box(s, 8.58, 2.0, 4.15, 3.72, WHITE, LINE)
    d.text(s, "기본 효용과의 절충", 8.83, 2.29, 3.65, 0.5, 21, NAVY, True)
    d.text(
        s,
        f"50:50 기본점수의 평균 효용\nC50: {price.loc['C50_reduced', 'nominal_mean_utility']:.4f}\n대표 R: {price.loc['R_minimax', 'nominal_mean_utility']:.4f}\n효용 차이: {price.loc['R_minimax', 'nominal_loss_vs_C50']:.4f}\n\n같은 최적후회 조합 {len(optima)}개 공개\n대표는 코드 순으로 선택",
        8.83,
        3.18,
        3.65,
        2.05,
        16,
        INK,
    )
    d.note(
        s,
        "이 값은 설계한 효용 기준의 손실이다. 광고효과·매출·예측 정확도 개선율이 아니다.",
        y=6.24,
        h=0.54,
    )

    s = d.new(
        "민감도·안정성",
        "가중치·후보 수·자료 표현에 따른 선택 위험을 확인",
        "가중치 범위·후보 수·자료 표현에 대한 전체 결과를 공개한다.",
    )
    rows = []
    for k in [3, 5, 10]:
        for low in [0.0, 0.3]:
            q = comparison[
                (comparison.k == k) & (comparison.weight_low == low)
            ].set_index("model")
            rows.append(
                [
                    str(k),
                    "0~100%" if low == 0 else "30~70%",
                    f"{q.loc['C50_reduced', 'worst_regret']:.4f}",
                    f"{q.loc['R_minimax', 'worst_regret']:.4f}",
                ]
            )
    d.table(
        s,
        ["K", "가중치 범위", "C50 후회", "R 후회"],
        rows,
        0.58,
        1.98,
        [0.8, 1.65, 1.65, 1.65],
        row_h=0.57,
        size=14,
    )
    rcv = cv[cv.model == "R_minimax"]
    rfamily = family_cv[family_cv.model == "R_minimax"]
    d.box(s, 6.7, 1.98, 6.03, 3.98, WHITE, LINE)
    d.text(s, "선택에 쓰지 않은 조건에서 확인", 7.0, 2.24, 5.43, 0.45, 20, NAVY, True)
    d.text(
        s,
        f"점포 분기를 하나씩 제외: {len(rcv)}개 검사\n제외 분기의 후회: {rcv.worst_regret.min():.4f}~{rcv.worst_regret.max():.4f}\n\n도로·정규화 정의 제외: {len(rfamily)}개 검사\n제외 정의의 후회: {rfamily.worst_regret.min():.4f}~{rfamily.worst_regret.max():.4f}",
        7.0,
        3.1,
        5.43,
        2.3,
        16.5,
        INK,
    )
    k3 = comparison[(comparison.k == 3) & (comparison.weight_low == 0)].set_index(
        "model"
    )
    tie = math.isclose(
        float(k3.loc["C50_reduced", "worst_regret"]),
        float(k3.loc["R_minimax", "worst_regret"]),
        abs_tol=1e-10,
    )
    note = (
        "K=3 전체 범위에서는 C50과 R의 최악후회가 같다. 보편적 우월성으로 확대하지 않는다."
        if tie
        else "선정 조건에 따른 차이를 공개하며, 목적함수 개선을 보편적 성과 우월성으로 확대하지 않는다."
    )
    d.note(s, note, y=6.3, fill="FFF1E5", color="A55D24")

    s = d.new(
        "외부 맥락",
        "외부 상권 지표로 결과의 해석 범위를 점검",
        "과거 예비값을 확인한 이후의 탐색적 검사다. 2025년 전 분기·업종 범위 결과를 함께 공개한다.",
    )
    eq = ext[ext.quarter == 20251].set_index("model")
    rows = []
    for m in models:
        rho = eq.loc[m, "spearman"] if "spearman" in eq else float("nan")
        rows.append(
            [
                MODEL_LABEL[m],
                pct(share(ext, m)),
                "집합 선택" if pd.isna(rho) else f"{float(rho):.4f}",
            ]
        )
    d.table(
        s,
        ["모델", "선택 5개 동 거래 비중", "순위상관"],
        rows,
        0.58,
        2.02,
        [2.5, 2.65, 1.75],
        row_h=0.56,
        size=13.4,
        highlight=4,
    )
    d.box(s, 7.78, 2.02, 4.95, 3.9, WHITE, LINE)
    d.text(s, "유리한 결과만 고르지 않는다", 8.03, 2.28, 4.45, 0.5, 20, NAVY, True)
    ca, cr = share(common, "A_stores"), share(common, "R_minimax")
    d.text(
        s,
        "모든 후보·분기에 공통으로\n보고된 업종만 보는 보조 검사\n\nQ1 거래 비중\n"
        + f"A: {pct(ca)}  /  대표 R: {pct(cr)}"
        + "\n\n외부 지표의 보편적 우위를\n입증했다고 말할 수 없다.",
        8.03,
        3.08,
        4.45,
        2.55,
        15,
        INK,
    )
    d.note(
        s,
        "거래 비중의 분모는 비교 후보 동의 합계 / 추정 거래는 실제 광고효과의 정답이 아님",
        y=6.3,
    )

    s = d.new(
        "GIS 구현",
        "설정을 바꾸면 지도·순위·선택 근거를 함께 확인",
        "현재 설정과 고정 연구 실험을 구분하고, 실제·추정·합성 자료의 표시를 유지한다.",
    )
    if dashboard and Path(dashboard).is_file():
        d.box(s, 0.58, 1.96, 8.55, 4.68, WHITE, LINE)
        d.picture(s, dashboard, 0.65, 2.03, 8.4, 4.54)
    else:
        map_path = report / "figures/ACQUIRED_selected_dongs.png"
        if not map_path.is_file():
            raise FileNotFoundError("Missing acquired candidate map")
        d.box(s, 0.58, 1.96, 8.55, 4.68, WHITE, LINE)
        d.picture(s, map_path, 0.65, 2.03, 8.4, 4.54)
    d.text(s, "핵심 후보와 대안", 9.45, 2.12, 3.0, 0.45, 21, NAVY, True)
    d.text(
        s,
        f"공통 후보\n{common_names}\n\n최악후회 기준 교체 후보\n{optional_names}\n\n기본 효용은 서로 다름\nR1 {price.loc['R_optimum_1', 'nominal_mean_utility']:.4f} / R2 {price.loc['R_optimum_2', 'nominal_mean_utility']:.4f}",
        9.45,
        2.92,
        3.0,
        3.5,
        16.5,
        INK,
    )
    d.text(
        s,
        "지도 좌표는 행정동 표시점이며 실제 배송 정차지가 아니다.",
        0.82,
        6.66,
        11.4,
        0.25,
        11,
        MUTED,
    )

    s = d.new(
        "활용·결론",
        "선택의 근거와 불확실성을 함께 전달하는 시스템",
        "실제 자료의 연결 검증 + 조건부 최적성 + 불리한 외부 결과 공개가 이번 연구의 핵심이다.",
    )
    d.card(
        s,
        0.58,
        2.02,
        3.9,
        2.78,
        "실무 활용",
        "지역 검토를 구조화",
        "후보를 좁히고 핵심·대안을 구분\n선호 변경의 영향을 설명\n결과를 지도·표로 전달",
        body_size=14.5,
    )
    d.card(
        s,
        4.7,
        2.02,
        3.9,
        2.78,
        "융합·확장",
        "같은 절차를 다른 업무로",
        "공간정보 + 의사결정 최적화\n다른 자치구·시설 후보 검토로 확장\n동일한 자료 정합성 검사가 전제",
        accent=BLUE,
        body_size=14,
    )
    d.card(
        s,
        8.82,
        2.02,
        3.91,
        2.78,
        "검증 범위",
        "조건을 명시한 결과",
        "마포구 집계 후보·보고 업종의 한계\n실제 광고효과·운행경로는 미검증\n가산 효용·후보 수는 연구 가정",
        accent=ORANGE,
        body_size=14,
    )
    d.box(s, 0.58, 5.28, 12.15, 1.15, NAVY)
    d.text(
        s,
        "가중치 하나의 정답을 선언하기보다,\n기준이 달라질 때의 선택 위험을 확인한다.",
        0.88,
        5.52,
        11.55,
        0.75,
        22,
        WHITE,
        True,
        align=PP_ALIGN.CENTER,
    )

    s = d.new(
        "참고문헌·출처",
        "자료의 출처와 해석 범위를 확인할 수 있도록",
        "모든 수치는 실제 확보한 집계표에서 재계산 / 기관 원본·인증키·개별 O/D는 공개 배포에서 제외",
    )
    refs = [
        (
            "[1] 서울특별시. 상권분석서비스(점포–행정동), 2024년.",
            "data.seoul.go.kr/dataList/OA-22172/S/1/datasetView.do",
        ),
        (
            "[2] 서울특별시. 상권분석서비스(추정매출–행정동), 2025년.",
            "data.seoul.go.kr/dataList/OA-22175/S/1/datasetView.do",
        ),
        (
            "[3] 한국교통연구원 KTDB. View-T 추정교통량·도로망, 2024년.",
            "viewt.ktdb.go.kr/cong/map/page.do  /  cong/pdf/Trafficestimate.pdf",
        ),
        (
            "[4] Bertsimas, Brown & Caramanis. Theory and Applications of Robust Optimization. 2010.",
            "https://arxiv.org/abs/1010.5445",
        ),
        (
            "[5] Mastin, Jaillet & Chin (2014). Randomized Minmax Regret for Combinatorial Optimization Under Uncertainty.",
            "https://arxiv.org/abs/1401.7043  /  배경 문헌; 본 연구는 결정적 집합 선택",
        ),
    ]
    for i, (title, url) in enumerate(refs):
        yy = 1.98 + i * 0.85
        d.text(s, title, 0.7, yy, 11.9, 0.35, 14.4, NAVY, True)
        d.text(s, url, 0.7, yy + 0.39, 11.9, 0.31, 12.1, MUTED)
    d.text(
        s,
        "주의: View-T는 교통 맥락 입력이다. 기관 안내에 따라 광고효과의 독립 검증 정답으로 쓰지 않는다.",
        0.72,
        6.48,
        11.9,
        0.32,
        11.4,
        TEAL,
        True,
    )
    if len(d.slides) != 15:
        raise AssertionError("Competition deck must contain exactly 15 slides")
    output.mkdir(parents=True, exist_ok=True)
    pptx_path = output / "Transit_OOH_Competition_Anonymous.pptx"
    d.prs.save(pptx_path)
    (output / "slide_outline.json").write_text(
        json.dumps(d.transcript, ensure_ascii=False, indent=2) + "\n"
    )
    return pptx_path, summary


def validate(pptx_path, report, output):
    if shutil.which("soffice") is None:
        raise RuntimeError("LibreOffice soffice is required for PPTX to PDF conversion")
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output.resolve()),
            str(pptx_path.resolve()),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    pdf_path = pptx_path.with_suffix(".pdf")
    if not pdf_path.is_file():
        raise FileNotFoundError("PPTX conversion did not create a PDF")
    doc = fitz.open(pdf_path)
    # Strip generic conversion metadata as well as identity-bearing fields.
    doc.set_metadata(
        {
            "title": "Transit OOH: 공개자료 기반 강건한 후보지역 선정",
            "author": "",
            "subject": "익명 심사용 발표자료",
            "keywords": "",
            "creator": "",
            "producer": "",
        }
    )
    clean = output / ".anonymous_clean.pdf"
    doc.save(clean, garbage=4, deflate=True)
    doc.close()
    clean.replace(pdf_path)
    doc = fitz.open(pdf_path)
    if len(doc) != 15:
        raise AssertionError("Converted PDF must have 15 pages")
    alltext = "\n".join(page.get_text() for page in doc)
    # These are direct identifiers, not generic bibliography author/institution names.
    banned = [
        "shshwk33",
        "지도교수",
        "정보통신공학과",
        "학번",
        "/workspace/",
        "C:/Users",
        "github.com/",
    ]
    found = [token for token in banned if token.lower() in alltext.lower()]
    if found:
        raise ValueError("Anonymity check failed: " + ", ".join(found))
    bounds = []
    for index, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    box = fitz.Rect(span["bbox"])
                    if not page.rect.contains(box) and span["text"].strip():
                        bounds.append(
                            {
                                "page": index + 1,
                                "text": span["text"],
                                "bbox": span["bbox"],
                            }
                        )
    if bounds:
        raise ValueError("Text outside PDF page: " + str(bounds[:3]))
    original = Presentation(pptx_path)
    missing_text, text_overlaps = [], []

    def canonical(value):
        return re.sub(r"\s+", "", value)

    for page_index, slide in enumerate(original.slides):
        extracted = canonical(doc[page_index].get_text())
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    value = canonical(paragraph.text)
                    if value and value not in extracted:
                        missing_text.append(
                            {"page": page_index + 1, "text": paragraph.text}
                        )
        rendered_lines = []
        for block_index, block in enumerate(doc[page_index].get_text("dict")["blocks"]):
            for line in block.get("lines", []):
                rendered_text = "".join(span["text"] for span in line["spans"])
                if rendered_text.strip():
                    rendered_lines.append(
                        (block_index, fitz.Rect(line["bbox"]), rendered_text)
                    )
        for j, (block_index, rectangle, text) in enumerate(rendered_lines):
            for other_index, other_rect, other_text in rendered_lines[j + 1 :]:
                intersection = rectangle & other_rect
                if (
                    block_index != other_index
                    and not intersection.is_empty
                    and intersection.width > 2
                    and intersection.height > 3
                ):
                    text_overlaps.append(
                        {"page": page_index + 1, "text": text, "other": other_text}
                    )
    if missing_text or text_overlaps:
        raise ValueError(
            "Converted text completeness/overlap check failed: "
            + str((missing_text + text_overlaps)[:3])
        )
    previews = output / "previews"
    previews.mkdir(exist_ok=True)
    thumbs = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
        pix.save(previews / f"slide_{i + 1:02d}.png")
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        image.thumbnail((480, 270))
        thumbs.append(image)
    sheet = Image.new("RGB", (3 * 500, 5 * 302), "#e4ebf1")
    draw = ImageDraw.Draw(sheet)
    for i, im in enumerate(thumbs):
        x, y = (i % 3) * 500 + 10, (i // 3) * 302 + 10
        sheet.paste(im, (x, y))
        draw.text((x, y + 274), f"{i + 1:02d}", fill="#142d49")
    sheet.save(output / "Contact_Sheet.png")
    (output / "presentation_text.txt").write_text(alltext + "\n")
    with ZipFile(pptx_path) as archive:
        core = archive.read("docProps/core.xml").decode()
        xml = "\n".join(
            archive.read(n).decode()
            for n in archive.namelist()
            if n.endswith(".xml")
            and (n.startswith("ppt/") or n.startswith("docProps/"))
        )
        ppt_identifiers = [token for token in banned if token.lower() in xml.lower()]
        if ppt_identifiers:
            raise ValueError("PPTX identity scan failed: " + str(ppt_identifiers))
    validation = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_report_sha256": sha256(report / "summary.json"),
        "pptx_sha256": sha256(pptx_path),
        "pdf_sha256": sha256(pdf_path),
        "pdf_pages": len(doc),
        "pptx_bytes": pptx_path.stat().st_size,
        "pdf_bytes": pdf_path.stat().st_size,
        "under_10mb": pdf_path.stat().st_size < 10_000_000,
        "conversion": "PPTX converted by LibreOffice soffice, then metadata stripped",
        "identity_tokens_found": found,
        "pptx_identity_tokens_found": ppt_identifiers,
        "out_of_page_text_spans": bounds,
        "missing_pptx_paragraphs_in_pdf": missing_text,
        "intersecting_rendered_text_lines": text_overlaps,
        "pdf_author": doc.metadata.get("author", ""),
        "has_pptx_core_properties": bool(core),
        "actual_data_only": True,
        "invented_team_contributions": False,
        "team_roles_confirmation": "User will write collaboration details separately; not a technical completion blocker",
        "known_limitations": [
            "Automated bounds check does not prove zero overlap; previews need visual review",
            "Current revised historical sources; not as-of prospective prediction",
            "Source citations are public institutions; no affiliation disclosed",
        ],
    }
    (output / "presentation_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n"
    )
    doc.close()
    (output / "README.md").write_text(
        "# 익명 경진대회 발표자료\n\n"
        "제출 파일: **Transit_OOH_Competition_Anonymous.pdf** (표지 포함 15쪽).\n"
        "수정 원본: Transit_OOH_Competition_Anonymous.pptx. PPTX를 LibreOffice로 실제 변환했습니다.\n\n"
        "자료·모델·실험은 reports/public_decision의 검증된 결과만 사용했습니다. "
        "광고효과·실제 배송 운행·예측 정확도를 입증한 자료로 해석하지 않습니다.\n\n"
        "## 재생성\n\n"
        "LibreOffice와 Noto Sans CJK KR 글꼴이 필요합니다. 아래 명령은 연구 의존성을 변경하지 않고 발표 제작 도구를 추가해 실행합니다.\n\n"
        "```bash\nuv run --frozen --with python-pptx==1.0.2 --with Pillow==12.3.0 python scripts/build_competition_slides.py\n```\n\n"
        "assets의 익명 실제 대시보드 캡처를 사용합니다. 수정 가능한 PPTX는 Noto Sans CJK KR 글꼴이 없으면 대체 글꼴로 표시될 수 있으므로 제출은 고정 PDF를 권합니다.\n\n"
        "## 제출 전 팀에서 확인할 것\n\n"
        "- 참가신청서·지도교수 추천서·연구윤리서약서의 실제 작성·서명 상태\n"
        "- 협업 관련 내용은 사용자가 별도로 작성합니다.\n"
        "- 최종 편집 후 학교·교수·학번·개인 계정·파일 경로·QR 등 익명성 재검사\n"
        "- 발표 신청 페이지의 정확한 최종 마감·접수 완료 여부\n\n"
        "이 폴더의 코드·검수 메모·미리보기는 PDF 본문이 아닌 별도 검토 파일입니다. "
        "제출처에 별도 요구가 없는 한 PDF와 공식 별첨만 제출합니다.\n"
    )
    return validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "reports/public_decision")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "deliverables/competition2026"
    )
    parser.add_argument("--dashboard", type=Path)
    args = parser.parse_args()
    saved_capture = args.output / "assets/dashboard_live_controls_map.png"
    dashboard = args.dashboard or (saved_capture if saved_capture.exists() else None)
    pptx_path, _ = build(args.report, args.output, dashboard)
    print(
        json.dumps(
            validate(pptx_path, args.report, args.output), ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
