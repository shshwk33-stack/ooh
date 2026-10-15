"""Synthetic contract fixtures, kept separate from acquired research inputs."""

import copy
import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from transit_ooh.viewt_client import ViewTClient
from transit_ooh.viewt_population import (
    aggregation_check,
    combine_inflow_batches,
    daily_inflow_panel,
    export_population,
    load_population,
    normalize_response,
    population_rank_stability,
    read_download,
)
from transit_ooh.viewt_routes import normalize_routes


@pytest.fixture
def query():
    return {
        "year": 2024,
        "dayTerm": "20241202,20241203",
        "daysCnt": 2,
        "zone": "11140000",
        "trafficType": "In",
        "zoneType": "2",
        "subZoneType": "0",
        "subZone": 0,
        "displayResult": "2",
        "sexs": "1,2",
        "times": "0-23/0-23",
        "trips": "all",
        "ages": "all",
    }


@pytest.fixture
def payload():
    def row(zone, value):
        return {
            "zone": zone,
            "V": value,
            "SX": 37.56,
            "SY": 126.92,
            "EX": 37.55,
            "EY": 126.91,
        }

    total = [row("11130000-11140000", 120), row("11140000-11140000", 80)]
    average = [row("11130000-11140000", 60), row("11140000-11140000", 40)]
    return {"all": [[total, average, [row("11130000-11140000", 99999)]]]}


def test_total_mean_and_density_are_not_added(payload, query):
    frame, meta = normalize_response(payload, query, "inflow")
    assert frame.period_trips.sum() == 200
    assert frame.mean_daily_trips.sum() == 100
    assert frame.internal_same_zone.sum() == 1
    assert frame.origin_latitude.iloc[0] == 37.56
    assert frame.origin_longitude.iloc[0] == 126.92
    assert meta["observation_type"] == "estimated"
    assert "daily coverage" in meta["coverage"]


@pytest.mark.parametrize(
    "change,error",
    [
        ({"daysCnt": 3}, "day count"),
        ({"year": 2023}, "year mismatch"),
        ({"dayTerm": "20241202,20241202"}, "repeated"),
        ({"zone": "11130000"}, "destination differs"),
        ({"trafficType": "Out"}, "inflow only"),
    ],
)
def test_query_coverage_mismatch_rejected(payload, query, change, error):
    query.update(change)
    with pytest.raises(ValueError, match=error):
        normalize_response(payload, query, "inflow")


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("average", "provider average"),
        ("missing", "coverage differ"),
        ("duplicate", "Repeated"),
        ("negative", "Negative"),
        ("axis", "latitude"),
        ("empty", "Empty"),
        ("denied", "Empty"),
    ],
)
def test_bad_response_not_silently_repaired(payload, query, mutation, error):
    if mutation == "average":
        payload["all"][0][1][0]["V"] = 61
    elif mutation == "missing":
        payload["all"][0][1].pop()
    elif mutation == "duplicate":
        payload["all"][0][0].append(payload["all"][0][0][0])
    elif mutation == "negative":
        payload["all"][0][0][0]["V"] = -1
    elif mutation == "axis":
        payload["all"][0][0][0]["SX"] = 126.92
    elif mutation == "empty":
        payload["all"] = []
    else:
        payload["all"] = "LoginError"
    with pytest.raises(ValueError, match=error):
        normalize_response(payload, query, "inflow")


def test_different_spatial_units_do_not_imply_no_internal_flow(payload, query):
    query.update(zoneType="3", zone="11140660")
    for rows in payload["all"][0][:2]:
        for row in rows:
            row["zone"] = row["zone"].split("-")[0] + "-11140660"
    frame, meta = normalize_response(payload, query, "inflow")
    assert frame.internal_same_zone.isna().all()
    assert meta["origin_unit"] != meta["destination_unit"]


def test_overlapping_or_different_batch_queries_rejected(payload, query):
    frame, meta = normalize_response(payload, query, "inflow")
    with pytest.raises(ValueError, match="overlapping"):
        combine_inflow_batches([("a", frame, meta), ("b", frame, meta)])
    other = copy.deepcopy(payload)
    other_query = {**query, "zone": "11130000", "sexs": "1"}
    for rows in other["all"][0][:2]:
        for row in rows:
            row["zone"] = row["zone"].split("-")[0] + "-11130000"
    second, second_meta = normalize_response(other, other_query, "inflow")
    with pytest.raises(ValueError, match="query conditions"):
        combine_inflow_batches([("a", frame, meta), ("b", second, second_meta)])


