import React, { useMemo, useRef, useState, useEffect } from "react";
import {
  Check,
  Crosshair,
  Layers3,
  Maximize2,
  Minus,
  Navigation,
  Plus,
  X,
} from "lucide-react";
import { DEMO_CANDIDATES, LAYERS } from "./demo";

const MODES = [
  { id: "value", label: "위치가치 히트맵", layer: "value" },
  { id: "vehicle", label: "차량 이동경로", layer: "vehicle" },
  { id: "population", label: "인구 통행구간", layer: "population" },
  { id: "milk", label: "밀크런 경로", layer: "milk" },
  { id: "poi", label: "POI/상권", layer: "poi" },
];
const schematicPositions = {
  "TA-001": { x: 470, y: 340 },
  "TA-002": { x: 845, y: 575 },
  "TA-003": { x: 225, y: 250 },
  "TA-004": { x: 465, y: 515 },
  "TA-005": { x: 285, y: 450 },
  "TA-006": { x: 650, y: 435 },
  "TA-007": { x: 735, y: 635 },
  "TA-008": { x: 540, y: 190 },
};

const outline = [
  [90, 175],
  [200, 110],
  [302, 58],
  [381, 89],
  [465, 82],
  [525, 145],
  [567, 235],
  [663, 245],
  [719, 304],
  [810, 308],
  [846, 380],
  [899, 421],
  [918, 504],
  [959, 568],
  [899, 630],
  [821, 661],
  [705, 640],
  [636, 662],
  [528, 620],
  [450, 616],
  [378, 577],
  [275, 569],
  [202, 521],
  [174, 451],
  [122, 397],
  [103, 302],
  [69, 248],
];
const regionPath = "M" + outline.map((p) => p.join(",")).join("L") + "Z";
function contains(x, y) {
  let yes = false;
  for (let i = 0, j = outline.length - 1; i < outline.length; j = i++) {
    const [a, b] = outline[i],
      [c, d] = outline[j];
    if (b > y !== d > y && x < ((c - a) * (y - b)) / (d - b) + a) yes = !yes;
  }
  return yes;
}
function buildStreets() {
  const paths = ["", "", "", ""],
    blocks = [];
  const node = (i, j) => [
    i * 18 + Math.sin(j * 0.15) * 26 + Math.sin(i * 0.38 + j * 0.12) * 9,
    j * 16 + Math.sin(i * 0.12) * 24 + Math.cos(j * 0.31 + i * 0.1) * 6,
  ];
  for (let i = -6; i < 67; i++)
    for (let j = -7; j < 59; j++) {
      const p = node(i, j);
      for (const [di, dj] of [
        [1, 0],
        [0, 1],
      ]) {
        const q = node(i + di, j + dj),
          within = contains(...p) && contains(...q);
        // A connected, warped schematic street mesh; no geospatial source is used.
        if (within && (i * 17 + j * 7 + di) % 29 === 0) continue;
        const kind = !within
          ? 0
          : (di ? j % 11 === 0 : i % 13 === 0)
            ? 3
            : (i + j) % 4 === 0
              ? 2
              : 1;
        paths[kind] +=
          `M${p[0].toFixed(1)},${p[1].toFixed(1)}L${q[0].toFixed(1)},${q[1].toFixed(1)}`;
      }
      if ((i + j) % 3 === 0)
        blocks.push({
          x: p[0] + 3,
          y: p[1] + 3,
          w: 7 + ((i + 90) % 7),
          h: 4 + ((j + 90) % 6),
        });
    }
  return { paths, blocks };
}
const arterial = [
  "M-40 160C125 194 168 230 252 278S375 303 470 340 690 426 835 545 970 609 1050 640",
  "M192 15C223 129 265 200 252 278S252 382 280 435 293 516 267 569 235 681 216 770",
  "M463-30C506 94 521 153 508 205S454 284 470 340 440 419 456 490 523 584 533 757",
  "M655 60C584 164 574 237 604 309S635 382 649 425 698 544 767 608 819 700 839 763",
  "M-30 448C99 413 190 406 280 435S386 490 456 490 565 458 649 425 799 389 1055 453",
  "M-30 301C155 323 280 384 382 371S439 322 470 340 628 312 721 310 930 323 1040 346",
  "M121 529C177 484 233 430 280 435S392 469 456 490 588 544 619 536 760 524 835 545 963 546 1040 534",
];
const route =
  "M225 250C304 273 387 310 470 340L540 190 470 340C403 365 342 415 285 450L465 515 620 542 650 435C714 467 790 529 845 575L735 635";
