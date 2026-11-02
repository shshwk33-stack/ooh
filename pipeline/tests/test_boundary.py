"""Exercise the pipeline contract without modifying the source dataset.

These fixtures test geometry handling, not Transit OOH research outcomes. The
historical boundary dataset is never interpreted as GPS or a scored result.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pipeline.boundary import PipelineError, run_pipeline


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "public/data/seoul-districts-2013.geojson"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_metadata(path: Path) -> dict:
    return {
        "schema_version": "1.0",
        "dataset_kind": "administrative_boundary",
        "geometry_only": True,
        "source": {
            "kind": "PUBLIC_AGGREGATE",
            "name": "Seoul district boundaries 2013",
            "publisher": "KOSTAT / southkorea/seoul-maps",
            "url": "https://github.com/southkorea/seoul-maps",
            "reference_year": 2013,
            "sha256": sha256(path),
            "license": "UNKNOWN",
        },
        "spatial": {
            "input_crs": "EPSG:4326",
            "coordinate_order": "longitude_latitude",
            "analysis_crs": "EPSG:5179",
            "crs_basis": "Processing input contract: longitude/latitude; no CRS member in original file.",
        },
    }


class BoundaryPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_bytes = SOURCE.read_bytes()
        cls.dataset = json.loads(cls.original_bytes)

    @classmethod
    def tearDownClass(cls):
        if SOURCE.read_bytes() != cls.original_bytes:
            raise AssertionError("The repository source dataset was modified")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="atlas-boundary-test-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.input = self.directory / "input.geojson"
        self.metadata = self.directory / "source.metadata.json"
        self.output = self.directory / "result"
        self.write_fixture(copy.deepcopy(self.dataset))

    def write_fixture(self, data, metadata=None):
        self.input.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.write_metadata(metadata or valid_metadata(self.input))

    def write_metadata(self, metadata):
        self.metadata.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    def execute(self, output=None, region_code="11140"):
        before = (self.input.read_bytes(), self.metadata.read_bytes())
        try:
            return run_pipeline(self.input, self.metadata, output or self.output, region_code)
        finally:
            self.assertEqual(before, (self.input.read_bytes(), self.metadata.read_bytes()))

    def failed_fixture(self, data=None, metadata=None, region_code="11140"):
        if data is not None:
            self.write_fixture(data, metadata)
        elif metadata is not None:
            self.write_metadata(metadata)
        with self.assertRaises(PipelineError):
            self.execute(region_code=region_code)
        report_path = self.output / "quality_report.json"
        self.assertTrue(report_path.is_file(), "Rejected data must produce a quality report")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["errors"])
        self.assertTrue(all(error.get("code") and error.get("message") for error in report["errors"]))
        self.assertTrue((self.output / "processing_log.jsonl").is_file())
        for name in ("mapo.geojson", "districts.csv", "mapo.projected.csv", "run_manifest.json"):
            self.assertFalse((self.output / name).exists(), "Failed runs must not leave usable results")
        return report

    def test_actual_dataset_contains_25_districts_and_extracts_mapo(self):
        manifest = self.execute()
        report = json.loads((self.output / "quality_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["feature_count"], 25)
        selected = json.loads((self.output / "mapo.geojson").read_text(encoding="utf-8"))
        self.assertEqual(selected["type"], "FeatureCollection")
        self.assertEqual(len(selected["features"]), 1)
        self.assertEqual(selected["features"][0]["properties"]["code"], "11140")
        self.assertEqual(selected["features"][0]["properties"]["name"], "마포구")
        source_geometry = next(feature["geometry"] for feature in self.dataset["features"] if feature["properties"]["code"] == "11140")
        output_geometry = selected["features"][0]["geometry"]
        self.assertEqual(output_geometry["type"], source_geometry["type"])
        self.assertEqual(len(output_geometry["coordinates"]), len(source_geometry["coordinates"]))
        # RFC 7946 winding normalization may reverse a ring. Vertices and their
        # sequence must otherwise remain unchanged; topology repair is disallowed.
        for original_ring, output_ring in zip(source_geometry["coordinates"], output_geometry["coordinates"]):
            self.assertIn(output_ring, [original_ring, list(reversed(original_ring))])
        self.assertEqual(manifest["output_kind"], "DERIVED")
        self.assertEqual(manifest["source"]["kind"], "PUBLIC_AGGREGATE")
        self.assertEqual(manifest["source"]["sha256"], sha256(self.input))
        self.assertTrue(manifest["geometry_only"])
        self.assertFalse(manifest["analysis_scores_generated"])
        self.assertEqual(selected["provenance"]["output_kind"], "DERIVED")
        self.assertEqual(selected["provenance"]["source_kind"], "PUBLIC_AGGREGATE")
        self.assertEqual(selected["provenance"]["source_sha256"], sha256(self.input))

    def test_metric_geometry_is_plausible_and_consistent_across_outputs(self):
        self.execute()
        with (self.output / "districts.csv").open(encoding="utf-8-sig", newline="") as stream:
            districts = list(csv.DictReader(stream))
        self.assertEqual(len(districts), 25)
        self.assertEqual([row["code"] for row in districts], sorted(row["code"] for row in districts))
        with (self.output / "mapo.projected.csv").open(encoding="utf-8-sig", newline="") as stream:
            projected = list(csv.DictReader(stream))
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["crs"], "EPSG:5179")
        area = float(projected[0]["area_m2"])
        perimeter = float(projected[0]["perimeter_m"])
        # Broad plausibility gates catch degree-based or km/m unit mistakes.
        # These bounds do not assert agreement with an official district area.
        self.assertGreater(area, 10_000_000)
        self.assertLess(area, 40_000_000)
        self.assertGreater(perimeter, 10_000)
        self.assertLess(perimeter, 100_000)
        matching = next(row for row in districts if row["code"] == "11140")
        self.assertAlmostEqual(float(matching["area_m2"]), area, delta=0.01)
        self.assertAlmostEqual(float(matching["perimeter_m"]), perimeter, delta=0.01)

    def test_pipeline_projection_matches_known_points_and_roundtrips(self):
        from pyproj import Transformer
        from shapely import wkt

        points = [[126.978, 37.5665], [127.5, 38.0], [127.5, 37.5], [126.978, 37.5665]]
        data = {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "properties": {"code": "11140", "name": "좌표 변환 검증", "name_eng": "Projection check", "base_year": "2013"},
            "geometry": {"type": "Polygon", "coordinates": [points]},
        }]}
        self.write_fixture(data)
        self.execute()
        with (self.output / "mapo.projected.csv").open(encoding="utf-8-sig", newline="") as stream:
            row = next(csv.DictReader(stream))
        projected = list(wkt.loads(row["geometry_wkt"]).exterior.coords)
        self.assertAlmostEqual(projected[0][0], 953901.165, delta=2.0)
        self.assertAlmostEqual(projected[0][1], 1952032.081, delta=2.0)
        self.assertAlmostEqual(projected[1][0], 1_000_000, delta=0.01)
        self.assertAlmostEqual(projected[1][1], 2_000_000, delta=0.01)
        inverse = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
        self.assertEqual(len(points), len(projected))
        for expected, converted in zip(points, projected):
            actual = inverse.transform(*converted)
            self.assertAlmostEqual(expected[0], actual[0], delta=1e-8)
            self.assertAlmostEqual(expected[1], actual[1], delta=1e-8)

    def test_identical_inputs_produce_same_run_id_and_result_bytes(self):
        first = self.execute()
        other = self.directory / "second-result"
        second = self.execute(output=other)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first, second)
        for name, expected_hash in first["outputs"].items():
            self.assertEqual(sha256(self.output / name), expected_hash)
        files = sorted(path.name for path in self.output.iterdir() if path.is_file() and path.name != "execution.json")
        self.assertIn("processing_log.jsonl", files)
        for name in files:
            self.assertEqual((self.output / name).read_bytes(), (other / name).read_bytes(), name)

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "existing.txt"
        sentinel.write_text("preserve previous run", encoding="utf-8")
        with self.assertRaises(PipelineError):
            self.execute()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve previous run")
        self.assertEqual({path.name for path in self.output.iterdir()}, {"existing.txt"})

    def test_source_directory_cannot_be_used_as_output(self):
        before = {path.name: path.read_bytes() for path in self.directory.iterdir() if path.is_file()}
        with self.assertRaises(PipelineError):
            self.execute(output=self.directory)
        after = {path.name: path.read_bytes() for path in self.directory.iterdir() if path.is_file()}
        self.assertEqual(before, after)

    def test_hash_mismatch_does_not_produce_outputs(self):
        metadata = valid_metadata(self.input)
        metadata["source"]["sha256"] = "0" * 64
        self.failed_fixture(metadata=metadata)

    def test_missing_required_metadata_is_rejected(self):
        metadata = valid_metadata(self.input)
        del metadata["source"]["publisher"]
        self.failed_fixture(metadata=metadata)

    def test_synthetic_source_cannot_be_relabelled_as_real_boundary(self):
        metadata = valid_metadata(self.input)
        metadata["source"]["kind"] = "SYNTHETIC"
        self.failed_fixture(metadata=metadata)

    def test_gps_source_cannot_be_used_as_aggregate_boundary(self):
        metadata = valid_metadata(self.input)
        metadata["source"]["kind"] = "OBSERVED_GPS"
        self.failed_fixture(metadata=metadata)

    def test_geometry_only_contract_is_required(self):
        metadata = valid_metadata(self.input)
        metadata["geometry_only"] = False
        self.failed_fixture(metadata=metadata)

    def test_incompatible_input_crs_is_rejected(self):
        metadata = valid_metadata(self.input)
        metadata["spatial"]["input_crs"] = "EPSG:5179"
        self.failed_fixture(metadata=metadata)

    def test_longitude_latitude_order_must_be_explicit(self):
        metadata = valid_metadata(self.input)
        metadata["spatial"]["coordinate_order"] = "latitude_longitude"
        self.failed_fixture(metadata=metadata)

    def test_embedded_crs_conflict_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["crs"] = {"type": "name", "properties": {"name": "EPSG:5179"}}
        self.failed_fixture(data)

    def test_unknown_region_is_rejected(self):
        self.failed_fixture(region_code="not-a-district")

    def test_empty_collection_is_rejected(self):
        self.failed_fixture({"type": "FeatureCollection", "features": []})

    def test_wrong_root_type_is_rejected(self):
        self.failed_fixture({"type": "Feature", "features": self.dataset["features"]})

    def test_missing_geometry_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        del data["features"][0]["geometry"]
        self.failed_fixture(data)

    def test_null_geometry_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"] = None
        self.failed_fixture(data)

    def test_null_properties_are_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["properties"] = None
        self.failed_fixture(data)

    def test_missing_district_id_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        del data["features"][0]["properties"]["code"]
        self.failed_fixture(data)

    def test_duplicate_district_id_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][1]["properties"]["code"] = data["features"][0]["properties"]["code"]
        self.failed_fixture(data)

    def test_unclosed_ring_is_rejected_without_silent_repair(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"]["coordinates"][0].pop()
        self.failed_fixture(data)

    def test_self_intersecting_geometry_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"] = {
            "type": "Polygon",
            "coordinates": [[[126.9, 37.5], [127.0, 37.6], [126.9, 37.6], [127.0, 37.5], [126.9, 37.5]]],
        }
        self.failed_fixture(data)

    def test_nan_coordinates_are_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"]["coordinates"][0][1][0] = float("nan")
        self.failed_fixture(data)

    def test_infinite_coordinates_are_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"]["coordinates"][0][1][0] = float("inf")
        self.failed_fixture(data)

    def test_string_coordinates_are_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"]["coordinates"][0][1][0] = "126.9"
        self.failed_fixture(data)

    def test_boolean_coordinates_are_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"]["coordinates"][0][1][0] = True
        self.failed_fixture(data)

    def test_out_of_range_coordinates_are_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"]["coordinates"][0][1][0] = 181
        self.failed_fixture(data)

    def test_null_coordinate_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"]["coordinates"][0][1][0] = None
        self.failed_fixture(data)

    def test_wrong_geometry_type_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"] = {"type": "Point", "coordinates": [126.9, 37.5]}
        self.failed_fixture(data)

    def test_cli_success_and_validation_failure_exit_codes(self):
        args = [sys.executable, "-m", "pipeline", "--input", str(self.input), "--metadata", str(self.metadata), "--output", str(self.output), "--region-code", "11140"]
        good = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(good.returncode, 0, good.stderr)
        bad_metadata = valid_metadata(self.input)
        bad_metadata["source"]["sha256"] = "0" * 64
        self.write_metadata(bad_metadata)
        bad_dir = self.directory / "bad-cli-result"
        args[args.index("--output") + 1] = str(bad_dir)
        bad = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(bad.returncode, 2, bad.stderr)
        self.assertEqual(json.loads((bad_dir / "quality_report.json").read_text(encoding="utf-8"))["status"], "failed")
        self.assertFalse((bad_dir / "run_manifest.json").exists())

    def test_late_export_failure_discards_partial_geojson(self):
        # The GeoJSON is staged before CSV serialization. A real write/encoding
        # failure at this point must publish only the failure report and log.
        with patch("pipeline.boundary._csv_bytes", side_effect=OSError("simulated export failure")):
            self.failed_fixture()
        self.assertEqual(
            {path.name for path in self.output.iterdir()},
            {"quality_report.json", "processing_log.jsonl"},
        )

    def test_valid_wgs84_outside_analysis_crs_area_is_rejected(self):
        data = copy.deepcopy(self.dataset)
        data["features"][0]["geometry"] = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }
        self.failed_fixture(data)

    def test_duplicate_json_keys_are_not_silently_accepted(self):
        self.input.write_text('{"type":"FeatureCollection","type":"FeatureCollection","features":[]}', encoding="utf-8")
        self.write_metadata(valid_metadata(self.input))
        report = self.failed_fixture()
        self.assertEqual(report["errors"][0]["code"], "DUPLICATE_JSON_KEY")

    def test_duplicate_names_generate_warning_without_merging_regions(self):
        data = copy.deepcopy(self.dataset)
        data["features"][1]["properties"]["name"] = data["features"][0]["properties"]["name"]
        self.write_fixture(data)
        self.execute()
        report = json.loads((self.output / "quality_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["feature_count"], 25)
        self.assertTrue(any(warning["code"] == "DUPLICATE_NAME" for warning in report["warnings"]))
        self.assertEqual(report["duplicate_region_codes"], 0)

    def test_missing_source_crs_and_unknown_license_are_reported(self):
        self.execute()
        report = json.loads((self.output / "quality_report.json").read_text(encoding="utf-8"))
        codes = {warning["code"] for warning in report["warnings"]}
        self.assertIn("CRS_NOT_DECLARED_IN_SOURCE", codes)
        self.assertIn("LICENSE_UNVERIFIED", codes)
        self.assertFalse(report["analysis_scores_generated"])
        self.assertFalse(report["bootstrap_performed"])


class SubmunicipalityPrefixTests(unittest.TestCase):
    """Check the historical 423-dong source and Mapo's 16-feature selection."""

    source_path = ROOT / "research_data/raw/seoul-submunicipalities-2013.geojson"
    metadata_path = ROOT / "research_data/sources/seoul-submunicipalities-2013.metadata.json"
    expected_codes = [
        "1114059", "1114060", "1114061", "1114063", "1114066", "1114068",
        "1114069", "1114070", "1114071", "1114072", "1114073", "1114074",
        "1114075", "1114076", "1114077", "1114078",
    ]

    @classmethod
    def setUpClass(cls):
        cls.source_bytes = cls.source_path.read_bytes()
        cls.metadata_bytes = cls.metadata_path.read_bytes()
        cls.raw_data = json.loads(cls.source_bytes)

    @classmethod
    def tearDownClass(cls):
        if cls.source_path.read_bytes() != cls.source_bytes or cls.metadata_path.read_bytes() != cls.metadata_bytes:
            raise AssertionError("Historical source or its metadata was modified")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="atlas-prefix-test-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.input = self.directory / "dong.geojson"
        self.metadata = self.directory / "dong.metadata.json"
        self.input.write_bytes(self.source_bytes)
        self.metadata.write_bytes(self.metadata_bytes)
        self.output = self.directory / "result"

    def execute(self, output=None, **selection):
        before = (self.input.read_bytes(), self.metadata.read_bytes())
        try:
            return run_pipeline(self.input, self.metadata, output or self.output, **selection)
        finally:
            self.assertEqual(before, (self.input.read_bytes(), self.metadata.read_bytes()))

    def assert_failed_selection(self, **selection):
        with self.assertRaises(PipelineError):
            self.execute(**selection)
        self.assertEqual(
            {path.name for path in self.output.iterdir()},
            {"quality_report.json", "processing_log.jsonl"},
        )
        report = json.loads((self.output / "quality_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["errors"])
        self.assertFalse(report["analysis_scores_generated"])

    def test_actual_423_source_selects_exactly_16_mapo_dongs(self):
        from shapely.geometry import shape

        self.assertEqual(len(self.raw_data["features"]), 423)
        manifest = self.execute(region_prefix="11140")
        report = json.loads((self.output / "quality_report.json").read_text(encoding="utf-8"))
        geojson = json.loads((self.output / "mapo.geojson").read_text(encoding="utf-8"))
        self.assertEqual(report["feature_count"], 423)
        self.assertEqual(report["selection"], {
            "mode": "prefix", "value": "11140", "feature_count": 16, "codes": self.expected_codes,
        })
        self.assertEqual(manifest["parameters"]["selection"], {"mode": "prefix", "value": "11140"})
        self.assertEqual(manifest["selected_codes"], self.expected_codes)
        self.assertEqual([feature["properties"]["code"] for feature in geojson["features"]], self.expected_codes)
        originals = {feature["properties"]["code"]: feature for feature in self.raw_data["features"]}
        bounds = []
        for feature in geojson["features"]:
            original = originals[feature["properties"]["code"]]
            self.assertEqual(feature["properties"], original["properties"])
            self.assertTrue(shape(feature["geometry"]).equals(shape(original["geometry"])))
            bounds.append(shape(original["geometry"]).bounds)
        self.assertEqual(geojson["bbox"], [
            min(bound[0] for bound in bounds), min(bound[1] for bound in bounds),
            max(bound[2] for bound in bounds), max(bound[3] for bound in bounds),
        ])
        with (self.output / "districts.csv").open(encoding="utf-8-sig", newline="") as stream:
            all_rows = list(csv.DictReader(stream))
        with (self.output / "mapo.projected.csv").open(encoding="utf-8-sig", newline="") as stream:
            selected_rows = list(csv.DictReader(stream))
        self.assertEqual(len(all_rows), 423)
        self.assertEqual([row["code"] for row in selected_rows], self.expected_codes)
        self.assertTrue(all(row["crs"] == "EPSG:5179" for row in selected_rows))
        area_sum = sum(float(row["area_m2"]) for row in selected_rows)
        perimeter_sum = sum(float(row["perimeter_m"]) for row in selected_rows)
        self.assertAlmostEqual(report["selected_region"]["sum_area_m2"], area_sum, delta=0.01)
        self.assertAlmostEqual(report["selected_region"]["sum_feature_perimeter_m"], perimeter_sum, delta=0.01)
        self.assertIn("shared internal borders", report["selected_region"]["perimeter_note"])
        self.assertEqual(manifest["source"]["kind"], "PUBLIC_AGGREGATE")
        self.assertEqual(manifest["source"]["license"], "UNKNOWN")
        self.assertIn("Apache-2.0", manifest["source"]["redistributor_license_declaration"])
        self.assertFalse(manifest["source"]["original_agency_terms_verified"])

    def test_prefix_selection_is_reproducible_and_changes_run_identity(self):
        prefix = self.execute(region_prefix="11140")
        repeated_dir = self.directory / "repeat"
        repeated = self.execute(output=repeated_dir, region_prefix="11140")
        self.assertEqual(prefix, repeated)
        for name, expected_hash in prefix["outputs"].items():
            self.assertEqual(sha256(self.output / name), expected_hash)
            self.assertEqual((self.output / name).read_bytes(), (repeated_dir / name).read_bytes())
        exact = self.execute(output=self.directory / "exact", region_code="1114077")
        self.assertNotEqual(prefix["run_id"], exact["run_id"])
        self.assertEqual(exact["selected_codes"], ["1114077"])
        self.assertEqual(exact["parameters"]["selection"], {"mode": "exact", "value": "1114077"})

    def test_api_rejects_conflicting_selection_arguments(self):
        self.assert_failed_selection(region_code="1114077", region_prefix="11140")

    def test_api_rejects_empty_prefix(self):
        self.assert_failed_selection(region_prefix="")

    def test_api_rejects_nonstring_prefix(self):
        self.assert_failed_selection(region_prefix=11140)

    def test_api_rejects_missing_prefix(self):
        self.assert_failed_selection(region_prefix="99999")

    def test_cli_prefix_success_and_conflicting_arguments(self):
        args = [sys.executable, "-m", "pipeline", "--input", str(self.input), "--metadata", str(self.metadata), "--output", str(self.output), "--region-prefix", "11140"]
        good = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(good.returncode, 0, good.stderr)
        manifest = json.loads((self.output / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["selected_codes"], self.expected_codes)
        conflict_dir = self.directory / "conflict"
        args[args.index("--output") + 1] = str(conflict_dir)
        conflict = subprocess.run([*args, "--region-code", "1114077"], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(conflict.returncode, 2)
        self.assertIn("not allowed", conflict.stderr)
        self.assertFalse(conflict_dir.exists())


if __name__ == "__main__":
    unittest.main()
