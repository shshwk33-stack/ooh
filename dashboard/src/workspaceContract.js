export const MAX_WORKSPACE_BYTES = 10 * 1024 * 1024;
export const SOURCE_KINDS = [
  "OBSERVED_GPS",
  "PUBLIC_AGGREGATE",
  "ESTIMATED",
  "SYNTHETIC",
  "DERIVED",
];
const finite = (v) => typeof v === "number" && Number.isFinite(v);
const text = (v) => typeof v === "string" && v.trim().length > 0;
const fail = (message) => {
  throw new Error(message);
};
const isScore = (v) => v === null || (finite(v) && v >= 0 && v <= 1);
function timestamp(value, label) {
  const match =
    typeof value === "string" &&
    value.match(
      /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?(Z|([+-])(\d{2}):(\d{2}))$/,
    );
  if (!match)
    fail(
      `${label}: UTC offset과 초를 포함한 ISO 시각이 필요합니다(최대 밀리초 정밀도).`,
    );
  const [year, month, day, hour, minute, second] = match
    .slice(1, 7)
    .map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0),
    days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const offsetHour = Number(match[10] || 0),
    offsetMinute = Number(match[11] || 0);
  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > days[month - 1] ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    offsetHour > 14 ||
    offsetMinute > 59 ||
    (offsetHour === 14 && offsetMinute !== 0) ||
    !Number.isFinite(Date.parse(value))
  )
    fail(`${label}: 실제 달력에 존재하는 날짜·시각·UTC offset이 필요합니다.`);
  return Date.parse(value);
}
function period(value, label) {
  if (!value || typeof value !== "object") fail(`${label}: 기간이 필요합니다.`);
  const a = timestamp(value.start, label + ".start"),
    b = timestamp(value.end, label + ".end");
  if (a > b) fail(`${label}: 시작 시각이 종료보다 늦습니다.`);
  try {
    new Intl.DateTimeFormat("en", { timeZone: value.timezone }).format();
  } catch {
    fail(`${label}: 유효한 IANA 시간대가 필요합니다.`);
  }
  if (!text(value.timezone)) fail(`${label}: 시간대가 필요합니다.`);
}
function coordinate(point, label) {
  if (
    !Array.isArray(point) ||
    point.length !== 2 ||
    !point.every(finite) ||
    point[0] < -180 ||
    point[0] > 180 ||
    point[1] < -85 ||
    point[1] > 85
  )
    fail(`${label}: 유효한 [경도, 위도]가 필요합니다(위도 ±85°).`);
}
function unique(items, key, label) {
  const ids = new Set();
  for (const item of items) {
    if (!item || !text(item[key]) || ids.has(item[key]))
      fail(`${label}: 비어 있지 않은 고유 ${key}가 필요합니다.`);
    ids.add(item[key]);
  }
  return ids;
}
function geometry(collection, label, allowed) {
  if (
    !collection ||
    collection.type !== "FeatureCollection" ||
    !Array.isArray(collection.features) ||
    collection.features.length > 20000
  )
    fail(`${label}: 최대 20,000개 GeoJSON 피처가 필요합니다.`);
  let coordinates = 0;
  for (const f of collection.features) {
    if (
      f?.type !== "Feature" ||
      !f.properties ||
      typeof f.properties !== "object" ||
      Array.isArray(f.properties) ||
      !allowed.includes(f.geometry?.type)
    )
      fail(`${label}: 지원하지 않는 피처/기하 형식입니다.`);
    for (const key of ["name", "unit"])
      if (
        f.properties[key] !== undefined &&
        typeof f.properties[key] !== "string"
      )
        fail(`${label}: ${key} 속성은 문자열이어야 합니다.`);
    if (
      f.properties.link_id !== undefined &&
      !["string", "number"].includes(typeof f.properties.link_id)
    )
      fail(`${label}: link_id 속성을 확인하세요.`);
    for (const key of ["value", "population", "traffic"])
      if (
        f.properties[key] !== undefined &&
        f.properties[key] !== null &&
        !finite(f.properties[key])
      )
        fail(`${label}: ${key} 속성은 유한 숫자여야 합니다.`);
    const g = f.geometry;
    const line = (points) => {
      if (!Array.isArray(points) || points.length < 2)
        fail(`${label}: 선의 좌표가 부족합니다.`);
      for (const p of points) {
        coordinate(p, label);
        coordinates++;
      }
    };
    const ring = (points) => {
      line(points);
      if (
        points.length < 4 ||
        points[0][0] !== points.at(-1)[0] ||
        points[0][1] !== points.at(-1)[1]
      )
        fail(`${label}: 닫힌 polygon ring이 필요합니다.`);
    };
    const polygon = (polys) => {
      if (!Array.isArray(polys) || !polys.length)
        fail(`${label}: polygon ring이 없습니다.`);
      polys.forEach(ring);
    };
    if (g.type === "Point") {
      coordinate(g.coordinates, label);
      coordinates++;
    } else if (g.type === "LineString") line(g.coordinates);
    else if (g.type === "MultiLineString") {
      if (!Array.isArray(g.coordinates) || !g.coordinates.length)
        fail(`${label}: 선 좌표가 없습니다.`);
      g.coordinates.forEach(line);
    } else if (g.type === "Polygon") polygon(g.coordinates);
    else if (g.type === "MultiPolygon") {
      if (!Array.isArray(g.coordinates) || !g.coordinates.length)
        fail(`${label}: polygon이 없습니다.`);
      g.coordinates.forEach(polygon);
    }
    if (coordinates > 300000)
      fail(`${label}: 좌표가 300,000개를 초과했습니다.`);
  }
}
export function validateWorkspace(data) {
  if (!data || data.schemaVersion !== "2.0")
    fail("지원하는 데이터 형식은 schemaVersion 2.0입니다.");
  const m = data.meta;
  if (!m || !["id", "name", "version", "region"].every((k) => text(m[k])))
    fail("자료 ID·이름·버전·연구지역이 필요합니다.");
  period(m.period, "meta.period");
  if (!Array.isArray(m.sources) || !m.sources.length)
    fail("자료별 출처 명세가 필요합니다.");
  const sources = unique(m.sources, "id", "sources");
  for (const s of m.sources) {
    if (!text(s.label) || !SOURCE_KINDS.includes(s.kind))
      fail("자료 출처 이름과 분류를 확인하세요.");
    for (const key of ["unit", "description", "method"])
      if (s[key] !== undefined && typeof s[key] !== "string")
        fail(`출처 ${key}는 문자열이어야 합니다.`);
    if (
      s.year !== undefined &&
      !(Number.isInteger(s.year) && s.year > 0) &&
      !(typeof s.year === "string" && /^\d{4}$/.test(s.year))
    )
      fail("출처 기준연도는 연도 숫자여야 합니다.");
    if (s.url !== undefined) {
      let u;
      try {
        u = new URL(s.url);
      } catch {
        fail("출처 URL은 전체 HTTP(S) 주소여야 합니다.");
      }
      if (!["http:", "https:"].includes(u.protocol) || u.username || u.password)
        fail("출처 URL에는 HTTP(S) 주소만 허용합니다.");
    }
  }
  const g = data.geometry;
  if (g?.crs !== "EPSG:4326")
    fail("지도 데이터의 CRS는 EPSG:4326이어야 합니다.");
  geometry(g.district, "district", ["Polygon", "MultiPolygon"]);
  geometry(g.units, "units", ["Polygon", "MultiPolygon"]);
  geometry(g.roads, "roads", ["LineString", "MultiLineString"]);
  geometry(g.routes, "routes", ["LineString", "MultiLineString"]);
  geometry(g.population, "population", ["Polygon", "MultiPolygon", "Point"]);
  geometry(g.poi, "poi", ["Point"]);
  const unitCodes = unique(
    g.units.features.map((f) => ({ id: String(f.properties.code || "") })),
    "id",
    "행정단위",
  );
  if (!Array.isArray(data.candidates) || data.candidates.length > 1000)
    fail("후보지역은 최대 1,000개입니다.");
  const candidates = unique(data.candidates, "id", "후보지역");
  for (const c of data.candidates) {
    if (!text(c.name) || !text(c.short) || !sources.has(c.sourceId))
      fail("후보지역 이름·약칭·출처 ID가 필요합니다.");
    coordinate([c.longitude, c.latitude], "후보 좌표");
    if (!isScore(c.mobility) || !isScore(c.spatial))
      fail("Mobility/Spatial은 0–1 숫자 또는 null이어야 합니다.");
    if (
      c.unitCode !== null &&
      c.unitCode !== undefined &&
      !unitCodes.has(String(c.unitCode))
    )
      fail("후보의 행정단위 코드가 실제 경계에 없습니다.");
    if (c.metrics !== undefined) {
      if (
        !c.metrics ||
        typeof c.metrics !== "object" ||
        Array.isArray(c.metrics)
      )
        fail("metrics는 객체여야 합니다.");
      for (const v of Object.values(c.metrics))
        if (v !== null && (!finite(v) || v < 0))
          fail("지표는 0 이상의 유한 숫자 또는 null이어야 합니다.");
    }
    if (c.metricUnits !== undefined) {
      if (
        !c.metricUnits ||
        typeof c.metricUnits !== "object" ||
        Array.isArray(c.metricUnits) ||
        Object.values(c.metricUnits).some(
          (unit) => typeof unit !== "string" || unit.length > 60,
        )
      )
        fail("metricUnits는 지표 이름별 단위 문자열이어야 합니다.");
    }
  }
  if (
    !data.gps ||
    !sources.has(data.gps.sourceId) ||
    !Array.isArray(data.gps.positions) ||
    data.gps.positions.length > 50000
  )
    fail("GPS 출처와 최대 50,000개 기록을 확인하세요.");
  unique(data.gps.positions, "id", "GPS");
  const instants = new Set();
  for (const p of data.gps.positions) {
    if (!text(p.vehicleId)) fail("GPS 차량 ID가 필요합니다.");
    timestamp(p.timestamp, "GPS 시각");
    coordinate([p.longitude, p.latitude], "GPS 좌표");
    const key = p.vehicleId + "|" + Date.parse(p.timestamp);
    if (instants.has(key)) fail("동일 차량·시각의 GPS가 중복되었습니다.");
    instants.add(key);
    if (
      p.unitCode !== null &&
      p.unitCode !== undefined &&
      !unitCodes.has(String(p.unitCode))
    )
      fail("GPS 행정단위 코드가 경계에 없습니다.");
  }
  const b = data.bootstrap;
  if (b !== null) {
    if (
      !b ||
      !sources.has(b.sourceId) ||
      m.sources.find((s) => s.id === b.sourceId)?.kind !== "DERIVED"
    )
      fail("안정성 결과는 DERIVED 출처를 명시해야 합니다.");
    if (
      !Number.isInteger(b.iterations) ||
      b.iterations < 1 ||
      !Number.isInteger(b.seed) ||
      !text(b.resampleUnit) ||
      !finite(b.weight) ||
      b.weight < 0 ||
      b.weight > 100 ||
      !Number.isInteger(b.topK) ||
      b.topK < 1
    )
      fail("안정성 반복수·seed·표본 단위·가중치·Top-K를 확인하세요.");
    period(b.period, "bootstrap.period");
    if (!Array.isArray(b.results)) fail("안정성 결과 목록이 필요합니다.");
    unique(b.results, "candidateId", "안정성");
    for (const r of b.results)
      if (
        !candidates.has(r.candidateId) ||
        !finite(r.meanRank) ||
        r.meanRank < 1 ||
        !finite(r.rankSD) ||
        r.rankSD < 0 ||
        !finite(r.topKProbability) ||
        r.topKProbability < 0 ||
        r.topKProbability > 1
      )
        fail("후보별 안정성 결과를 확인하세요.");
  }
  return data;
}
export function parseWorkspaceJson(value) {
  if (
    typeof value !== "string" ||
    new TextEncoder().encode(value).byteLength > MAX_WORKSPACE_BYTES
  )
    fail("JSON 자료는 최대 10MB입니다.");
  let parsed;
  try {
    parsed = JSON.parse(value);
  } catch {
    fail("유효한 JSON 파일이 아닙니다.");
  }
  // JSON.parse discards duplicate members, so check keys before using the parsed result.
  const stack = [];
  for (let i = 0; i < value.length; i++) {
    const ch = value[i];
    if (ch === '"') {
      const start = i++;
      for (; i < value.length; i++) {
        if (value[i] === "\\") {
          i++;
          continue;
        }
        if (value[i] === '"') break;
      }
      const top = stack.at(-1);
      if (top?.object && top.key) {
        const key = JSON.parse(value.slice(start, i + 1));
        if (top.keys.has(key)) fail("JSON 객체에 중복된 키가 있습니다.");
        top.keys.add(key);
        top.key = false;
      }
    } else if (ch === "{")
      stack.push({ object: true, key: true, keys: new Set() });
    else if (ch === "[") stack.push({ object: false });
    else if (ch === "}" || ch === "]") stack.pop();
    else if (ch === "," && stack.at(-1)?.object) stack.at(-1).key = true;
  }
  return validateWorkspace(parsed);
}

