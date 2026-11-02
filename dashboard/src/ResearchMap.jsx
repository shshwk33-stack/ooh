import React, { useEffect, useMemo, useRef, useState } from "react";
import { Check, Crosshair, Expand, Layers3, LocateFixed, Minus, Plus, X } from "lucide-react";
import "./ResearchMap.css";

const WIDTH = 1000, HEIGHT = 660, PAD = 62;
const VEHICLE_COLORS = ["#efb851", "#58cbbb", "#a8a4ea", "#ec9e8e"];
const INIT_LAYERS = { district: true, dongs: true, labels: true, routes: true, points: true };
const LAYERS = [
  ["district", "마포구 외곽", "PUBLIC"],
  ["dongs", "행정동 경계", "PUBLIC"],
  ["labels", "행정동 이름", null],
  ["routes", "합성 운행경로", "SYNTHETIC"],
  ["points", "합성 GPS 관측점", "SYNTHETIC"],
];

// The geometry is projected by the Python pipeline. No decorative roads or
// interpolated values are manufactured in this component.
function shapesFrom(input) {
  const list = input?.features || input || [];
  return list.map((entry) => {
    const properties = entry.properties || entry;
    const geometry = entry.geometry;
    let polygons = entry.polygons;
    if (!polygons && geometry) polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    if (!polygons && entry.rings) {
      const rings = entry.rings;
      polygons = typeof rings?.[0]?.[0]?.[0] === "number" ? [rings] : rings;
    }
    return { ...entry, code: String(properties.code), name: properties.name,
      polygons: polygons || [], labelPoint: entry.label || entry.labelPoint || entry.label_point || entry.center };
  });
}
function allPoints(shapes) { return shapes.flatMap((s) => s.polygons.flatMap((p) => p.flat())); }
function bounds(points) {
  return [Math.min(...points.map((p) => p[0])), Math.min(...points.map((p) => p[1])),
    Math.max(...points.map((p) => p[0])), Math.max(...points.map((p) => p[1]))];
}
function averageCenter(shape) {
  if (shape.labelPoint) return shape.labelPoint;
  const ring = shape.polygons[0]?.[0] || [];
  let area = 0, cx = 0, cy = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const cross = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
    area += cross; cx += (ring[j][0] + ring[i][0]) * cross; cy += (ring[j][1] + ring[i][1]) * cross;
  }
  if (area) return [cx / (3 * area), cy / (3 * area)];
  const b = bounds(ring); return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
}
const dayOf = (p) => p.localDate || p.day || p.timestamp?.slice(0, 10);
const vehicleOf = (p) => p.vehicleId || p.vehicle_id;

