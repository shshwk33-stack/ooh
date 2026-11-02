import test from "node:test";
import assert from "node:assert/strict";
import { rankCandidates, toCSV } from "../src/model.js";
test("weighting changes ranking and uses the defined weighted sum", () => {
  const movement = rankCandidates(100),
    space = rankCandidates(0);
  assert.equal(movement[0].name, "홍대입구역");
  assert.equal(space[0].name, "공덕역");
  const mixed = rankCandidates(60);
  for (const c of mixed)
    assert.ok(Math.abs(c.score - (c.mobility * 0.6 + c.spatial * 0.4)) < 1e-9);
});
test("time and region filters affect the actual results", () => {
  assert.equal(rankCandidates(60, "all", "망원동").length, 1);
  assert.equal(rankCandidates(60, "all", "망원동")[0].name, "망원시장");
  assert.notEqual(
    rankCandidates(60, "morning")[0].score,
    rankCandidates(60, "evening")[0].score,
  );
});
test("CSV reflects the current scenario", () => {
  const rows = rankCandidates(30);
  const csv = toCSV(rows, 30);
  assert.ok(csv.includes(rows[0].score.toFixed(3)));
  assert.ok(csv.includes("30%"));
  assert.equal(csv.split("\n").length, rows.length + 1);
});
