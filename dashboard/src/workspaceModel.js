import { validateWorkspace } from "./workspaceContract.js";

export const WORKSPACE_WEIGHTS = Array.from({ length: 21 }, (_, i) => i * 5);
const COLORS = [
  "#27866b",
  "#d09a36",
  "#4b91bf",
  "#a274bc",
  "#85938b",
  "#b67d68",
  "#4d9d9c",
  "#7280ad",
];
const score = (value) => typeof value === "number" && Number.isFinite(value);
export function rankedWorkspaceCandidates(dataset, mobility = 60) {
  if (!score(mobility) || mobility < 0 || mobility > 100)
    throw new Error("Mobility 가중치는 0–100이어야 합니다.");
  const alpha = mobility / 100;
  const rows = dataset.candidates
    .map((c, index) => {
      const valid =
        (alpha === 0 || score(c.mobility)) && (alpha === 1 || score(c.spatial));
      const m = score(c.mobility) ? c.mobility * alpha : null,
        s = score(c.spatial) ? c.spatial * (1 - alpha) : null;
      const total = valid ? (m || 0) + (s || 0) : null;
      return {
        ...c,
        color: COLORS[index % COLORS.length],
        score: total,
        value: total === null ? "—" : total.toFixed(3),
        mobilityContribution: m,
        spatialContribution: s,
        static: c.spatial,
      };
    })
    .sort((a, b) =>
      a.score === null
        ? b.score === null
          ? a.id.localeCompare(b.id)
          : 1
        : b.score === null
          ? -1
          : b.score - a.score || a.id.localeCompare(b.id),
    );
  let rank = 0;
  return rows.map((c) => ({ ...c, rank: c.score === null ? null : ++rank }));
}
function ranks(values) {
  const sorted = values.map((v, i) => ({ v, i })).sort((a, b) => a.v - b.v),
    result = [];
  for (let i = 0; i < sorted.length; ) {
    let j = i + 1;
    while (j < sorted.length && sorted[j].v === sorted[i].v) j++;
    for (let k = i; k < j; k++) result[sorted[k].i] = (i + 1 + j) / 2;
    i = j;
  }
  return result;
}
function pearson(a, b) {
  if (a.length < 2) return null;
  const ma = a.reduce((s, x) => s + x, 0) / a.length,
    mb = b.reduce((s, x) => s + x, 0) / b.length;
  let up = 0,
    aa = 0,
    bb = 0;
  for (let i = 0; i < a.length; i++) {
    up += (a[i] - ma) * (b[i] - mb);
    aa += (a[i] - ma) ** 2;
    bb += (b[i] - mb) ** 2;
  }
  return aa && bb ? up / Math.sqrt(aa * bb) : null;
}
function kendall(a, b) {
  let agree = 0,
    disagree = 0,
    tiesA = 0,
    tiesB = 0;
  for (let i = 0; i < a.length; i++)
    for (let j = i + 1; j < a.length; j++) {
      const x = Math.sign(a[i] - a[j]),
        y = Math.sign(b[i] - b[j]);
      if (!x && !y) continue;
      if (!x) tiesA++;
      else if (!y) tiesB++;
      else if (x === y) agree++;
      else disagree++;
    }
  const d = Math.sqrt((agree + disagree + tiesA) * (agree + disagree + tiesB));
  return d ? (agree - disagree) / d : null;
}
function compare(a, b, k = 5) {
  const byId = new Map(b.filter((c) => c.score !== null).map((c) => [c.id, c]));
  const paired = a.filter((c) => c.score !== null && byId.has(c.id));
  const aa = paired.map((c) => c.score),
    bb = paired.map((c) => byId.get(c.id).score);
  const ka = a.filter((c) => c.score !== null).slice(0, k),
    kb = new Set(
      b
        .filter((c) => c.score !== null)
        .slice(0, k)
        .map((c) => c.id),
    );
  const denominator = Math.min(k, ka.length, kb.size);
  return {
    spearman: pearson(ranks(aa), ranks(bb)),
    kendall: kendall(aa, bb),
    topKOverlap: denominator
      ? ka.filter((c) => kb.has(c.id)).length / denominator
      : null,
    topK: k,
    pairedCount: paired.length,
  };
}
const dateFormats = new Map();
function formats(timezone) {
  if (!dateFormats.has(timezone))
    dateFormats.set(timezone, {
      day: new Intl.DateTimeFormat("en-CA", {
        timeZone: timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }),
      hour: new Intl.DateTimeFormat("en-GB", {
        timeZone: timezone,
        hour: "2-digit",
        hourCycle: "h23",
      }),
    });
  return dateFormats.get(timezone);
}
const localDay = (timestamp, timezone) =>
  formats(timezone).day.format(new Date(timestamp));