export default function ResearchMap({ data, selectedCode, onSelect, filters = {}, positions: suppliedPositions, summary }) {
  const svg = useRef(null), stageRef = useRef(null), drag = useRef(null), wasDragged = useRef(false);
  const [zoom, setZoom] = useState(1), [pan, setPan] = useState({ x: 0, y: 0 });
  const [layers, setLayers] = useState(INIT_LAYERS), [layerOpen, setLayerOpen] = useState(false);
  const [full, setFull] = useState(false), [hover, setHover] = useState(null);
  const [screenScale, setScreenScale] = useState(1);
  const projected = data.projected || data;
  const district = useMemo(() => shapesFrom(projected.district || projected.districts), [projected]);
  const dongs = useMemo(() => shapesFrom(projected.dongs), [projected]);
  const allPositions = data.gps?.positions || data.positions || [];
  const filtered = useMemo(() => suppliedPositions || summary?.positions || allPositions.filter((p) =>
    (!filters.vehicle || filters.vehicle === "all" || vehicleOf(p) === filters.vehicle) &&
    (!filters.day || filters.day === "all" || dayOf(p) === filters.day) &&
    (!filters.time || filters.time === "all" || (filters.time === "morning" ? p.hour < 12 : p.hour >= 12))),
  [suppliedPositions, summary?.positions, allPositions, filters.vehicle, filters.day, filters.time]);
  const metricBounds = useMemo(() => bounds(allPoints([...district, ...dongs])), [district, dongs]);
  const [minX, minY, maxX, maxY] = metricBounds;
  const pxPerM = Math.min((WIDTH - PAD * 2) / (maxX - minX), (HEIGHT - PAD * 2) / (maxY - minY));
  const mapWidth = (maxX - minX) * pxPerM, mapHeight = (maxY - minY) * pxPerM;
  const originX = (WIDTH - mapWidth) / 2, originY = (HEIGHT - mapHeight) / 2;
  const project = ([x, y]) => [originX + (x - minX) * pxPerM, originY + (maxY - y) * pxPerM];
  const pathOf = (shape) => shape.polygons.map((polygon) => polygon.map((ring) =>
    ring.map((point, i) => `${i ? "L" : "M"}${project(point).map((v) => v.toFixed(2)).join(",")}`).join("") + "Z").join("")).join("");
  const routes = useMemo(() => {
    const grouped = new Map();
    for (const p of filtered) {
      const key = `${vehicleOf(p)}|${dayOf(p)}`;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(p);
    }
    return [...grouped].map(([id, points]) => ({ id, vehicle: vehicleOf(points[0]), points: [...points].sort((a, b) => a.timestamp.localeCompare(b.timestamp)) }));
  }, [filtered]);
  const vehicles = [...new Set(allPositions.map(vehicleOf))].sort();
  const color = (vehicle) => VEHICLE_COLORS[Math.max(0, vehicles.indexOf(vehicle)) % VEHICLE_COLORS.length];
  const selected = dongs.find((d) => d.code === selectedCode);
  const metricStep = zoom > 3 ? 250 : zoom > 1.5 ? 500 : 1000;
  const gridX = [], gridY = [];
  for (let x = Math.ceil(minX / metricStep) * metricStep; x <= maxX; x += metricStep) gridX.push(x);
  for (let y = Math.ceil(minY / metricStep) * metricStep; y <= maxY; y += metricStep) gridY.push(y);
  const scaleM = [2000, 1000, 500, 250, 100, 50].find((m) => m * pxPerM * zoom * screenScale <= 155) || 50;
  const scaleWidth = scaleM * pxPerM * zoom * screenScale;

  useEffect(() => {
    const element = svg.current;
    const update = () => {
      const rect = element.getBoundingClientRect();
      setScreenScale(Math.min(rect.width / WIDTH, rect.height / HEIGHT));
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const element = stageRef.current;
    const wheel = (event) => {
      event.preventDefault();
      setZoom((z) => Math.max(1, Math.min(12, z * (event.deltaY < 0 ? 1.15 : 1 / 1.15))));
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);

  useEffect(() => {
    if (!full) return;
    const close = (e) => { if (e.key === "Escape") setFull(false); };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [full]);

  const reset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };
  const zoomTo = (points) => {
    if (!points.length) return;
    setLayerOpen(false);
    const b = bounds(points), centre = project([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]);
    const next = Math.max(1, Math.min(12, Math.min((WIDTH - 200) / Math.max(1, (b[2] - b[0]) * pxPerM), (HEIGHT - 160) / Math.max(1, (b[3] - b[1]) * pxPerM))));
    setZoom(next); setPan({ x: (WIDTH / 2 - centre[0]) * next, y: (HEIGHT / 2 - centre[1]) * next });
  };
  const eventPoint = (e) => {
    const point = svg.current.createSVGPoint();
    point.x = e.clientX; point.y = e.clientY;
    const transformed = point.matrixTransform(svg.current.getScreenCTM().inverse());
    return [transformed.x, transformed.y];
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
    if (!wasDragged.current && Math.hypot(x - drag.current.x, y - drag.current.y) < 4) return;
    wasDragged.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    setPan({ x: drag.current.pan.x + x - drag.current.x, y: drag.current.pan.y + y - drag.current.y });
  };
  const toggle = (id) => setLayers((current) => ({ ...current, [id]: !current[id] }));
  const changeZoom = (factor) => setZoom((z) => Math.max(1, Math.min(12, z * factor)));

  return <div className={`research-map ${full ? "research-map-expanded" : ""}`} data-testid="research-map">
    <div className="research-map-toolbar">
      <div className="research-map-tabs"><button className="active" onClick={reset}>행정경계</button><button onClick={() => zoomTo(filtered.map((p) => [p.x, p.y]))}>운행 위치 확대</button></div>
      <span className="research-map-year">KOSTAT · 2013</span>
    </div>
    <div className="research-map-stage" ref={stageRef}>
      <svg ref={svg} className="research-map-svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="group" aria-label="실제 마포구 16개 행정동 경계와 합성 GPS 좌표 지도" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
        <defs><radialGradient id="research-map-background"><stop offset="0" stopColor="#1a3d46"/><stop offset="1" stopColor="#102c35"/></radialGradient></defs>
        <rect width={WIDTH} height={HEIGHT} fill="url(#research-map-background)" />
        <g transform={`translate(${WIDTH / 2 + pan.x},${HEIGHT / 2 + pan.y}) scale(${zoom}) translate(${-WIDTH / 2},${-HEIGHT / 2})`} data-testid="research-map-transform">
          <g className="research-map-grid" aria-hidden="true">
            {gridX.map((x) => <line key={x} x1={project([x, minY])[0]} x2={project([x, minY])[0]} y1={originY - 20} y2={originY + mapHeight + 20} />)}
            {gridY.map((y) => <line key={y} y1={project([minX, y])[1]} y2={project([minX, y])[1]} x1={originX - 20} x2={originX + mapWidth + 20} />)}
          </g>
          {layers.dongs && <g data-layer="research-dongs">{dongs.map((dong) => <path key={dong.code} d={pathOf(dong)} fillRule="evenodd" className={`research-dong ${dong.code === selectedCode ? "selected" : ""}`} role="button" tabIndex={0} aria-label={`${dong.name} 행정동 선택`} aria-pressed={dong.code === selectedCode} data-dong={dong.code} onClick={() => { if (!wasDragged.current) onSelect?.(dong.code); }} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect?.(dong.code); } }}><title>{dong.name} · {dong.code} · 2013 경계</title></path>)}</g>}
          {layers.district && <g data-layer="research-district" className="research-district">{district.map((d) => <path key={d.code} d={pathOf(d)} fill="none" />)}</g>}
          {layers.routes && <g data-layer="research-routes">{routes.map((route) => <polyline key={route.id} fill="none" stroke={color(route.vehicle)} strokeWidth={2.8 / Math.sqrt(zoom)} points={route.points.map((p) => project([p.x, p.y]).join(",")).join(" ")} opacity=".95" strokeLinecap="round" strokeLinejoin="round"><title>{route.id} · 합성 운행경로</title></polyline>)}</g>}
          {layers.points && <g data-layer="research-points">{filtered.map((p, i) => {
            const xy = project([p.x, p.y]);
            return <circle key={`${vehicleOf(p)}-${p.timestamp}-${i}`} cx={xy[0]} cy={xy[1]} r={2.4 / Math.sqrt(zoom)} fill={color(vehicleOf(p))} stroke="#f3fff8" strokeWidth={.6 / zoom} tabIndex={0} role="img" aria-label={`${vehicleOf(p)} ${p.timestamp} 합성 GPS점`} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(p)} onBlur={() => setHover(null)}><title>{vehicleOf(p)} · {p.timestamp} · SYNTHETIC</title></circle>;
          })}</g>}
          {layers.labels && <g className="research-dong-labels" data-layer="research-labels" pointerEvents="none">{dongs.map((d) => {
            const [x, y] = project(averageCenter(d));
            return <text key={d.code} x={x} y={y} fontSize={d.code === selectedCode ? 16 / Math.sqrt(zoom) : 14 / Math.sqrt(zoom)} className={d.code === selectedCode ? "selected" : ""}>{d.name}</text>;
          })}</g>}
        </g>
      </svg>
      <div className="research-map-source"><span className="public-mark"/>실제 행정경계 <i/> <span className="synthetic-mark"/>합성 운행</div>
      <div className="research-map-north" aria-label="북쪽"><span>N</span><svg width="18" height="30" viewBox="0 0 18 30"><path d="M9 2L17 26L9 21L1 26Z" fill="#e5f2ec"/><path d="M9 2V21L17 26Z" fill="#7f9b95"/></svg></div>
      <button className="research-layer-trigger" aria-label="GIS 레이어 제어" aria-expanded={layerOpen} onClick={() => setLayerOpen(!layerOpen)}><Layers3 size={15}/><span>레이어</span><small>{Object.values(layers).filter(Boolean).length}</small></button>
      {layerOpen && <div className="research-map-layers"><div><Layers3 size={16}/><b>레이어 제어</b><button aria-label="GIS 레이어 패널 닫기" onClick={() => setLayerOpen(false)}><X size={13}/></button></div>{LAYERS.map(([id, name, kind]) => <label key={id}><input type="checkbox" checked={layers[id]} onChange={() => toggle(id)} aria-label={name}/><span className="research-layer-check">{layers[id] && <Check size={10}/>}</span><span>{name}</span>{kind && <small className={kind === "SYNTHETIC" ? "synthetic" : ""}>{kind === "SYNTHETIC" ? "합성" : "공개"}</small>}</label>)}</div>}
      <div className="research-map-controls"><button aria-label={full ? "실제 지도 전체화면 닫기" : "실제 지도 전체화면"} onClick={() => setFull(!full)}>{full ? <X size={17}/> : <Expand size={17}/>}</button><button aria-label="실제 지도 확대" onClick={() => changeZoom(1.4)}><Plus size={18}/></button><button aria-label="실제 지도 축소" onClick={() => changeZoom(1 / 1.4)}><Minus size={18}/></button><button aria-label="실제 지도 중심 복원" onClick={reset}><Crosshair size={17}/></button>{selected && <button aria-label="선택 행정동 확대" onClick={() => zoomTo(allPoints([selected]))}><LocateFixed size={17}/></button>}</div>
      <div className="research-map-legend"><b>마포구 · 실제 공간자료</b><span><i/>행정동 16개 <em>EPSG:5179</em></span><span><i className="route"/>표시 GPS {filtered.length}점 <em>SYNTHETIC</em></span></div>
      <div className="research-map-scale"><span>{scaleM >= 1000 ? `${scaleM / 1000} km` : `${scaleM} m`}</span><div style={{ width: `${scaleWidth}px` }}/></div>
      {hover && <div className="research-point-tooltip"><small>SYNTHETIC GPS</small><b>{vehicleOf(hover)}</b><span>{new Date(hover.timestamp).toLocaleString("ko-KR", { timeZone: "Asia/Seoul", hour12: false })}</span><span>{Number(hover.longitude).toFixed(5)}, {Number(hover.latitude).toFixed(5)}</span></div>}
      {!filtered.length && <div className="research-map-empty">선택 조건에 해당하는 합성 GPS가 없습니다.</div>}
    </div>
    <div className="research-map-caption"><span>2013 공개 경계 · 좌표 기반 표시</span><span>운행경로는 합성 시나리오이며 실제 도로망이 아닙니다.</span></div>
  </div>;
}
