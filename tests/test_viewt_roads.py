"""Synthetic provider-layout fixtures test errors; no fixture is research data."""

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import pytest
from openpyxl import Workbook
from shapely.geometry import LineString
from streamlit.testing.v1 import AppTest

from transit_ooh.viewt_roads import (
    attach_network,
    combine_roads,
    export_context,
    load_context,
    read_official_excel,
)


def provider_file(
    kind,
    *,
    year=2024,
    day="평일",
    region="서울특별시 마포구",
    ids=("1001", "1002"),
    hourly=False,
    cell=None,
):
    book = Workbook()
    sheet = book.active
    title = "추정교통량" if kind == "traffic" else "평균속도"
    for value in [
        f"{title}(도로구간)",
        f"- 기준년도 : {year}년",
        f"- 기간 : {day}",
        f"- 권역범위 : {region} / 읍면동",
        "- 도로등급 : 시군도",
    ]:
        sheet.append([value])
    classes = ["전체", "승용차", "버스", "트럭"] if kind == "traffic" else ["전체"]
    sheet.append(
        [
            "5.5 LINK ID",
            "ITS LINK ID",
            "도로등급",
            "도로명",
            "권역",
            "연장(km)",
            "차선수",
            *[f"{v}-{day}" for v in classes],
        ]
    )
    sheet.append([None] * 7 + ["7시~8시" if hourly else "연평균 일"] * len(classes))
    for i, link in enumerate(ids):
        values = [100 + i, 70 + i, 10, 20] if kind == "traffic" else [25 + i]
        sheet.append(
            [link, f"900{i}", "시군도", "테스트 도로", region, 0.5, 2, *values]
        )
    if cell:
        sheet[cell[0]] = cell[1]
    stream = BytesIO()
    book.save(stream)
    # The real provider files incorrectly declare A1:A1, hiding rows in read-only mode.
    fixed = BytesIO()
    with (
        zipfile.ZipFile(BytesIO(stream.getvalue())) as original,
        zipfile.ZipFile(fixed, "w") as out,
    ):
        for item in original.infolist():
            data = original.read(item)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = re.sub(
                    rb'<dimension ref="[^"]+"', b'<dimension ref="A1:A1"', data
                )
            out.writestr(item, data)
    return fixed.getvalue()


@pytest.fixture
def context():
    return combine_roads(
        read_official_excel(provider_file("traffic"), "traffic"),
        read_official_excel(provider_file("speed"), "speed"),
    )


def network_zip(tmp_path, ids=(1001, 1002)):
    directory = tmp_path / "shape"
    directory.mkdir(exist_ok=True)
    frame = gpd.GeoDataFrame(
        {"k_link_id": ids},
        geometry=[
            LineString([(126.90 + i * 0.01, 37.55), (126.91 + i * 0.01, 37.56)])
            for i in range(len(ids))
        ],
        crs="EPSG:4326",
    ).to_crs("EPSG:5179")
    frame.to_file(directory / "roads.shp", encoding="cp949")
    output = tmp_path / "roads.zip"
    with zipfile.ZipFile(output, "w") as z:
        for f in directory.iterdir():
            z.write(f, f.name)
    return output


def test_wrong_dimensions_keep_all_rows_and_leading_zero_ids():
    result = read_official_excel(
        provider_file("traffic", ids=("001001", "001002")), "traffic"
    )
    assert result.table.link_id.tolist() == ["001001", "001002"]
    assert result.metadata["declared_dimensions"] == "A1:A1"
    assert result.metadata["statistic"] == "annual_average_day"


@pytest.mark.parametrize(
    "change",
    [
        dict(year=2023),
        dict(day="주말"),
        dict(region="서울특별시 강남구"),
        dict(ids=("1001", "1003")),
    ],
)
def test_different_year_period_region_or_coverage_cannot_join(change):
    traffic = read_official_excel(provider_file("traffic"), "traffic")
    speed = read_official_excel(provider_file("speed", **change), "speed")
    with pytest.raises(ValueError, match=r"Incompatible|ID sets differ"):
        combine_roads(traffic, speed)