const localHour = (timestamp, timezone) =>
  Number(formats(timezone).hour.format(new Date(timestamp)));
export function deriveWorkspace(dataset, filters = {}) {
  validateWorkspace(dataset);
  const weight = filters.mobility ?? 60,
    timezone = dataset.meta.period.timezone;
  const start = Date.parse(dataset.meta.period.start),
    end = Date.parse(dataset.meta.period.end);
  const allPositions = dataset.gps.positions
    .filter(
      (p) => Date.parse(p.timestamp) >= start && Date.parse(p.timestamp) <= end,
    )
    .map((p) => ({
      ...p,
      day: localDay(p.timestamp, timezone),
      hour: localHour(p.timestamp, timezone),
    }));
  const vehicles = [...new Set(allPositions.map((p) => p.vehicleId))].sort(),
    days = [...new Set(allPositions.map((p) => p.day))].sort();
  const vehicle = filters.vehicle || "all",
    day = filters.day || "all",
    time = filters.time || "all";
  if (
    !["all", "morning", "afternoon"].includes(time) ||
    (vehicle !== "all" && !vehicles.includes(vehicle)) ||
    (day !== "all" && !days.includes(day))
  )
    throw new Error("조회 조건이 현재 자료에 없습니다.");
  const filteredPositions = allPositions.filter(
    (p) =>
      (vehicle === "all" || p.vehicleId === vehicle) &&
      (day === "all" || p.day === day) &&
      (time === "all" || (time === "morning" ? p.hour < 12 : p.hour >= 12)),
  );
  const candidates = rankedWorkspaceCandidates(dataset, weight),
    eligible = candidates.filter((c) => c.score !== null),
    highest = eligible[0]?.score ?? null,
    average = eligible.length
      ? eligible.reduce((sum, c) => sum + c.score, 0) / eligible.length
      : null;
  const sensitivity = WORKSPACE_WEIGHTS.map((w) => ({
    weight: w,
    rows: rankedWorkspaceCandidates(dataset, w),
  }));
  const rankSeries = candidates
    .slice(0, 5)
    .map((c) => ({
      id: c.id,
      name: c.short,
      color: c.color,
      values: sensitivity.map(
        (s) => s.rows.find((r) => r.id === c.id)?.rank ?? null,
      ),
    }));
  const units = dataset.geometry.units.features.map((f) => ({
    ...f.properties,
    code: String(f.properties.code),
    sampleCount: filteredPositions.filter(
      (p) => p.unitCode === String(f.properties.code),
    ).length,
  }));
  const b = dataset.bootstrap;
  const samePeriod =
    b &&
    Date.parse(b.period.start) === Date.parse(dataset.meta.period.start) &&
    Date.parse(b.period.end) === Date.parse(dataset.meta.period.end) &&
    b.period.timezone === dataset.meta.period.timezone;
  const sameCandidates =
    b &&
    b.results.length === dataset.candidates.length &&
    dataset.candidates.every((c) =>
      b.results.some((r) => r.candidateId === c.id),
    );
  const bootstrapStatus = !b
    ? "unavailable"
    : b.weight !== weight
      ? "weight_mismatch"
      : !samePeriod
        ? "period_mismatch"
        : !sameCandidates
          ? "candidate_mismatch"
          : "available";
  const bootstrap = bootstrapStatus === "available" ? dataset.bootstrap : null;
  const topIds = new Set(
    eligible.slice(0, bootstrap?.topK || 5).map((c) => c.id),
  );
  const topResults =
    bootstrap?.results.filter((r) => topIds.has(r.candidateId)) || [];
  const stability = topResults.length
    ? topResults.reduce((s, r) => s + r.topKProbability, 0) / topResults.length
    : null;
  const spatial = rankedWorkspaceCandidates(dataset, 0),
    mobility = rankedWorkspaceCandidates(dataset, 100);
  const comparisons = {
    spatial,
    mobility,
    integrated: candidates,
    spatialMobility: compare(spatial, mobility),
    spatialIntegrated: compare(spatial, candidates),
    mobilityIntegrated: compare(mobility, candidates),
  };
  const roadCount = dataset.geometry.roads.features.length || null;
  const kpis = {
    candidateCount: candidates.length,
    scoredCount: eligible.length,
    highest,
    average,
    roadCount,
    unitCount: units.length,
    positionCount: filteredPositions.length,
    vehicleCount: new Set(filteredPositions.map((p) => p.vehicleId)).size,
    dayCount: new Set(filteredPositions.map((p) => p.day)).size,
    stability,
  };
  return {
    candidates,
    highest,
    average,
    roadCount,
    selectedCandidate:
      candidates.find((c) => c.id === filters.selectedId) ||
      candidates[0] ||
      null,
    weights: WORKSPACE_WEIGHTS,
    sensitivity,
    rankSeries,
    filteredPositions,
    positions: filteredPositions,
    allPositions,
    units,
    kpis,
    vehicles,
    days,
    availableVehicles: vehicles,
    availableDays: days,
    bootstrap,
    bootstrapStatus,
    comparisons,
    mobilityWeight: weight,
    spatialWeight: 100 - weight,
    sourceKinds: [...new Set(dataset.meta.sources.map((s) => s.kind))],
    scoreFilterScope: "static",
    filters: {
      mobility: weight,
      vehicle,
      day,
      time,
      selectedId: filters.selectedId || null,
    },
    quality: {
      status: "validated",
      sourceCount: dataset.meta.sources.length,
      candidateCount: candidates.length,
      geometryUnits: units.length,
    },
  };
}
const esc = (v) => '"' + String(v ?? "").replaceAll('"', '""') + '"';
export function exportWorkspaceCsv(dataset, filters = {}) {
  const a = deriveWorkspace(dataset, filters),
    headers = [
      "id",
      "name",
      "rank",
      "mobility",
      "spatial",
      "integrated",
      "mobility_weight",
      "spatial_weight",
      "source_id",
      "source_kind",
      "period_start",
      "period_end",
      "timezone",
      "gps_vehicle_filter",
      "gps_day_filter",
      "gps_time_filter",
    ];
  const rows = a.candidates.map((c) => [
    c.id,
    c.name,
    c.rank,
    c.mobility,
    c.spatial,
    c.score,
    a.mobilityWeight,
    a.spatialWeight,
    c.sourceId,
    dataset.meta.sources.find((s) => s.id === c.sourceId)?.kind,
    dataset.meta.period.start,
    dataset.meta.period.end,
    dataset.meta.period.timezone,
    a.filters.vehicle,
    a.filters.day,
    a.filters.time,
  ]);
  return (
    "\uFEFF" + [headers, ...rows].map((r) => r.map(esc).join(",")).join("\r\n")
  );
}
export function exportWorkspaceJson(dataset) {
  validateWorkspace(dataset);
  return JSON.stringify(dataset, null, 2);
}