export const CSV_COLUMNS = [
  "id",
  "name",
  "short",
  "longitude",
  "latitude",
  "mobility",
  "spatial",
  "unit_code",
  "source_id",
  "source_label",
  "source_kind",
  "period_start",
  "period_end",
  "timezone",
];
const csvEscape = (v) => '"' + String(v ?? "").replaceAll('"', '""') + '"';
export function exportCandidatesTemplate() {
  return "\uFEFF" + CSV_COLUMNS.join(",") + "\r\n";
}
export function parseCsv(value) {
  if (
    typeof value !== "string" ||
    new TextEncoder().encode(value).byteLength > MAX_WORKSPACE_BYTES
  )
    fail("CSV 자료는 최대 10MB입니다.");
  const s = value.replace(/^\uFEFF/, "");
  const rows = [];
  let row = [],
    field = "",
    quoted = false,
    closed = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (quoted) {
      if (ch === '"') {
        if (s[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          quoted = false;
          closed = true;
        }
      } else field += ch;
      continue;
    }
    if (ch === '"') {
      if (field.length || closed) fail("CSV 인용부호 위치를 확인하세요.");
      quoted = true;
      continue;
    }
    if (ch === "," || ch === "\n" || ch === "\r") {
      row.push(field);
      field = "";
      closed = false;
      if (ch !== ",") {
        rows.push(row);
        row = [];
        if (ch === "\r" && s[i + 1] === "\n") i++;
      }
      continue;
    }
    if (closed) fail("CSV 닫힌 인용부호 뒤에 문자가 있습니다.");
    field += ch;
  }
  if (quoted) fail("CSV 인용부호가 닫히지 않았습니다.");
  if (field.length || closed || row.length) {
    row.push(field);
    rows.push(row);
  }
  if (!rows.length) fail("CSV가 비었습니다.");
  const header = rows.shift();
  if (
    new Set(header).size !== header.length ||
    CSV_COLUMNS.some((c) => !header.includes(c))
  )
    fail("CSV 필수 열 또는 고유 헤더를 확인하세요.");
  if (!rows.length || rows.length > 1000)
    fail("CSV는 후보 1–1,000개를 포함해야 합니다.");
  return rows.map((r) => {
    if (r.length !== header.length) fail("CSV 열 개수가 일치하지 않습니다.");
    return Object.fromEntries(header.map((h, i) => [h, r[i]]));
  });
}
export function importCandidatesCsv(csvText, base) {
  validateWorkspace(base);
  const rows = parseCsv(csvText),
    sources = new Map(base.meta.sources.map((s) => [s.id, { ...s }]));
  const first = rows[0];
  const p = {
    start: first.period_start,
    end: first.period_end,
    timezone: first.timezone,
  };
  period(p, "CSV 기간");
  const number = (value, label, nullable = false) => {
    if (nullable && value.trim() === "") return null;
    if (
      !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim()) ||
      !Number.isFinite(Number(value))
    )
      fail(`${label}: 숫자가 필요합니다.`);
    return Number(value);
  };
  const candidates = rows.map((r) => {
    if (
      r.period_start !== first.period_start ||
      r.period_end !== first.period_end ||
      r.timezone !== first.timezone
    )
      fail("CSV 후보의 분석기간·시간대가 서로 다릅니다.");
    if (
      !SOURCE_KINDS.includes(r.source_kind) ||
      !text(r.source_id) ||
      !text(r.source_label)
    )
      fail("CSV 출처 ID·이름·분류가 필요합니다.");
    const existing = sources.get(r.source_id);
    if (
      existing &&
      (existing.kind !== r.source_kind || existing.label !== r.source_label)
    )
      fail("같은 출처 ID의 분류·이름이 충돌합니다.");
    sources.set(r.source_id, {
      ...(existing || {}),
      id: r.source_id,
      label: r.source_label,
      kind: r.source_kind,
    });
    return {
      id: r.id,
      name: r.name,
      short: r.short,
      longitude: number(r.longitude, "longitude"),
      latitude: number(r.latitude, "latitude"),
      mobility: number(r.mobility, "mobility", true),
      spatial: number(r.spatial, "spatial", true),
      unitCode: r.unit_code || null,
      sourceId: r.source_id,
      metrics: {},
    };
  });
  const result = {
    ...base,
    meta: {
      ...base.meta,
      id: base.meta.id + "-csv",
      name: "가져온 후보지역",
      version: "CSV",
      period: p,
      sources: [...sources.values()],
      scoreTemporalResolution: "static",
    },
    candidates,
    bootstrap: null,
  };
  return validateWorkspace(result);
}
export function exportCandidatesCsv(data) {
  validateWorkspace(data);
  const rows = data.candidates.map((c) => {
    const s = data.meta.sources.find((s) => s.id === c.sourceId);
    return [
      c.id,
      c.name,
      c.short,
      c.longitude,
      c.latitude,
      c.mobility,
      c.spatial,
      c.unitCode,
      s.id,
      s.label,
      s.kind,
      data.meta.period.start,
      data.meta.period.end,
      data.meta.period.timezone,
    ];
  });
  return (
    "\uFEFF" +
    [CSV_COLUMNS, ...rows]
      .map((row) => row.map(csvEscape).join(","))
      .join("\r\n")
  );
}
export async function fetchWorkspace(
  url,
  { signal, timeoutMs = 15000, fetchImpl = globalThis.fetch } = {},
) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    fail("API의 전체 HTTP(S) 주소를 입력하세요.");
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password
  )
    fail("인증정보가 없는 HTTP(S) API 주소만 지원합니다.");
  if (
    [...parsed.searchParams.keys()].some((k) =>
      /token|secret|api.?key|authorization/i.test(k),
    )
  )
    fail("API 비밀키는 서버 측 프록시에서 관리하세요.");
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(parsed.href, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "omit",
      signal: controller.signal,
      redirect: "error",
    });
    if (!response.ok) fail(`API 응답 오류: HTTP ${response.status}`);
    if (
      !/application\/(?:[\w.-]+\+)?json/i.test(
        response.headers.get("content-type") || "",
      )
    )
      fail("API는 application/json 응답을 반환해야 합니다.");
    const length = Number(response.headers.get("content-length"));
    if (length > MAX_WORKSPACE_BYTES) fail("API 응답은 최대 10MB입니다.");
    const reader = response.body?.getReader();
    if (!reader) return parseWorkspaceJson(await response.text());
    const decoder = new TextDecoder();
    let size = 0,
      body = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_WORKSPACE_BYTES) {
        await reader.cancel();
        fail("API 응답은 최대 10MB입니다.");
      }
      body += decoder.decode(value, { stream: true });
    }
    body += decoder.decode();
    return parseWorkspaceJson(body);
  } catch (error) {
    if (controller.signal.aborted)
      throw new Error("API 연결이 취소되었거나 응답 시간이 초과되었습니다.");
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
