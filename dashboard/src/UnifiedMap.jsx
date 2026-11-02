import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  Crosshair,
  Expand,
  Layers3,
  LocateFixed,
  Minus,
  Plus,
  X,
} from "lucide-react";
import "./UnifiedMap.css";

const W = 1000,
  H = 660,
  PAD = 52,
  R = 6378137;
const MODES = [
  ["integrated", "통합 위치가치"],
  ["mobility", "이동특성"],
  ["spatial", "공간특성"],
  ["routes", "차량 경로"],
  ["boundaries", "행정경계"],
];
const INITIAL = {
  units: true,
  labels: true,
  value: true,
  candidates: true,
  roads: true,
  routes: true,
  points: false,
  population: false,
  poi: false,
};
const PALETTE = [
  "#284a62",
  "#3d6f7b",
  "#589586",
  "#b2ad68",
  "#d5a552",
  "#dc814f",
];
const ROUTE_COLORS = ["#61d0c3", "#edc26b", "#9aabd9", "#ce9bba"];
const emptyFC = { type: "FeatureCollection", features: [] };
const features = (fc) => fc?.features || [];
const coordinate = (c) => [
  Number(c.longitude ?? c.lon),
  Number(c.latitude ?? c.lat),
];

// EPSG:3857 is used only for display. Ground scale compensates for latitude;
// research measurements and provenance remain in the dataset's own contract.
function mercator([lon, lat]) {
  const limited = Math.max(-85.05112878, Math.min(85.05112878, lat));
  return [
    (R * lon * Math.PI) / 180,
    R * Math.log(Math.tan(Math.PI / 4 + (limited * Math.PI) / 360)),
  ];
}
function extent(points) {
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const [x, y] of points) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return points.length ? [minX, minY, maxX, maxY] : [0, 0, 1, 1];
}
function polygons(geometry) {
  return geometry?.type === "Polygon"
    ? [geometry.coordinates]
    : geometry?.type === "MultiPolygon"
      ? geometry.coordinates
      : [];
}
function lines(geometry) {
  return geometry?.type === "LineString"
    ? [geometry.coordinates]
    : geometry?.type === "MultiLineString"
      ? geometry.coordinates
      : [];
}
function unitCode(feature) {
  return String(feature.properties?.code ?? feature.id ?? "");
}
function metricOf(candidate, mode) {
  const value =
    mode === "mobility"
      ? candidate.mobility
      : mode === "spatial"
        ? candidate.spatial
        : (candidate.score ?? candidate.integrated);
  return Number.isFinite(value) ? value : null;
}
function colorOf(value) {
  return value == null
    ? "#25474a"
    : PALETTE[
        Math.max(
          0,
          Math.min(PALETTE.length - 1, Math.floor(value * PALETTE.length)),
        )
      ];
}
function centerOf(feature) {
  const ring = polygons(feature.geometry)[0]?.[0] || [];
  if (!ring.length) return [0, 0];
  const coords = ring.map(mercator);
  let area = 0,
    cx = 0,
    cy = 0;
  for (let i = 0, j = coords.length - 1; i < coords.length; j = i++) {
    const cross = coords[j][0] * coords[i][1] - coords[i][0] * coords[j][1];
    area += cross;
    cx += (coords[j][0] + coords[i][0]) * cross;
    cy += (coords[j][1] + coords[i][1]) * cross;
  }
  if (Math.abs(area) > 0.001) return [cx / (3 * area), cy / (3 * area)];
  const b = extent(coords);
  return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
}
function dayOf(position, timezone) {
  if (position.day) return position.day;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone || "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(position.timestamp));
}

