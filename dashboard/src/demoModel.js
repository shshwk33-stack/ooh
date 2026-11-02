/**
 * Presentation selectors for the standalone dashboard.
 * These formulas operate on DEMO fixtures only, never on research data.
 * Static is explicitly the spatial-only baseline (S).
 * Bootstrap fields remain canned examples and are not statistical estimates.
 */
import { DEMO_CANDIDATES } from "./demo.js";

export const DEMO_WEIGHTS = Object.freeze([0, 20, 40, 60, 80, 100]);
const SERIES_COLORS = Object.freeze({
  "TA-001": "#27866b",
  "TA-002": "#c89436",
  "TA-003": "#528fc4",
  "TA-004": "#9b78b5",
  "TA-005": "#8b9690",
  "TA-006": "#b87c6e",
  "TA-007": "#5d9e9b",
  "TA-008": "#7681ad",
});

export function validateDemoWeight(mobility) {
  const weight = Number(mobility);
  if (!Number.isFinite(weight) || weight < 0 || weight > 100) {
    throw new RangeError("Mobility 가중치는 0–100 범위의 숫자여야 합니다.");
  }
  return weight;
}

export function formatDemoScore(value) {
  return (Math.round((Number(value) + Number.EPSILON) * 1000) / 1000).toFixed(
    3,
  );
}

export function rankedCandidatesAtWeight(mobility = 60) {
  const weight = validateDemoWeight(mobility);
  return DEMO_CANDIDATES.map((candidate) => {
    // Inputs have three decimal places. Work in thousandths so endpoint
    // and equal-score ordering do not depend on addition round-off.
    const m = Math.round(Number(candidate.mobility) * 1000);
    const s = Math.round(Number(candidate.spatial) * 1000);
    const mobilityContribution = (m * weight) / 100000;
    const spatialContribution = (s * (100 - weight)) / 100000;
    const score = (m * weight + s * (100 - weight)) / 100000;
    const reason =
      `현재 가중치에서 이동 기여 ${mobilityContribution.toFixed(3)}, 공간 기여 ${spatialContribution.toFixed(3)}입니다. ` +
      (Number(candidate.mobility) > Number(candidate.spatial)
        ? "이동 점수가 공간 점수보다 높아, 이동 비중을 높일수록 상대적으로 유리합니다."
        : "공간 점수가 이동 점수보다 높아, 공간 비중을 높일수록 상대적으로 유리합니다.");
    return {
      ...candidate,
      static: candidate.spatial,
      score,
      value: formatDemoScore(score),
      mobilityContribution,
      spatialContribution,
      reason,
    };
  })
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id, "en"))
    .map((candidate, index) => ({ ...candidate, rank: index + 1 }));
}

export function rankAtWeight(id, mobility = 60) {
  return (
    rankedCandidatesAtWeight(mobility).find((candidate) => candidate.id === id)
      ?.rank ?? null
  );
}

export function deriveDemo(mobility = 60) {
  const weight = validateDemoWeight(mobility);
  const candidates = rankedCandidatesAtWeight(weight);
  const topFive = candidates.slice(0, 5);
  const ranksByWeight = DEMO_WEIGHTS.map((value) =>
    rankedCandidatesAtWeight(value),
  );
  return {
    candidates,
    highest: candidates[0].value,
    highestCandidate: candidates[0],
    average: formatDemoScore(
      candidates.reduce((sum, candidate) => sum + candidate.score, 0) /
        candidates.length,
    ),
    roadCount: 408,
    // A summary of the separate fixed Bootstrap example, not a new analysis.
    stability: formatDemoScore(
      topFive.reduce((sum, candidate) => sum + Number(candidate.top5), 0) /
        topFive.length,
    ),
    bootstrap: candidates.map(({ id, short, mean, top5, sigma }) => ({
      id,
      short,
      mean,
      top5,
      sigma,
    })),
    rankSeries: topFive.map((candidate) => ({
      id: candidate.id,
      name: candidate.short,
      color: SERIES_COLORS[candidate.id],
      values: ranksByWeight.map(
        (ranked) => ranked.find((row) => row.id === candidate.id).rank,
      ),
    })),
    weights: [...DEMO_WEIGHTS],
    mobilityWeight: weight,
    spatialWeight: 100 - weight,
  };
}
