import test from "node:test";
import assert from "node:assert/strict";
import { DEMO_CANDIDATES } from "../src/demo.js";
import {
  deriveDemo,
  rankAtWeight,
  rankedCandidatesAtWeight,
} from "../src/demoModel.js";

const near = (actual, expected) =>
  assert.ok(Math.abs(actual - expected) < 1e-12, `${actual} != ${expected}`);

test("all displayed scores reconcile with DEMO weighted inputs and spatial-only baseline", () => {
  for (let weight = 0; weight <= 100; weight += 5) {
    const demo = deriveDemo(weight);
    assert.equal(demo.mobilityWeight + demo.spatialWeight, 100);
    for (const candidate of demo.candidates) {
      const expected =
        (Number(candidate.mobility) * weight) / 100 +
        (Number(candidate.spatial) * (100 - weight)) / 100;
      near(candidate.score, expected);
      near(
        candidate.mobilityContribution + candidate.spatialContribution,
        candidate.score,
      );
      assert.equal(
        candidate.value,
        (Math.round((expected + Number.EPSILON) * 1000) / 1000).toFixed(3),
      );
      assert.equal(candidate.static, candidate.spatial);
    }
  }
});

test("rank and KPI summaries come from the same score collection", () => {
  for (const weight of [0, 30, 50, 60, 80, 100]) {
    const demo = deriveDemo(weight);
    assert.deepEqual(
      demo.candidates.map((c) => c.rank),
      [1, 2, 3, 4, 5, 6, 7, 8],
    );
    for (let i = 1; i < demo.candidates.length; i++)
      assert.ok(demo.candidates[i - 1].score >= demo.candidates[i].score);
    assert.equal(demo.highest, demo.candidates[0].value);
    assert.equal(
      demo.average,
      (demo.candidates.reduce((n, c) => n + c.score, 0) / 8).toFixed(3),
    );
    assert.equal(
      demo.stability,
      (
        demo.candidates.slice(0, 5).reduce((n, c) => n + Number(c.top5), 0) / 5
      ).toFixed(3),
    );
  }
});

test("weight changes produce real ranking reversals while preserving identity", () => {
  const baseline = deriveDemo(60);
  assert.equal(baseline.candidates[0].id, "TA-001");
  assert.equal(baseline.candidates[1].id, "TA-002");
  assert.equal(deriveDemo(30).candidates[0].id, "TA-002");
  assert.equal(deriveDemo(80).candidates[1].id, "TA-003");
  assert.equal(rankAtWeight("TA-001", 0), 4);
  assert.equal(rankAtWeight("TA-001", 100), 1);
  assert.equal(rankAtWeight("unknown", 60), null);
});

test("sensitivity series agrees with rankings at every plotted weight", () => {
  const demo = deriveDemo(60);
  for (const series of demo.rankSeries) {
    assert.equal(series.values.length, demo.weights.length);
    series.values.forEach((rank, index) =>
      assert.equal(rank, rankAtWeight(series.id, demo.weights[index])),
    );
  }
});

test("endpoints preserve inputs and ties use candidate ID consistently", () => {
  for (const c of rankedCandidatesAtWeight(0)) near(c.score, Number(c.spatial));
  for (const c of rankedCandidatesAtWeight(100))
    near(c.score, Number(c.mobility));
  const tied = rankedCandidatesAtWeight(60).filter((c) => c.score === 0.7);
  assert.deepEqual(
    tied.map((c) => c.id),
    ["TA-007", "TA-008"],
  );
  assert.deepEqual(rankedCandidatesAtWeight(60), rankedCandidatesAtWeight(60));
});

test("selectors leave fixtures and canned Bootstrap examples unchanged", () => {
  const before = structuredClone(DEMO_CANDIDATES);
  for (const weight of [0, 30, 60, 100]) {
    const demo = deriveDemo(weight);
    for (const candidate of demo.candidates) {
      const source = before.find((c) => c.id === candidate.id);
      for (const key of [
        "x",
        "y",
        "name",
        "visits",
        "population",
        "poi",
        "mean",
        "top5",
        "sigma",
      ])
        assert.equal(candidate[key], source[key]);
    }
  }
  assert.deepEqual(DEMO_CANDIDATES, before);
  assert.throws(() => deriveDemo(-1), RangeError);
  assert.throws(() => deriveDemo(101), RangeError);
  assert.throws(() => deriveDemo(NaN), RangeError);
});