def test_aggregation_check_never_fills_absent_origins(payload, query):
    frame, _ = normalize_response(payload, query, "inflow")
    with pytest.raises(ValueError, match="origins differ"):
        aggregation_check(frame, frame.iloc[:1])
    assert aggregation_check(frame, frame)["max_origin_difference"] == 0


def test_directed_od_uses_total_and_mean_not_reciprocal_sum(payload, query):
    total = [payload["all"][0][0][0]]
    avg = [payload["all"][0][1][0]]
    response = {
        "all": [
            [{}],
            total,
            [120],
            [{**total[0], "V": 999}],
            [999],
            avg,
            [60],
            [{**avg[0], "V": 499.5}],
            [499.5],
        ]
    }
    query.update(LineType="OOD", drawlimits=10000, displayResult="3")
    frame, _ = normalize_response(response, query, "od")
    assert frame.period_trips.sum() == 120
    query["drawlimits"] = 1
    with pytest.raises(ValueError, match="provider cap"):
        normalize_response(response, query, "od")


def test_files_checksums_and_missing_ui_state(payload, query, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "zone_names_2024.json").write_text(
        json.dumps(
            {
                "shpMap": {
                    "11130000": "서울특별시 서대문구",
                    "11140000": "서울특별시 마포구",
                }
            }
        )
    )
    (raw / "mapo_inflow_test.json").write_text(json.dumps(payload))
    (raw / "mapo_inflow_test.request.json").write_text(json.dumps(query))
    assert len(read_download(raw / "mapo_inflow_test.json", "inflow")[0]) == 2
    output = tmp_path / "output"
    export_population(raw, output)
    restored = load_population(output)[0][1]
    assert restored.within_mapo.sum() == 1
    (output / "mapo_inflow_test.csv").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        load_population(output)
    script = tmp_path / "page.py"
    app = Path(__file__).resolve().parents[1] / "app"
    script.write_text(
        f"import sys\nsys.path.insert(0,{str(app)!r})\nimport viewt_population_page as page\nfrom pathlib import Path\noriginal=page.LOCAL\ntry:\n    page.LOCAL=Path({str(tmp_path / 'absent')!r})\n    page.render()\nfinally:\n    page.LOCAL=original\n"
    )
    at = AppTest.from_file(script).run()
    assert not at.exception and not at.metric
    assert any("아직 없습니다" in w.value for w in at.warning)


def test_client_requires_success_without_echoing_provider_response(monkeypatch):
    client = ViewTClient()
    with pytest.raises(RuntimeError, match="Authenticate"):
        client.fetch("names", {"year": 2024})
    monkeypatch.setattr(
        client,
        "_request",
        lambda *a, **kw: json.dumps({"tokenKey": "SUCCESS"}).encode(),
    )
    client.authenticate("synthetic-test-credential")
    assert client.authenticated
    monkeypatch.setattr(
        client,
        "_request",
        lambda *a, **kw: json.dumps(
            {"tokenKey": "ENDDATE", "untrusted_echo": "sensitive_echo"}
        ).encode(),
    )
    with pytest.raises(RuntimeError, match="expired") as error:
        client.authenticate("synthetic-test-credential")
    assert not client.authenticated and "sensitive_echo" not in str(error.value)


def test_route_percentage_and_sequence_contract():
    query = {"DPRTR_ZONEID": "11140740", "ARRIVE_ZONEID": "11140680", "YEAR": 2024}
    result = {
        "STATE": 200,
        "CNT": 1,
        "DPRTR_ZONEID": 11140740,
        "ARRIVE_ZONEID": 11140680,
        "RESULT": [
            {
                "RANK": 1,
                "VALUE": 70,
                "CNT": 2,
                "LINKS": [{"LINKID": 1001, "ORDER": 0}, {"LINKID": 1002, "ORDER": 1}],
            }
        ],
    }
    table = normalize_routes(result, query)
    assert table.share_percent.tolist() == [70, 70]
    assert "vehicle_flow" not in table and "speed" not in table
    broken = copy.deepcopy(result)
    broken["RESULT"][0]["VALUE"] = 101
    with pytest.raises(ValueError, match="percentage"):
        normalize_routes(broken, query)
    broken = copy.deepcopy(result)
    broken["RESULT"][0]["LINKS"][1]["ORDER"] = 0
    with pytest.raises(ValueError, match="sequence"):
        normalize_routes(broken, query)
    result["DPRTR_ZONEID"] = 11140770
    with pytest.raises(ValueError, match="differs"):
        normalize_routes(result, query)


