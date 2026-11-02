import test from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_WORKSPACE } from "../src/workspaceData.js";
import {
  deriveWorkspace,
  exportWorkspaceCsv,
  exportWorkspaceJson,
} from "../src/workspaceModel.js";
import {
  validateWorkspace,
  parseWorkspaceJson,
  exportCandidatesCsv,
  exportCandidatesTemplate,
  importCandidatesCsv,
  fetchWorkspace,
} from "../src/workspaceContract.js";
const clone = () => structuredClone(DEFAULT_WORKSPACE);

test("API display metadata rejects objects that could break source tables or GIS labels", () => {
  for (const key of ["year", "unit", "description", "method"]) {
    const d = clone();
    d.meta.sources[0][key] = { unexpected: "object" };
    assert.throws(() => validateWorkspace(d));
  }
  for (const key of ["name", "unit", "value", "population", "traffic"]) {
    const d = clone();
    d.geometry.units.features[0].properties[key] = { unexpected: "object" };
    assert.throws(() => validateWorkspace(d));
  }
});

test("unified workspace preserves actual boundaries, synthetic provenance and score reversals", () => {
  const d = clone(),
    before = JSON.stringify(d),
    a = deriveWorkspace(d, { mobility: 60 }),
    b = deriveWorkspace(d, { mobility: 30 });
  assert.equal(a.candidates[0].id, "TA-001");
  assert.equal(a.candidates[0].value, "0.876");
  assert.equal(b.candidates[0].id, "TA-002");
  assert.equal(b.candidates[0].value, "0.906");
  assert.equal(a.kpis.unitCount, 16);
  assert.equal(a.kpis.positionCount, 72);
  assert.equal(a.roadCount, null);
  assert.equal(a.bootstrap, null);
  assert.equal(a.kpis.stability, null);
  assert.equal(
    d.meta.sources.find((s) => s.id === "candidate-scenario").kind,
    "SYNTHETIC",
  );
  assert.equal(JSON.stringify(d), before);
});
test("named scenario anchors do not swap Mangwon and Hapjeong when source order differs", () => {
  const mangwon = DEFAULT_WORKSPACE.candidates.find((c) => c.id === "TA-003"),
    hapjeong = DEFAULT_WORKSPACE.candidates.find((c) => c.id === "TA-005");
  assert.equal(mangwon.short, "망원역");
  assert.equal(hapjeong.short, "합정역");
  assert.ok(mangwon.latitude > hapjeong.latitude);
  assert.ok(mangwon.longitude < hapjeong.longitude);
  assert.equal(mangwon.unitCode, "1114072");
  assert.equal(hapjeong.unitCode, "1114068");
  assert.deepEqual([mangwon.longitude, mangwon.latitude], [126.9105, 37.556]);
  assert.deepEqual(
    [hapjeong.longitude, hapjeong.latitude],
    [126.9139, 37.5496],
  );
  assert.equal(mangwon.coordinateMethod, "manual_scenario_anchor");
  assert.match(
    DEFAULT_WORKSPACE.meta.sources.find((s) => s.id === "candidate-scenario")
      .method,
    /not official/,
  );
});
test("GPS filters act on observations without inventing temporal score changes", () => {
  const all = deriveWorkspace(clone()),
    a = deriveWorkspace(clone(), {
      vehicle: "SYNTH-VEH-01",
      day: "2024-05-01",
    }),
    none = deriveWorkspace(clone(), { time: "afternoon" });
  assert.equal(a.filteredPositions.length, 12);
  assert.equal(none.filteredPositions.length, 0);
  assert.equal(none.highest, all.highest);
  assert.equal(
    all.units.reduce((s, u) => s + u.sampleCount, 0),
    72,
  );
  assert.throws(() => deriveWorkspace(clone(), { vehicle: "unknown" }));
});
test("incomplete scores stay null except zero-weight dimensions and unscored rows do not rank", () => {
  const d = clone();
  d.candidates[0].mobility = null;
  const a = deriveWorkspace(d, { mobility: 60 }),
    s = deriveWorkspace(d, { mobility: 0 });
  assert.equal(a.candidates.find((c) => c.id === "TA-001").score, null);
  assert.equal(a.candidates.find((c) => c.id === "TA-001").rank, null);
  assert.equal(s.candidates.find((c) => c.id === "TA-001").score, 0.78);
  for (const c of d.candidates) {
    c.mobility = null;
    c.spatial = null;
  }
  assert.equal(deriveWorkspace(d).highest, null);
  assert.equal(deriveWorkspace(d).average, null);
});
test("sensitivity, contributions and correlations share the same weighted calculation", () => {
  const a = deriveWorkspace(clone(), { mobility: 60 });
  assert.equal(a.weights.length, 21);
  assert.equal(a.sensitivity.length, 21);
  for (const row of a.candidates)
    assert.ok(
      Math.abs(row.mobilityContribution + row.spatialContribution - row.score) <
        1e-12,
    );
  for (const series of a.rankSeries)
    assert.equal(
      series.values[12],
      a.candidates.find((c) => c.id === series.id).rank,
    );
  const s = deriveWorkspace(clone(), { mobility: 0 });
  assert.equal(s.comparisons.spatialIntegrated.spearman, 1);
  assert.equal(s.comparisons.spatialIntegrated.kendall, 1);
  assert.equal(s.comparisons.spatialIntegrated.topKOverlap, 1);
});
function withBootstrap() {
  const d = clone();
  d.meta.sources.push({
    id: "computed-bootstrap",
    label: "Independent resampling result",
    kind: "DERIVED",
  });
  d.bootstrap = {
    sourceId: "computed-bootstrap",
    iterations: 1000,
    seed: 42,
    resampleUnit: "vehicle-day",
    weight: 60,
    period: { ...d.meta.period },
    topK: 5,
    results: d.candidates.map((c, i) => ({
      candidateId: c.id,
      meanRank: i + 1,
      rankSD: 0.2,
      topKProbability: i < 5 ? 0.9 : 0.1,
    })),
  };
  return d;
}
test("bootstrap is only shown for matching weights, period and complete candidate cohort", () => {
  const d = withBootstrap();
  assert.ok(Math.abs(deriveWorkspace(d).kpis.stability - 0.9) < 1e-12);
  assert.equal(
    deriveWorkspace(d, { mobility: 30 }).bootstrapStatus,
    "weight_mismatch",
  );
  d.bootstrap.period.end = "2024-05-02T23:59:59+09:00";
  assert.equal(deriveWorkspace(d).bootstrapStatus, "period_mismatch");
  assert.equal(deriveWorkspace(d).kpis.stability, null);
  d.bootstrap.period = { ...d.meta.period };
  d.bootstrap.results.pop();
  assert.equal(deriveWorkspace(d).bootstrapStatus, "candidate_mismatch");
});
test("CSV roundtrip handles Korean, quotes, commas and embedded newlines without provenance changes", () => {
  const d = clone();
  d.candidates[0].name = '홍대, "입구"\n연결';
  const csv = exportCandidatesCsv(d),
    r = importCandidatesCsv(csv, d);
  assert.equal(r.candidates.length, 8);
  assert.equal(r.candidates[0].name, d.candidates[0].name);
  assert.equal(r.candidates[0].mobility, 0.94);
  assert.equal(r.bootstrap, null);
  assert.equal(deriveWorkspace(r).candidates[0].value, "0.876");
  assert.ok(exportCandidatesTemplate().includes("source_kind"));
  assert.ok(exportWorkspaceCsv(r).includes("SYNTHETIC"));
  assert.equal(JSON.parse(exportWorkspaceJson(r)).schemaVersion, "2.0");
});
test("CSV rejects malformed quoting, duplicate headers, missing columns and source conflicts", () => {
  const d = clone(),
    good = exportCandidatesCsv(d);
  assert.throws(() => importCandidatesCsv("id,id\n1,2", d));
  assert.throws(() => importCandidatesCsv(good.replace('"id"', '"name"'), d));
  assert.throws(() => importCandidatesCsv(good + '"unclosed', d));
  assert.throws(() =>
    importCandidatesCsv(good.replaceAll('"SYNTHETIC"', '"OBSERVED_GPS"'), d),
  );
  const columns = good.split("\r\n"),
    row = columns[1].replace('"0.94"', '"bad"');
  assert.throws(() => importCandidatesCsv([columns[0], row].join("\r\n"), d));
});
test("strict contract rejects schema, finite scores, coordinates, duplicate IDs and detached sources", () => {
  for (const mutate of [
    (d) => (d.schemaVersion = "1"),
    (d) => (d.candidates[0].mobility = NaN),
    (d) => (d.candidates[0].latitude = 90),
    (d) => (d.candidates[1].id = d.candidates[0].id),
    (d) => (d.candidates[0].sourceId = "missing"),
    (d) => d.geometry.units.features[0].geometry.coordinates[0].pop(),
    (d) => (d.gps.positions[1].timestamp = d.gps.positions[0].timestamp),
    (d) => (d.meta.sources[0].url = "javascript:alert(1)"),
  ]) {
    const d = clone();
    mutate(d);
    assert.throws(() => validateWorkspace(d));
  }
  assert.throws(
    () => parseWorkspaceJson('{"schemaVersion":"2.0","schemaVersion":"2.0"}'),
    /중복/,
  );
  assert.throws(() => parseWorkspaceJson("NaN"));
});
test("calendar validation rejects normalized impossible dates and preserves explicit metric units", () => {
  for (const impossible of [
    "2024-02-30T12:00:00Z",
    "2023-02-29T12:00:00Z",
    "2024-04-31T12:00:00Z",
    "2024-05-01T24:00:00Z",
    "2024-05-01T12:00:00+14:30",
  ]) {
    const d = clone();
    d.meta.period.start = impossible;
    assert.throws(() => validateWorkspace(d), /달력/);
  }
  const d = clone();
  d.candidates[0].metricUnits = {
    traffic: "대/일",
    population: "명/일",
    poi: "개",
  };
  assert.equal(validateWorkspace(d).candidates[0].metricUnits.traffic, "대/일");
  d.candidates[0].metricUnits.traffic = 123;
  assert.throws(() => validateWorkspace(d), /metricUnits/);
  const valid = clone();
  valid.gps.positions[0].timestamp = "2024-02-29T12:00:00Z";
  validateWorkspace(valid);
});
test("API adapter accepts canonical JSON, rejects bad responses and never mutates existing data", async () => {
  const d = clone(),
    before = JSON.stringify(d),
    r = await fetchWorkspace("https://example.org/workspace", {
      fetchImpl: async (url, options) => {
        assert.equal(options.credentials, "omit");
        return new Response(JSON.stringify(d), {
          headers: { "Content-Type": "application/json" },
        });
      },
    });
  assert.equal(r.candidates.length, 8);
  for (const response of [
    new Response("no", { status: 503 }),
    new Response("{}", { headers: { "Content-Type": "text/html" } }),
    new Response("{}", { headers: { "Content-Type": "application/json" } }),
    new Response("{}", {
      headers: {
        "Content-Type": "application/json",
        "Content-Length": "11000000",
      },
    }),
  ])
    await assert.rejects(() =>
      fetchWorkspace("https://example.org/workspace", {
        fetchImpl: async () => response,
      }),
    );
  await assert.rejects(() =>
    fetchWorkspace("https://user:secret@example.org/data"),
  );
  await assert.rejects(() =>
    fetchWorkspace("https://example.org/data?api_key=secret"),
  );
  assert.equal(JSON.stringify(d), before);
});
test("API request cancellation and timeout fail clearly instead of replacing data", async () => {
  const fetchImpl = (url, { signal }) =>
    new Promise((resolve, reject) => {
      if (signal.aborted) reject(new Error("aborted"));
      else
        signal.addEventListener("abort", () => reject(new Error("aborted")), {
          once: true,
        });
    });
  await assert.rejects(
    () =>
      fetchWorkspace("https://example.org/data", { fetchImpl, timeoutMs: 5 }),
    /취소|초과/,
  );
});
