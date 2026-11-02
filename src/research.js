import { rankCandidates } from "./model.js";
export const locations = {
  "MP-024": [37.5572, 126.9245],
  "MP-018": [37.5445, 126.9515],
  "MP-041": [37.5496, 126.9139],
  "MP-032": [37.5477, 126.9229],
  "MP-009": [37.5561, 126.9055],
  "MP-056": [37.5478, 126.9425],
  "MP-063": [37.5396, 126.9459],
  "MP-015": [37.5627, 126.9257],
};
export const weights = Array.from({ length: 21 }, (_, i) => i * 5);
export function rankOf(id, alpha, time = "all", area = "all") {
  return rankCandidates(alpha, time, area).findIndex((c) => c.id === id) + 1;
}
export function stability(id, time = "all", area = "all") {
  const ranks = weights.map((a) => rankOf(id, a, time, area));
  return {
    best: Math.min(...ranks),
    worst: Math.max(...ranks),
    top3: ranks.filter((r) => r <= 3).length,
    ranks,
  };
}
export function decomposition(c, alpha, time) {
  const mobility = (c.mobility * alpha) / 100,
    spatial = c.spatial * (1 - alpha / 100),
    factor = time === "morning" ? 0.91 : time === "evening" ? 1.06 : 1;
  return {
    mobility,
    spatial,
    factor,
    raw: mobility + spatial,
    final: Math.min(0.99, (mobility + spatial) * factor),
  };
}
export function validateRoads(data) {
  if (
    data?.type !== "FeatureCollection" ||
    !Array.isArray(data.features) ||
    !data.features.length
  )
    throw Error("비어 있지 않은 GeoJSON FeatureCollection이 필요합니다.");
  if (data.features.length > 20000)
    throw Error("20,000개 이하의 도로 피처를 불러올 수 있습니다.");
  for (const f of data.features) {
    if (!["LineString", "MultiLineString"].includes(f.geometry?.type))
      throw Error("도로는 LineString 또는 MultiLineString이어야 합니다.");
    const lines =
      f.geometry.type === "LineString"
        ? [f.geometry.coordinates]
        : f.geometry.coordinates;
    if (!Array.isArray(lines) || !lines.length)
      throw Error("도로 좌표가 없습니다.");
    for (const line of lines) {
      if (!Array.isArray(line) || line.length < 2)
        throw Error("도로 선에는 최소 두 좌표가 필요합니다.");
      for (const p of line) {
        if (
          !Array.isArray(p) ||
          p.length < 2 ||
          !Number.isFinite(p[0]) ||
          !Number.isFinite(p[1]) ||
          p[0] < 124 ||
          p[0] > 132 ||
          p[1] < 33 ||
          p[1] > 39
        )
          throw Error("한국 지역 WGS84 [경도, 위도] 좌표가 필요합니다.");
      }
    }
    if (
      f.properties?.traffic != null &&
      (!Number.isFinite(f.properties.traffic) || f.properties.traffic < 0)
    )
      throw Error("traffic은 0 이상의 숫자여야 합니다.");
  }
  return data;
}