export default function UnifiedMap({
  dataset,
  analysis,
  selectedId,
  onSelect,
  selectedUnit,
  onUnitSelect,
  mode = "integrated",
  onModeChange,
}) {
  const svg = useRef(null),
    stage = useRef(null),
    drag = useRef(null),
    wasDragged = useRef(false);
  const [zoom, setZoom] = useState(1),
    [pan, setPan] = useState({ x: 0, y: 0 });
  const [layers, setLayers] = useState(INITIAL),
    [layerOpen, setLayerOpen] = useState(false),
    [full, setFull] = useState(false);
  const [scale, setScale] = useState(1),
    [hover, setHover] = useState(null);
  const geometry = dataset.geometry || {};
  const units = features(geometry.units),
    district = features(geometry.district),
    roads = features(geometry.roads),
    sourceRoutes = features(geometry.routes);
  const population = features(geometry.population),
    poi = features(geometry.poi);
  const candidates = analysis?.candidates || dataset.candidates || [];
  const positions =
    analysis?.filteredPositions ||
    analysis?.positions ||
    dataset.gps?.positions ||
    [];
  const selectedCode =
    typeof selectedUnit === "object" ? selectedUnit?.code : selectedUnit;
  const canonicalMode = mode === "value" ? "integrated" : mode;
  const valueMode = ["integrated", "mobility", "spatial"].includes(
    canonicalMode,
  );
  const layerOptions = [
    ["units", "행정경계", true],
    ["labels", "행정동 이름", true],
    [
      "value",
      "위치가치 분포",
      candidates.some((c) => metricOf(c, canonicalMode) != null),
    ],
    ["candidates", "후보지역", candidates.length > 0],
    ["roads", "도로망", roads.length > 0],
    ["routes", "차량 경로", positions.length > 1 || sourceRoutes.length > 0],
    ["points", "GPS 기록점", positions.length > 0],
    ["population", "인구 활동", population.length > 0],
    ["poi", "POI · 상권", poi.length > 0],
  ];
  const unitValues = useMemo(() => {
    const result = new Map();
    for (const candidate of candidates) {
      const value = metricOf(candidate, canonicalMode);
      if (value == null || candidate.unitCode == null) continue;
      const key = String(candidate.unitCode),
        group = result.get(key) || [];
      group.push(value);
      result.set(key, group);
    }
    return new Map(
      [...result].map(([key, values]) => [
        key,
        values.reduce((a, b) => a + b, 0) / values.length,
      ]),
    );
  }, [candidates, canonicalMode]);
  const mapBounds = useMemo(() => {
    const points = [...units, ...district].flatMap((f) =>
      polygons(f.geometry).flat(2).map(mercator),
    );
    return extent(
      points.length ? points : candidates.map((c) => mercator(coordinate(c))),
    );
  }, [dataset]);
  const [minX, minY, maxX, maxY] = mapBounds;
  const pxPerM = Math.min(
    (W - PAD * 2) / Math.max(1, maxX - minX),
    (H - PAD * 2) / Math.max(1, maxY - minY),
  );
  const x0 = (W - (maxX - minX) * pxPerM) / 2,
    y0 = (H - (maxY - minY) * pxPerM) / 2;
  const projectMetric = ([x, y]) => [
    x0 + (x - minX) * pxPerM,
    y0 + (maxY - y) * pxPerM,
  ];
  const project = (point) => projectMetric(mercator(point));
  const polygonPath = (feature) =>
    polygons(feature.geometry)
      .map((p) =>
        p
          .map(
            (ring) =>
              ring
                .map(
                  (point, i) =>
                    `${i ? "L" : "M"}${project(point)
                      .map((n) => n.toFixed(2))
                      .join(",")}`,
                )
                .join("") + "Z",
          )
          .join(""),
      )
      .join("");
  const linePoints = (line) =>
    line
      .map((point) =>
        project(point)
          .map((n) => n.toFixed(2))
          .join(","),
      )
      .join(" ");
  const gpsRoutes = useMemo(() => {
    const result = new Map();
    for (const p of positions) {
      const key = `${p.vehicleId}|${dayOf(p, dataset.meta?.period?.timezone)}`;
      if (!result.has(key)) result.set(key, []);
      result.get(key).push(p);
    }
    return [...result].map(([id, points]) => ({
      id,
      vehicle: points[0].vehicleId,
      points: [...points].sort((a, b) =>
        a.timestamp.localeCompare(b.timestamp),
      ),
    }));
  }, [positions, dataset]);
  const vehicleIds = [
    ...new Set((dataset.gps?.positions || []).map((p) => p.vehicleId)),
  ].sort();
  const routeColor = (id) =>
    ROUTE_COLORS[Math.max(0, vehicleIds.indexOf(id)) % ROUTE_COLORS.length];
  const averageLatitude = candidates.length
    ? candidates.reduce((total, c) => total + c.latitude, 0) / candidates.length
    : 37.55;
  const groundFactor = Math.cos((averageLatitude * Math.PI) / 180);
  const groundPxPerM = (pxPerM / groundFactor) * zoom * scale;
  const scaleM =
    [2000, 1000, 500, 250, 100, 50, 20].find((m) => m * groundPxPerM <= 125) ||
    20;

  const fit = (points, closeLayers = true) => {
    if (!points.length) return;
    const b = extent(points.map(mercator)),
      centre = projectMetric([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]);
    const next = Math.max(
      1,
      Math.min(
        10,
        Math.min(
          (W - 190) / Math.max(1, (b[2] - b[0]) * pxPerM),
          (H - 170) / Math.max(1, (b[3] - b[1]) * pxPerM),
        ),
      ),
    );
    setZoom(next);
    setPan({ x: (W / 2 - centre[0]) * next, y: (H / 2 - centre[1]) * next });
    if (closeLayers) setLayerOpen(false);
  };
  const reset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };
  useEffect(() => {
    if (candidates.length > 1) fit(candidates.map(coordinate), false);
    else reset();
  }, [dataset]);
  useEffect(() => {
    const element = svg.current;
    const update = () => {
      const r = element.getBoundingClientRect();
      setScale(Math.min(r.width / W, r.height / H));
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const element = stage.current;
    const wheel = (e) => {
      e.preventDefault();
      setZoom((z) =>
        Math.max(1, Math.min(12, z * (e.deltaY < 0 ? 1.14 : 1 / 1.14))),
      );
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);
  useEffect(() => {
    if (!full) return;
    const close = (e) => {
      if (e.key === "Escape") setFull(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [full]);
  const eventPoint = (e) => {
    const p = svg.current.createSVGPoint();
    p.x = e.clientX;
    p.y = e.clientY;
    const out = p.matrixTransform(svg.current.getScreenCTM().inverse());
    return [out.x, out.y];
  };
  const pointerDown = (e) => {
    if (e.button !== 0) return;
    const [x, y] = eventPoint(e);
    wasDragged.current = false;
    drag.current = { x, y, pan };
  };
  const pointerMove = (e) => {
    if (!drag.current) return;
    const [x, y] = eventPoint(e);
    if (
      !wasDragged.current &&
      Math.hypot(x - drag.current.x, y - drag.current.y) < 4
    )
      return;
    wasDragged.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    setPan({
      x: drag.current.pan.x + x - drag.current.x,
      y: drag.current.pan.y + y - drag.current.y,
    });
  };
  const candidateSelected = candidates.find((c) => c.id === selectedId);
  const scoreName =
    canonicalMode === "mobility"
      ? "Mobility Score"
      : canonicalMode === "spatial"
        ? "Spatial Score"
        : "Integrated Score";
  const scoreRange = candidates
    .map((c) => metricOf(c, canonicalMode))
    .filter((v) => v != null);
  const markerUnit = 1 / Math.max(0.001, zoom * scale);
  const grid = [],
    step = (maxX - minX) / 12;
  if (step > 0)
    for (let n = 0; n <= 12; n++)
      grid.push([minX + step * n, minY + ((maxY - minY) * n) / 12]);
  const routeView = canonicalMode === "routes";

  return (
    <div
      className={`unified-map ${full ? "unified-map-expanded" : ""}`}
      data-testid="unified-map"
    >
      <div
        className="unified-map-tabs"
        role="tablist"
        aria-label="지도 분석 모드"
      >
        {MODES.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={canonicalMode === id}
            onClick={() => onModeChange?.(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="unified-map-stage" ref={stage}>
        <svg
          className="unified-map-svg"
          ref={svg}
          viewBox={`0 0 ${W} ${H}`}
          aria-label="실제 행정경계 기반 후보지역 위치가치 지도"
          role="group"
          onPointerDown={pointerDown}
          onPointerMove={pointerMove}
          onPointerUp={() => {
            drag.current = null;
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
        >
          <defs>
            <pattern
              id="unified-no-score"
              width="11"
              height="11"
              patternUnits="userSpaceOnUse"
            >
              <rect width="11" height="11" fill="#203e45" />
              <path
                d="M-3 3L3-3M0 11L11 0M8 14L14 8"
                stroke="#42625f"
                strokeWidth=".6"
                opacity=".3"
              />
            </pattern>
          </defs>
          <rect width={W} height={H} fill="#102d37" />
          <g
            transform={`translate(${W / 2 + pan.x},${H / 2 + pan.y}) scale(${zoom}) translate(${-W / 2},${-H / 2})`}
            data-testid="unified-map-transform"
          >
            <g className="unified-map-grid" aria-hidden="true">
              {grid.map(([x, y], i) => (
                <g key={i}>
                  <line
                    x1={projectMetric([x, minY])[0]}
                    x2={projectMetric([x, minY])[0]}
                    y1="-400"
                    y2="1000"
                  />
                  <line
                    x1="-400"
                    x2="1600"
                    y1={projectMetric([minX, y])[1]}
                    y2={projectMetric([minX, y])[1]}
                  />
                </g>
              ))}
            </g>
            {layers.units && (
              <g data-layer="unified-units">
                {units.map((feature) => {
                  const code = unitCode(feature),
                    value = unitValues.get(code),
                    active =
                      String(selectedCode || candidateSelected?.unitCode) ===
                      code;
                  return (
                    <path
                      key={code}
                      d={polygonPath(feature)}
                      fillRule="evenodd"
                      className={`unified-unit ${active ? "selected" : ""}`}
                      fill={
                        layers.value && valueMode
                          ? value == null
                            ? "url(#unified-no-score)"
                            : colorOf(value)
                          : "#254c4e"
                      }
                      data-unit-code={code}
                      role="button"
                      tabIndex={0}
                      aria-label={`${feature.properties?.name || code} 행정동 선택`}
                      aria-pressed={active}
                      onClick={() => {
                        if (!wasDragged.current) onUnitSelect?.(code);
                      }}
                      onKeyDown={(e) => {
                        if (["Enter", " "].includes(e.key)) {
                          e.preventDefault();
                          onUnitSelect?.(code);
                        }
                      }}
                    >
                      <title>
                        {feature.properties?.name} ·{" "}
                        {value == null
                          ? "연결된 후보 점수 없음"
                          : `후보 점수 평균 ${value.toFixed(3)}`}
                      </title>
                    </path>
                  );
                })}
              </g>
            )}
            <g className="unified-district">
              {district.map((feature, i) => (
                <path key={i} d={polygonPath(feature)} fill="none" />
              ))}
            </g>
            {layers.population && (
              <g data-layer="unified-population">
                {population.map((feature, i) => {
                  const tooltip = `${feature.properties?.name || "인구 활동"} · ${feature.properties?.value ?? feature.properties?.population ?? "원본 자료"}${feature.properties?.unit ? ` ${feature.properties.unit}` : ""}`;
                  if (feature.geometry?.type === "Point") {
                    const [x, y] = project(feature.geometry.coordinates),
                      radius = 5 / Math.max(0.001, zoom * scale);
                    return (
                      <circle
                        key={i}
                        cx={x}
                        cy={y}
                        r={radius}
                        fill="#aaa0d0"
                        fillOpacity=".78"
                        stroke="#d3c9ea"
                        strokeWidth={1 / Math.max(0.001, zoom * scale)}
                      >
                        <title>{tooltip}</title>
                      </circle>
                    );
                  }
                  return (
                    <path
                      key={i}
                      d={polygonPath(feature)}
                      fill="#756d9c"
                      fillOpacity=".42"
                    >
                      <title>{tooltip}</title>
                    </path>
                  );
                })}
              </g>
            )}
            {layers.roads && (
              <g className="unified-roads" data-layer="unified-roads">
                {roads.flatMap((feature, i) =>
                  lines(feature.geometry).map((line, j) => (
                    <polyline
                      key={`${i}-${j}`}
                      points={linePoints(line)}
                      fill="none"
                      stroke={
                        Number.isFinite(feature.properties?.traffic)
                          ? feature.properties.traffic > 10000
                            ? "#e6bd64"
                            : "#a9b9a2"
                          : "#7da398"
                      }
                    >
                      <title>
                        {feature.properties?.name ||
                          feature.properties?.link_id ||
                          "도로 링크"}
                        {feature.properties?.traffic != null
                          ? ` · ${feature.properties.traffic} ${feature.properties?.unit || "(원본 단위)"}`
                          : ""}
                      </title>
                    </polyline>
                  )),
                )}
              </g>
            )}
            {layers.routes && (
              <g data-layer="unified-routes">
                {sourceRoutes.flatMap((feature, i) =>
                  lines(feature.geometry).map((line, j) => (
                    <polyline
                      key={`source-${i}-${j}`}
                      points={linePoints(line)}
                      className="unified-source-route"
                      fill="none"
                    />
                  )),
                )}
                {gpsRoutes.map((route) => (
                  <polyline
                    key={route.id}
                    fill="none"
                    points={linePoints(route.points.map(coordinate))}
                    stroke={routeColor(route.vehicle)}
                    strokeWidth={(routeView ? 3.4 : 2.3) / zoom}
                    opacity={routeView ? 0.96 : 0.75}
                    strokeLinecap="round"
                  >
                    <title>
                      {route.vehicle} · {route.id.split("|")[1]} · 위치기록
                      연결선
                    </title>
                  </polyline>
                ))}
              </g>
            )}
            {layers.points && (
              <g data-layer="unified-points">
                {positions.map((position, i) => {
                  const [x, y] = project(coordinate(position));
                  return (
                    <circle
                      key={position.id || i}
                      cx={x}
                      cy={y}
                      r={2.7 / zoom}
                      fill={routeColor(position.vehicleId)}
                      stroke="#ebf7f0"
                      strokeWidth={0.65 / zoom}
                      onMouseEnter={() => setHover(position)}
                      onMouseLeave={() => setHover(null)}
                      tabIndex={0}
                      onFocus={() => setHover(position)}
                      onBlur={() => setHover(null)}
                    >
                      <title>
                        {position.vehicleId} · {position.timestamp}
                      </title>
                    </circle>
                  );
                })}
              </g>
            )}
            {layers.poi && (
              <g data-layer="unified-poi">
                {poi.map((feature, i) => {
                  if (feature.geometry?.type !== "Point") return null;
                  const [x, y] = project(feature.geometry.coordinates);
                  return (
                    <circle
                      key={i}
                      cx={x}
                      cy={y}
                      r={3.4 / zoom}
                      fill="#e9c877"
                      stroke="#132e30"
                      strokeWidth={1 / zoom}
                    >
                      <title>{feature.properties?.name || "POI"}</title>
                    </circle>
                  );
                })}
              </g>
            )}
            {layers.labels && (
              <g className="unified-unit-labels" pointerEvents="none">
                {units.map((feature) => {
                  const p = projectMetric(centerOf(feature));
                  return (
                    <text
                      key={unitCode(feature)}
                      x={p[0]}
                      y={p[1]}
                      fontSize={11 / Math.sqrt(zoom)}
                    >
                      {feature.properties?.name}
                    </text>
                  );
                })}
              </g>
            )}
            {layers.candidates && (
              <g data-layer="unified-candidates">
                {candidates.map((candidate, i) => {
                  const [x, y] = project(coordinate(candidate)),
                    active = candidate.id === selectedId,
                    fullLabel = candidate.short || candidate.name,
                    label =
                      fullLabel.length > 12
                        ? fullLabel.slice(0, 10) + "…"
                        : fullLabel,
                    width = Math.max(51, label.length * 10 + 14) * markerUnit;
                  return (
                    <g
                      key={candidate.id}
                      role="button"
                      tabIndex={0}
                      aria-label={`${candidate.name} 후보지 선택`}
                      aria-pressed={active}
                      data-candidate-id={candidate.id}
                      className={`unified-candidate ${active ? "selected" : ""}`}
                      transform={`translate(${x},${y})`}
                      onClick={() => {
                        if (!wasDragged.current) onSelect?.(candidate.id);
                      }}
                      onKeyDown={(e) => {
                        if (["Enter", " "].includes(e.key)) {
                          e.preventDefault();
                          onSelect?.(candidate.id);
                        }
                      }}
                    >
                      {active && (
                        <circle
                          r={23 * markerUnit}
                          fill="#dbb160"
                          fillOpacity=".18"
                          stroke="#e1bf79"
                          strokeWidth={markerUnit}
                        />
                      )}
                      <circle
                        r={(active ? 16 : 13.5) * markerUnit}
                        fill={active ? "#d4a448" : "#f4f9ed"}
                        stroke={active ? "#fff3ce" : "#489b7d"}
                        strokeWidth={2 * markerUnit}
                      />
                      <text
                        y={4 * markerUnit}
                        fontSize={13 * markerUnit}
                        textAnchor="middle"
                        fill={active ? "#fff" : "#19543e"}
                        fontWeight="700"
                      >
                        {candidate.rank ?? i + 1}
                      </text>
                      <rect
                        x={-width / 2}
                        y={20 * markerUnit}
                        width={width}
                        height={21 * markerUnit}
                        rx={3 * markerUnit}
                        fill={active ? "#ba9340" : "#153d3e"}
                        fillOpacity={active ? 0.98 : 0.95}
                      />
                      <text
                        x="0"
                        y={34 * markerUnit}
                        textAnchor="middle"
                        fontSize={10.5 * markerUnit}
                        fill="#f0f7ed"
                        fontWeight={active ? "650" : "500"}
                      >
                        {label}
                      </text>
                      <title>
                        {candidate.name} ·{" "}
                        {metricOf(candidate, canonicalMode) == null
                          ? "점수 입력 대기"
                          : metricOf(candidate, canonicalMode).toFixed(3)}
                      </title>
                    </g>
                  );
                })}
              </g>
            )}
          </g>
        </svg>
        <div className="unified-map-source">
          <i />
          {units.length || district.length ? "행정경계" : "후보 좌표"} <span />
          좌표 기반 공간 분석
        </div>
        <div className="unified-map-north">
          <span>N</span>
          <svg viewBox="0 0 18 30" width="16" height="27">
            <path d="M9 2L17 26L9 21L1 26Z" fill="#e0eee5" />
            <path d="M9 2V21L17 26Z" fill="#8aaca0" />
          </svg>
        </div>
        <button
          className="unified-map-layer-trigger"
          aria-label="지도 레이어 제어"
          aria-expanded={layerOpen}
          onClick={() => setLayerOpen((v) => !v)}
        >
          <Layers3 size={15} />
          <span>레이어</span>
          <b>
            {
              layerOptions.filter(
                ([id, , available]) => available && layers[id],
              ).length
            }
          </b>
        </button>
        {layerOpen && (
          <div className="unified-map-layers">
            <div>
              <Layers3 size={15} />
              <b>레이어 제어</b>
              <button
                aria-label="지도 레이어 닫기"
                onClick={() => setLayerOpen(false)}
              >
                <X size={13} />
              </button>
            </div>
            {layerOptions.map(([id, label, available]) => (
              <label className={available ? "" : "unavailable"} key={id}>
                <input
                  type="checkbox"
                  aria-label={label}
                  checked={available && layers[id]}
                  disabled={!available}
                  onChange={() => setLayers((v) => ({ ...v, [id]: !v[id] }))}
                />
                <span className="unified-layer-check">
                  {available && layers[id] && <Check size={10} />}
                </span>
                <span>{label}</span>
                {!available && <small>연결 대기</small>}
              </label>
            ))}
          </div>
        )}
        <div className="unified-map-controls">
          <button
            aria-label={full ? "지도 전체화면 닫기" : "지도 전체화면"}
            onClick={() => setFull((v) => !v)}
          >
            {full ? <X size={16} /> : <Expand size={16} />}
          </button>
          <button
            aria-label="지도 확대"
            onClick={() => setZoom((z) => Math.min(12, z * 1.4))}
          >
            <Plus size={18} />
          </button>
          <button
            aria-label="지도 축소"
            onClick={() => setZoom((z) => Math.max(1, z / 1.4))}
          >
            <Minus size={18} />
          </button>
          <button aria-label="지도 전체 범위" onClick={reset}>
            <Crosshair size={16} />
          </button>
          <button
            aria-label="후보지역 범위 확대"
            disabled={!candidates.length}
            onClick={() => fit(candidates.map(coordinate))}
          >
            <LocateFixed size={16} />
          </button>
        </div>
        <div className="unified-map-legend">
          <b>
            {valueMode
              ? scoreName
              : routeView
                ? "차량 위치기록"
                : "공간 분석 단위"}
          </b>
          {valueMode ? (
            <>
              <div className="unified-score-ramp" />
              <div className="unified-legend-ends">
                <span>0.0</span>
                <span>0.5</span>
                <span>1.0</span>
              </div>
              <small>행정동 색상 · 포함 후보 점수 평균</small>
            </>
          ) : (
            <>
              <p>
                {routeView
                  ? `${positions.length}개 위치기록 · ${gpsRoutes.length}개 차량·일자`
                  : `${units.length}개 행정동 · ${candidates.length}개 후보지역`}
              </p>
              <small>
                {routeView
                  ? "기록 좌표를 시각순으로 연결"
                  : "제공된 공간 형상으로 표시"}
              </small>
            </>
          )}
        </div>
        <div className="unified-map-scale">
          <span>{scaleM >= 1000 ? `${scaleM / 1000} km` : `${scaleM} m`}</span>
          <div style={{ width: scaleM * groundPxPerM }} />
        </div>
        {hover && (
          <div className="unified-map-tooltip">
            <b>{hover.vehicleId}</b>
            <span>
              {new Date(hover.timestamp).toLocaleString("ko-KR", {
                timeZone: dataset.meta?.period?.timezone || "Asia/Seoul",
                hour12: false,
              })}
            </span>
            <span>
              {hover.longitude.toFixed(5)}, {hover.latitude.toFixed(5)}
            </span>
          </div>
        )}
        {routeView && !positions.length && !sourceRoutes.length && (
          <div className="unified-map-empty">
            선택 조건에 표시할 차량 위치기록이 없습니다.
          </div>
        )}
        {valueMode && !scoreRange.length && (
          <div className="unified-map-empty">
            점수가 연결되면 위치가치 분포를 표시합니다.
          </div>
        )}
      </div>
      <div className="unified-map-caption">
        <span>표시 좌표계 EPSG:3857 · 위도 보정 축척</span>
        <div>
          <button onClick={() => fit(candidates.map(coordinate))}>
            후보 범위
          </button>
          <i />
          <button onClick={reset}>전체 범위</button>
        </div>
      </div>
    </div>
  );
}