const milk =
  "M225 250L238 355 285 450 465 515 620 542 845 575 782 398 660 308 470 340 337 308Z";
const populationBands = [
  "M204 312C316 238 379 318 470 340S645 391 735 459",
  "M256 449C348 405 431 480 456 490S659 511 816 555",
  "M506 190C489 261 483 311 470 340S456 424 456 490",
];
const pois = [
  [306, 260, "상업"],
  [352, 295, "상업"],
  [424, 286, "문화"],
  [508, 293, "상업"],
  [547, 341, "문화"],
  [392, 378, "문화"],
  [337, 426, "상업"],
  [494, 437, "상업"],
  [585, 430, "업무"],
  [692, 477, "업무"],
  [745, 527, "업무"],
  [805, 491, "업무"],
  [537, 208, "문화"],
  [232, 349, "상업"],
  [389, 531, "문화"],
];
const heatColors = [
  "#3157b9",
  "#6042b8",
  "#964da8",
  "#cfb53a",
  "#f2ae31",
  "#f0523d",
];

export default function DesignMap({
  selected,
  onSelect,
  layers,
  setLayers,
  candidates = DEMO_CANDIDATES,
  mode,
  onModeChange,
}) {
  const [localMode, setLocalMode] = useState("value"),
    [zoom, setZoom] = useState(1),
    [pan, setPan] = useState({ x: 0, y: 0 }),
    [full, setFull] = useState(false),
    [layerOpen, setLayerOpen] = useState(true);
  const currentMode = mode ?? localMode;
  const drag = useRef(null);
  const streets = useMemo(buildStreets, []);
  const mapCandidates = useMemo(
    () =>
      candidates.map((candidate) => ({
        ...candidate,
        ...schematicPositions[candidate.id],
      })),
    [candidates],
  );
  const chooseMode = (next) => {
    setLocalMode(next);
    if (onModeChange) onModeChange(next);
    const target = MODES.find((m) => m.id === next)?.layer;
    if (target && !layers[target]) setLayers({ ...layers, [target]: true });
  };
  useEffect(() => {
    if (!full) return;
    const key = (e) => {
      if (e.key === "Escape") setFull(false);
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [full]);
  const cells = useMemo(() => {
    const paths = heatColors.map(() => "");
    for (let x = 108; x < 955; x += 18)
      for (let y = 93; y < 660; y += 18) {
        if (!contains(x, y)) continue;
        let sum = 0,
          total = 0,
          nearest = Infinity;
        mapCandidates.forEach((c) => {
          const d = Math.hypot(c.x - x, c.y - y);
          nearest = Math.min(nearest, d);
          const w = Math.exp((-d * d) / 10500);
          sum += Number(c.value) * w;
          total += w;
        });
        if (nearest > 112 || !total) continue;
        const displayIntensity =
          (sum / total) * Math.exp((-nearest * nearest) / 10500);
        const index = Math.max(
          0,
          Math.min(5, Math.floor(displayIntensity * 7)),
        );
        paths[index] += `M${x},${y}h16v16h-16Z`;
      }
    return paths;
  }, [mapCandidates]);
  const emphasis = (layer) =>
    currentMode === layer
      ? 1
      : currentMode === "value"
        ? layer === "population"
          ? 0.5
          : layer === "vehicle"
            ? 0.85
            : 0.65
        : layer === "value"
          ? 0.2
          : 0.28;
  const mapLayers = LAYERS.some((l) => l.id === "poi")
    ? LAYERS
    : [
        ...LAYERS,
        { id: "poi", label: "POI/상권", type: "dot", color: "#cab37c" },
      ];
  const layerEnabled = Boolean(
    layers[MODES.find((m) => m.id === currentMode)?.layer],
  );
  const legendLabel =
    currentMode === "value"
      ? "상대 위치가치"
      : currentMode === "population"
        ? "인구 통행 강도"
        : currentMode === "vehicle"
          ? "차량 이동경로"
          : currentMode === "milk"
            ? "밀크런 순환경로"
            : "POI · 상권 유형";
  return (
    <div className={"map-workspace " + (full ? "map-expanded" : "")}>
      <div className="map-mode-tabs" role="tablist" aria-label="지도 분석 모드">
        {MODES.map((m) => (
          <button
            key={m.id}
            role="tab"
            aria-selected={currentMode === m.id}
            tabIndex={currentMode === m.id ? 0 : -1}
            className={currentMode === m.id ? "active" : ""}
            onClick={() => chooseMode(m.id)}
            onKeyDown={(e) => {
              const index = MODES.findIndex((item) => item.id === currentMode);
              let next = index;
              if (e.key === "ArrowRight") next = (index + 1) % MODES.length;
              else if (e.key === "ArrowLeft")
                next = (index + MODES.length - 1) % MODES.length;
              else if (e.key === "Home") next = 0;
              else if (e.key === "End") next = MODES.length - 1;
              else return;
              e.preventDefault();
              chooseMode(MODES[next].id);
              e.currentTarget.parentElement
                .querySelectorAll('[role="tab"]')
                [next].focus();
            }}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div className={"design-map mode-" + currentMode}>
        <svg
          className="map-canvas"
          viewBox="0 0 1000 720"
          preserveAspectRatio="xMidYMid meet"
          aria-label="DEMO / Schematic Map. 디자인용 개념도이며 실제 도로·실측 데이터가 아닙니다."
          onPointerDown={(e) => {
            if (e.target.closest("[data-candidate]")) return;
            const point = new DOMPoint(e.clientX, e.clientY).matrixTransform(
              e.currentTarget.getScreenCTM().inverse(),
            );
            drag.current = { x: point.x, y: point.y, pan };
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            if (drag.current) {
              const point = new DOMPoint(e.clientX, e.clientY).matrixTransform(
                e.currentTarget.getScreenCTM().inverse(),
              );
              setPan({
                x: drag.current.pan.x + point.x - drag.current.x,
                y: drag.current.pan.y + point.y - drag.current.y,
              });
            }
          }}
          onPointerUp={() => (drag.current = null)}
          onPointerCancel={() => (drag.current = null)}
        >
          <defs>
            <clipPath id="study-area">
              <path d={regionPath} />
            </clipPath>
            <pattern
              id="map-texture"
              width="140"
              height="120"
              patternUnits="userSpaceOnUse"
            >
              <rect width="140" height="120" fill="#223a44" />
              <path
                d="M-20 95L150 22M30 130L67-10M-10 25L150 116"
                stroke="#2c4650"
                strokeWidth=".65"
              />
              <path
                d="M0 45L120 140M100 0L160 80"
                stroke="#1f3540"
                strokeWidth="14"
              />
            </pattern>
            <radialGradient id="score-hotspot">
              <stop offset="0" stopColor="#fa3f36" stopOpacity=".96" />
              <stop offset=".19" stopColor="#fc6731" stopOpacity=".94" />
              <stop offset=".38" stopColor="#ffc42d" stopOpacity=".82" />
              <stop offset=".55" stopColor="#e6ce46" stopOpacity=".55" />
              <stop offset=".76" stopColor="#8b42c6" stopOpacity=".45" />
              <stop offset="1" stopColor="#395ac0" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="selected-halo">
              <stop offset="0" stopColor="#fae8a5" stopOpacity=".3" />
              <stop offset="1" stopColor="#fae8a5" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect width="1000" height="720" fill="url(#map-texture)" />
          <g
            transform={`translate(${500 + pan.x} ${360 + pan.y}) scale(${zoom}) translate(-500 -360)`}
          >
            <path
              d="M-100 0H258L192 109 71 160-100 142Z M715-40H1100V150L958 122 870 52Z"
              fill="#2b443d"
              opacity=".8"
            />
            <path
              d="M135 143L194 125 218 148 194 182 166 181Z M598 524L622 540 608 570 569 553Z M696 244L754 256 763 279 707 279Z"
              fill="#3b5545"
              opacity=".55"
            />
            <g fill="#2c444d" opacity=".8">
              {streets.blocks.map((b, i) => (
                <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} rx="1" />
              ))}
            </g>
            <path
              d="M-80 490C95 505 94 603 271 650S568 669 704 766 976 788 1120 754"
              stroke="#173340"
              strokeWidth="105"
              fill="none"
            />
            <path
              d="M-80 490C95 505 94 603 271 650S568 669 704 766 976 788 1120 754"
              stroke="#49616a"
              strokeWidth="1"
              fill="none"
            />
            <path
              d="M120 594L55 747 M345 675L298 790 M667 733L650 835"
              stroke="#607671"
              strokeWidth="4"
              fill="none"
              opacity=".45"
            />
            <g
              className="base-labels"
              textAnchor="middle"
              fill="#82978e"
              fontSize="15"
            >
              <text x="716" y="173">
                주거 권역
              </text>
              <text x="185" y="134">
                생활 상권
              </text>
              <text x="890" y="332">
                업무 권역
              </text>
              <text
                x="192"
                y="624"
                fill="#658695"
                fontSize="17"
                letterSpacing="8"
                transform="rotate(16 192 624)"
              >
                하천 · 개념도
              </text>
              <text x="411" y="154">
                문화 상권
              </text>
              <text x="222" y="362">
                생활 권역
              </text>
              <text x="598" y="573">
                업무·주거 권역
              </text>
            </g>
            <path d={regionPath} fill="#344f9f" fillOpacity=".28" />
            {layers.value && (
              <g
                data-layer="value"
                clipPath="url(#study-area)"
                opacity={emphasis("value")}
              >
                {mapCandidates.map((candidate) => (
                  <circle
                    key={candidate.id}
                    className="hotspot-core"
                    cx={candidate.x}
                    cy={candidate.y}
                    r={76 + Number(candidate.value) * 65}
                    fill="url(#score-hotspot)"
                    opacity={0.66 + Number(candidate.value) * 0.3}
                  />
                ))}
                {cells.map((d, i) => (
                  <path
                    key={i}
                    d={d}
                    fill={heatColors[i]}
                    fillOpacity={i < 2 ? 0.19 : 0.25}
                    stroke={heatColors[i]}
                    strokeOpacity=".06"
                    strokeWidth=".5"
                  />
                ))}
              </g>
            )}
            {layers.population && (
              <g
                data-layer="population"
                clipPath="url(#study-area)"
                opacity={emphasis("population")}
                fill="none"
                strokeLinecap="round"
              >
                {populationBands.map((d, i) => (
                  <g key={i}>
                    <path
                      d={d}
                      stroke="#8878b0"
                      strokeWidth={35 + i * 7}
                      opacity=".09"
                    />
                    <path
                      d={d}
                      stroke="#9181ba"
                      strokeWidth={11 + i * 4}
                      opacity=".22"
                    />
                    <path
                      d={d}
                      stroke="#b4a4d4"
                      strokeWidth="2"
                      opacity=".55"
                      strokeDasharray="2 7"
                    />
                  </g>
                ))}
              </g>
            )}
            <g fill="none" strokeLinecap="round" strokeLinejoin="round">
              <path
                d={streets.paths[0]}
                stroke="#4d6269"
                strokeWidth=".7"
                opacity=".3"
              />
              {layers.roads && (
                <g data-layer="roads">
                  <path
                    d={streets.paths[1]}
                    stroke="#96afa1"
                    strokeWidth=".7"
                    opacity=".58"
                  />
                  <path
                    d={streets.paths[2]}
                    stroke="#c2ce83"
                    strokeWidth=".85"
                    opacity=".66"
                  />
                  <path
                    d={streets.paths[3]}
                    stroke="#d4d872"
                    strokeWidth="1"
                    opacity=".8"
                  />
                  {arterial.map((d, i) => (
                    <g key={i}>
                      <path d={d} stroke="#203b41" strokeWidth="4.8" />
                      <path
                        d={d}
                        stroke="#e0dc70"
                        strokeWidth="1.35"
                        opacity=".85"
                      />
                    </g>
                  ))}
                </g>
              )}
              {layers.milk && (
                <g data-layer="milk" opacity={emphasis("milk")}>
                  <path
                    d={milk}
                    stroke="#efc56c"
                    strokeWidth="7"
                    opacity=".1"
                  />
                  <path
                    d={milk}
                    stroke="#e5b65d"
                    strokeWidth="2.5"
                    strokeDasharray="10 6"
                  />
                  {[
                    [238, 355],
                    [456, 490],
                    [835, 545],
                    [660, 308],
                  ].map(([x, y], i) => (
                    <rect
                      key={i}
                      x={x - 4}
                      y={y - 4}
                      width="8"
                      height="8"
                      fill="#f4d79b"
                      stroke="#786334"
                      strokeWidth="1.5"
                    />
                  ))}
                </g>
              )}
              {layers.vehicle && (
                <g data-layer="vehicle" opacity={emphasis("vehicle")}>
                  <path
                    d={route}
                    stroke="#9be5df"
                    strokeWidth="7"
                    opacity=".12"
                  />
                  <path d={route} stroke="#8fedf1" strokeWidth="3" />
                  {[
                    [337, 308],
                    [399, 385],
                    [619, 536],
                    [782, 398],
                  ].map(([x, y], i) => (
                    <g key={i} transform={`translate(${x} ${y})`}>
                      <circle r="6" fill="#c3eeea" />
                      <path d="M-2 3L0-4 4 3 0 1Z" fill="#2b6e65" />
                    </g>
                  ))}
                </g>
              )}
            </g>
            {layers.poi && (
              <g data-layer="poi" opacity={emphasis("poi")}>
                {pois.map(([x, y, type], i) => (
                  <g key={i} transform={`translate(${x} ${y})`}>
                    <circle
                      r="9"
                      fill="#263d3d"
                      stroke={
                        type === "문화"
                          ? "#a993c6"
                          : type === "업무"
                            ? "#8bb4ba"
                            : "#c9b582"
                      }
                      strokeWidth="1.2"
                    />
                    <rect
                      x="-2.5"
                      y="-2.5"
                      width="5"
                      height="5"
                      fill={
                        type === "문화"
                          ? "#a993c6"
                          : type === "업무"
                            ? "#8bb4ba"
                            : "#c9b582"
                      }
                    />
                    <title>{type} POI · DEMO</title>
                  </g>
                ))}
              </g>
            )}
            <path
              d={regionPath}
              stroke="#eef4ec"
              strokeWidth="1.7"
              fill="none"
              opacity=".95"
            />
            {layers.candidates &&
              mapCandidates.map((c) => {
                const active = selected === c.id;
                return (
                  <g
                    key={c.id}
                    data-candidate={c.id}
                    className={"candidate-pin " + (active ? "active" : "")}
                    role="button"
                    tabIndex="0"
                    aria-label={`${c.short} 후보지 선택`}
                    aria-pressed={active}
                    onClick={() => onSelect(c.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelect(c.id);
                      }
                    }}
                    transform={`translate(${c.x} ${c.y})`}
                  >
                    <title>{`${c.short} · DEMO 위치가치 ${c.value}`}</title>
                    {active && <circle r="70" fill="url(#selected-halo)" />}
                    <circle
                      r={active ? 31 : 22}
                      fill="#aac6aa"
                      opacity={active ? 0.12 : 0.035}
                    />
                    <circle
                      r={active ? 23 : 16}
                      fill={active ? "#e64c3c" : "#3aab6c"}
                      stroke={active ? "#ffffff" : "#f0fff1"}
                      strokeWidth={active ? 3.2 : 2.2}
                    />
                    <text
                      textAnchor="middle"
                      dy={active ? 6 : 5}
                      fontSize={active ? 19 : 15}
                      fontWeight="650"
                      fill="#ffffff"
                    >
                      {c.rank}
                    </text>
                    <rect
                      x={active ? -65 : -44}
                      y={active ? 31 : 23}
                      width={active ? 130 : 88}
                      height={active ? 29 : 24}
                      rx="3"
                      fill={active ? "#13283b" : "#183040"}
                      fillOpacity={active ? 0.98 : 0.94}
                      stroke={active ? "#ffbc9f" : "#45616a"}
                      strokeOpacity=".65"
                    />
                    <text
                      y={active ? 50 : 40}
                      textAnchor="middle"
                      fill={active ? "#ffffff" : "#dce9e7"}
                      fontSize={active ? 15 : 12}
                      fontWeight={active ? 650 : 450}
                    >
                      {c.short}
                    </text>
                  </g>
                );
              })}
          </g>
        </svg>
        <div className="map-demo-tag">
          <span /> DEMO / SCHEMATIC MAP
        </div>
        <div className="map-north">
          <Navigation size={18} />
          <span>N</span>
        </div>
        <button
          className="map-full-button"
          aria-label={full ? "지도 전체화면 닫기" : "지도 전체화면"}
          onClick={() => setFull(!full)}
        >
          {full ? <X size={15} /> : <Maximize2 size={14} />}
        </button>
        <div className={"layer-panel " + (!layerOpen ? "collapsed" : "")}>
          <button
            className="layer-panel-heading"
            onClick={() => setLayerOpen(!layerOpen)}
            aria-expanded={layerOpen}
          >
            <Layers3 size={13} />
            <b>레이어 제어</b>
            <span>{layerOpen ? "−" : "+"}</span>
          </button>
          {layerOpen && (
            <div className="layer-options">
              {mapLayers
                .filter((l) => l.id !== "poi" || currentMode === "poi")
                .map((l) => (
                  <label key={l.id}>
                    <input
                      type="checkbox"
                      checked={Boolean(layers[l.id])}
                      onChange={() =>
                        setLayers({ ...layers, [l.id]: !layers[l.id] })
                      }
                    />
                    <span
                      className={
                        "layer-checkbox " + (layers[l.id] ? "checked" : "")
                      }
                    >
                      {layers[l.id] && <Check size={10} />}
                    </span>
                    <span>{l.label}</span>
                    <i
                      className={"layer-symbol " + l.type}
                      style={{ "--layer-color": l.color }}
                    />
                  </label>
                ))}
            </div>
          )}
        </div>
        <div className="map-controls">
          <button
            aria-label="지도 확대"
            onClick={() => setZoom((z) => Math.min(2.4, z + 0.2))}
          >
            <Plus size={18} />
          </button>
          <button
            aria-label="지도 축소"
            onClick={() => setZoom((z) => Math.max(0.7, z - 0.2))}
          >
            <Minus size={18} />
          </button>
          <button
            aria-label="지도 중심 복원"
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
          >
            <Crosshair size={17} />
          </button>
        </div>
        <div className={"map-legend mode-legend-" + currentMode}>
          <b>
            {legendLabel}
            <span>DEMO</span>
          </b>
          {currentMode === "value" || currentMode === "population" ? (
            <>
              <div
                className={
                  "legend-ramp " +
                  (currentMode === "population" ? "population-ramp" : "")
                }
              />
              <div className="legend-ends">
                <span>낮음</span>
                <span>높음</span>
              </div>
            </>
          ) : currentMode === "poi" ? (
            <div className="poi-legend">
              <span>
                <i style={{ background: "#c9b582" }} />
                상업
              </span>
              <span>
                <i style={{ background: "#a993c6" }} />
                문화
              </span>
              <span>
                <i style={{ background: "#8bb4ba" }} />
                업무
              </span>
            </div>
          ) : (
            <div className="route-legend">
              <i
                className={
                  currentMode === "milk" ? "milk-line" : "vehicle-line"
                }
              />
              <span>
                {currentMode === "milk"
                  ? "순환 운행 시나리오"
                  : "차량 이동 시나리오"}
              </span>
            </div>
          )}
        </div>
        <div className="map-scale">
          <div>
            <span>0</span>
            <span>0.5</span>
            <span>1.0</span>
            <span>2.0 km</span>
          </div>
          <i />
          <small>거리 표시 UI 예시</small>
        </div>
        <div className="map-mode-status">
          {!layerEnabled ? "선택 레이어 꺼짐" : `${Math.round(zoom * 100)}%`}
        </div>
        <div className="map-disclaimer">
          직접 구성한 SVG 개념도 · 좌표·거리·통행량은 실측값이 아닙니다.
        </div>
      </div>
    </div>
  );
}