def test_daily_panel_rejects_annual_replication_and_incomplete_dates(payload, query):
    frame, meta = normalize_response(payload, query, "inflow")
    with pytest.raises(ValueError, match="single-date"):
        daily_inflow_panel([("period", frame, meta)], {"11140000"})
    query.update(zoneType="3", zone="11140660", dayTerm="20241202/20241202", daysCnt=1)
    for metric in payload["all"][0][:2]:
        for row in metric:
            row["zone"] = row["zone"].split("-")[0] + "-11140660"
    for row in payload["all"][0][1]:
        row["V"] *= 2
    frame, meta = normalize_response(payload, query, "inflow")
    with pytest.raises(ValueError, match="Incomplete destination"):
        daily_inflow_panel([("day", frame, meta)], {"11140660", "11140740"})


@pytest.fixture
def daily_panel():
    dates = pd.bdate_range("2024-12-02", periods=20)
    return pd.DataFrame(
        [
            {
                "date": str(day.date()),
                "destination_id": f"11140{i:03}",
                "reported_trips": 1000
                - i * 20
                + ((d % 5) * 20 if i % 2 else -(d % 5) * 20),
            }
            for d, day in enumerate(dates)
            for i in range(16)
        ]
    )


def test_paired_bootstrap_conserves_topk_and_week_blocks(daily_panel):
    day, day_draws = population_rank_stability(daily_panel, cluster="day", n=40)
    week, week_draws = population_rank_stability(daily_panel, cluster="week", n=40)
    for result in [day, week]:
        assert result.top5_probability.sum() == pytest.approx(5)
        assert result.top10_probability.sum() == pytest.approx(10)
        assert (result.mean_p975 >= result.mean_p025).all()
    assert day.resampling_units.eq(20).all()
    assert week.resampling_units.eq(4).all()
    assert day_draws.unique_dates.lt(20).any()
    for encoded in week_draws.drawn_dates:
        counts = pd.Series(json.loads(encoded)).value_counts()
        for _, group in counts.groupby(pd.to_datetime(counts.index).to_period("W-SUN")):
            assert len(group) == 5 and group.nunique() == 1


@pytest.mark.parametrize("problem", ["missing", "duplicate", "negative"])
def test_daily_stability_rejects_incomplete_or_invalid_panel(daily_panel, problem):
    if problem == "missing":
        daily_panel = daily_panel.iloc[1:]
    elif problem == "duplicate":
        daily_panel = pd.concat([daily_panel, daily_panel.head(1)])
    else:
        daily_panel.loc[0, "reported_trips"] = -1
    with pytest.raises(ValueError):
        population_rank_stability(daily_panel, n=20)


def test_only_transient_http_errors_are_retried(monkeypatch):
    from transit_ooh.viewt_client import ViewTHTTPError

    client = ViewTClient()
    client.authenticated = True
    waits = []
    monkeypatch.setattr("transit_ooh.viewt_client.time.sleep", waits.append)
    calls = []

    def transient(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ViewTHTTPError(503)
        return b'{"shpMap": {"11140000": "Mapo"}}'

    monkeypatch.setattr(client, "_request", transient)
    assert json.loads(client.fetch("names", {"year": 2024}))["shpMap"]
    assert len(calls) == 2 and waits == [5]

    def forbidden(*args, **kwargs):
        raise ViewTHTTPError(403)

    monkeypatch.setattr(client, "_request", forbidden)
    with pytest.raises(ViewTHTTPError):
        client.fetch("names", {"year": 2024})
    assert waits == [5]


def test_empty_response_can_be_recorded_but_permission_errors_cannot_be_skipped(
    monkeypatch,
):
    from transit_ooh.viewt_client import ViewTNoDataError

    client = ViewTClient()
    client.authenticated = True
    monkeypatch.setattr(client, "_request", lambda *a, **kw: b'{"all":[]}')
    with pytest.raises(ViewTNoDataError) as error:
        client.fetch("inflow", {})
    assert json.loads(error.value.raw) == {"all": []}
    monkeypatch.setattr(client, "_request", lambda *a, **kw: b'{"all":"LoginError"}')
    with pytest.raises(ValueError) as error:
        client.fetch("inflow", {})
    assert not isinstance(error.value, ViewTNoDataError)