@pytest.mark.parametrize(
    "change,error",
    [
        (dict(hourly=True), "annual-average"),
        (dict(ids=("1001", "1001")), "Duplicate"),
        (dict(ids=("1.0", "1002")), "digit strings"),
        (dict(ids=(-1, 1002)), "exact integers"),
        (dict(cell=("H8", None)), "missing cells"),
        (dict(cell=("H8", -1)), "negative"),
        (dict(cell=("H8", 300)), "class total"),
        (dict(cell=("E8", "서울특별시 강남구")), "District"),
    ],
)
def test_ambiguous_or_invalid_values_do_not_become_zero(change, error):
    with pytest.raises(ValueError, match=error):
        read_official_excel(provider_file("traffic", **change), "traffic")


def test_wrong_or_corrupt_files_are_rejected():
    with pytest.raises(ValueError, match="Invalid XLSX"):
        read_official_excel(b"not an xlsx", "traffic")
    with pytest.raises(ValueError, match="Expected official"):
        read_official_excel(provider_file("speed"), "traffic")


def test_road_attribute_mismatch_rejected():
    traffic = read_official_excel(provider_file("traffic"), "traffic")
    speed = read_official_excel(provider_file("speed", cell=("F8", 0.8)), "speed")
    with pytest.raises(ValueError, match="attributes disagree"):
        combine_roads(traffic, speed)


def test_geometry_join_crs_and_roundtrip_preserve_context(context, tmp_path):
    output = tmp_path / "output"
    export_context(context, output, network_zip(tmp_path), 2024)
    restored, geometry = load_context(output)
    assert len(geometry["features"]) == 2
    coordinate = geometry["features"][0]["geometry"]["coordinates"][0]
    assert coordinate == pytest.approx([126.90, 37.55], abs=1e-7)
    assert restored.table.trucks_per_day.tolist() == [20, 20]
    assert restored.table.all_vehicles_per_day.tolist() == [100, 101]
    assert restored.metadata["network"]["boundary_overlay"] == "none"
    assert "daily_bootstrap" in restored.metadata["unavailable_outputs"]
    assert "integrated_score" not in restored.table
    assert "date" not in restored.table
    export_context(context, output)  # Old geometry must not survive a table-only run.
    assert not (output / "roads.geojson").exists()
    assert load_context(output)[1] is None


def test_mismatched_network_has_no_partial_outputs(context, tmp_path):
    output = tmp_path / "output"
    archive = network_zip(tmp_path, ids=(1001, 1003))
    with pytest.raises(ValueError, match="reference year"):
        export_context(context, output, archive, 2023)
    with pytest.raises(ValueError, match="no network geometry"):
        export_context(context, output, archive, 2024)
    assert not output.exists()


@pytest.mark.parametrize("filename", ["roads.csv", "roads.geojson"])
def test_changed_artifact_requires_revalidation(context, tmp_path, filename):
    export_context(context, tmp_path / "output", network_zip(tmp_path), 2024)
    artifact = tmp_path / "output" / filename
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_context(artifact.parent)


def test_ui_official_mode_and_metric_updates_without_synthetic_fallback(
    context, tmp_path
):
    geometry, _ = attach_network(context, network_zip(tmp_path), 2024)
    export_context(context, tmp_path / "input")
    fixture_app = tmp_path / "app.py"
    app_directory = Path(__file__).resolve().parents[1] / "app"
    fixture_app.write_text(
        f"import sys\nsys.path.insert(0, {str(app_directory)!r})\n"
        "import viewt_roads_page as page\nfrom pathlib import Path\n"
        "original = page.LOCAL\ntry:\n"
        f"    page.LOCAL = Path({str(tmp_path / 'input')!r})\n    page.render()\n"
        "finally:\n    page.LOCAL = original\n"
    )
    at = AppTest.from_file(fixture_app).run()
    assert not at.exception
    assert at.metric[0].value == "2개"
    assert "SYNTHETIC" not in " ".join(w.value for w in at.warning)
    at.selectbox(key="official_road_metric").set_value("평균속도 (km/h)").run()
    assert not at.exception
    assert at.dataframe[0].value.speed_kmh.tolist() == [26, 25]
    at.radio(key="official_roads_source").set_value("Excel 직접 업로드").run()
    assert not at.exception and len(at.metric) == 0 and len(at.dataframe) == 0
    assert any("두 공식 파일" in w.value for w in at.warning)
    # Geometry can be serialized without NaN and includes selected metrics.
    assert (
        json.loads(json.dumps(geometry, allow_nan=False))["features"][0]["properties"][
            "trucks_per_day"
        ]
        == 20
    )
