import test from "node:test";
import assert from "node:assert/strict";
import { rankCandidates } from "../src/model.js";
import {
  decomposition,
  stability,
  rankOf,
  validateRoads,
} from "../src/research.js";
test("displayed contributions reconcile to unchanged model across weights and time conditions", () => {
  for (const time of ["all", "morning", "evening"])
    for (let a = 0; a <= 100; a += 5)
      for (const c of rankCandidates(a, time)) {
        assert.ok(Math.abs(decomposition(c, a, time).final - c.score) < 1e-12);
      }
});
test("stability is calculated over 21 scenarios and respects filtered candidate universe", () => {
  const s = stability("MP-024");
  assert.equal(s.ranks.length, 21);
  assert.equal(s.top3, s.ranks.filter((r) => r <= 3).length);
  assert.equal(rankOf("MP-018", 0), 1);
  assert.equal(rankOf("MP-024", 100), 1);
  assert.equal(stability("MP-009", "all", "망원동").top3, 21);
});
test("GeoJSON rejects invalid data and accepts valid local road geometry", () => {
  const f = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { traffic: 200 },
        geometry: {
          type: "LineString",
          coordinates: [
            [126.91, 37.55],
            [126.92, 37.56],
          ],
        },
      },
    ],
  };
  assert.equal(validateRoads(f), f);
  assert.throws(() =>
    validateRoads({ type: "FeatureCollection", features: [] }),
  );
  assert.throws(() =>
    validateRoads({
      ...f,
      features: [{ ...f.features[0], properties: { traffic: -1 } }],
    }),
  );
  assert.throws(() =>
    validateRoads({
      ...f,
      features: [
        {
          ...f.features[0],
          geometry: { type: "Point", coordinates: [126.91, 37.55] },
        },
      ],
    }),
  );
  assert.throws(() =>
    validateRoads({
      ...f,
      features: [
        {
          ...f.features[0],
          geometry: {
            type: "LineString",
            coordinates: [
              [200000, 400000],
              [200001, 400001],
            ],
          },
        },
      ],
    }),
  );
});
