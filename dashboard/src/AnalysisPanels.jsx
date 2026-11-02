import React, { useEffect, useMemo, useRef, useState } from "react";
import { Info } from "lucide-react";
import { DEMO_CANDIDATES } from "./demo";

export function DemoBadge({ className = "" }) {
  return (
    <span
      className={"demo-badge " + className}
      title="프런트엔드 시연 데이터 · 실제 연구모델 실행 결과가 아닙니다"
    >
      DEMO
    </span>
  );
}

export function PanelTitle({ children, info, tag = true }) {
  return (
    <div className="panel-title">
      <h2>{children}</h2>
      <div>
        {info && (
          <span className="info-tip" tabIndex="0" role="note" aria-label={info}>
            <Info size={14} />
            <span>{info}</span>
          </span>
        )}
        {tag && <DemoBadge />}
      </div>
    </div>
  );
}

function useSelectedRowScroll(selected, candidates) {
  const ref = useRef(null);
  useEffect(() => {
    const container = ref.current;
    if (!container || !selected) return;
    const row = Array.from(
      container.querySelectorAll("[data-candidate-id]"),
    ).find((node) => node.getAttribute("data-candidate-id") === selected);
    if (!row) return;
    const box = container.getBoundingClientRect(),
      item = row.getBoundingClientRect();
    const header =
      container.querySelector("thead")?.getBoundingClientRect().height || 0;
    if (item.top < box.top + header)
      container.scrollTop -= box.top + header - item.top + 4;
    else if (item.bottom > box.bottom)
      container.scrollTop += item.bottom - box.bottom + 4;
  }, [selected, candidates]);
  return ref;
}

export function ComparisonTable({
  candidates = DEMO_CANDIDATES,
  selected,
  onSelect,
}) {
  const topFive = candidates.slice(0, 5);
  const outside = candidates.find(
    (c) => c.id === selected && !topFive.some((item) => item.id === c.id),
  );
  const rows = outside ? [...topFive, outside] : topFive;
  const scrollRef = useSelectedRowScroll(selected, candidates);
  return (
    <section className="surface lower-panel comparison-panel">
      <PanelTitle info="Static(S)는 공간 점수만 사용하는 기준 모델입니다. Integrated(V)는 현재 Mobility·Spatial 가중치에 따른 DEMO 점수입니다.">
        모델별 후보지역 비교 <small>(Top-5)</small>
        {outside && (
          <small className="selected-outside-note">+ 선택 후보</small>
        )}
      </PanelTitle>
      <div className="table-wrap analysis-table-scroll" ref={scrollRef}>
        <table className="comparison-table">
          <thead>
            <tr>
              <th scope="col">순위</th>
              <th scope="col">후보지</th>
              <th scope="col" title="공간 점수 단독 기준: Static = Spatial">
                Static <small>(S)</small>
              </th>
              <th scope="col">
                Mobility <small>(M)</small>
              </th>
              <th scope="col">
                Integrated <small>(V)</small>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr
                key={c.id}
                className={selected === c.id ? "selected-row" : ""}
                onClick={() => onSelect?.(c.id)}
                data-candidate-id={c.id}
              >
                <td>{c.rank}</td>
                <td>
                  <button
                    aria-pressed={selected === c.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect?.(c.id);
                    }}
                  >
                    {c.short}
                  </button>
                </td>
                <td>{c.spatial}</td>
                <td>{c.mobility}</td>
                <td>
                  <b>{c.value}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel-footnote">
        {outside
          ? "Top 5 및 선택 후보 · Static = Spatial 단독"
          : "Static = Spatial 단독 · 현재 가중치에 따른 DEMO 비교"}
      </div>
    </section>
  );
}

const DEFAULT_WEIGHTS = Array.from({ length: 21 }, (_, i) => i * 5);
const DEFAULT_COLORS = [
  "#27866b",
  "#d79b34",
  "#5c95cb",
  "#a07bc1",
  "#899c88",
  "#c1837e",
  "#6d9eaa",
  "#aea56f",
];
function fallbackSeries(candidates, weights) {
  return candidates.slice(0, 5).map((c, i) => ({
    id: c.id,
    name: c.short,
    color: DEFAULT_COLORS[i],
    values: weights.map((weight) => {
      const sorted = [...candidates].sort(
        (a, b) =>
          Number(b.mobility) * weight +
            Number(b.spatial) * (100 - weight) -
            (Number(a.mobility) * weight +
              Number(a.spatial) * (100 - weight)) || a.id.localeCompare(b.id),
      );
      return sorted.findIndex((item) => item.id === c.id) + 1;
    }),
  }));
}

export function RankChart({
  mobility = 60,
  series,
  weights = DEFAULT_WEIGHTS,
  selected,
  onSelect,
}) {
  const [hoverIndex, setHoverIndex] = useState(null);
  const sourceSeries = useMemo(
    () => (series?.length ? series : fallbackSeries(DEMO_CANDIDATES, weights)),
    [series, weights],
  );
  const expanded = mobility < 30 || mobility > 80;
  const domainMin = expanded ? 0 : 30,
    domainMax = expanded ? 100 : 80;
  const ticks = expanded ? [0, 20, 40, 60, 80, 100] : [30, 40, 50, 60, 70, 80];
  const plotWeights = weights.filter(
    (weight) =>
      weight >= domainMin &&
      weight <= domainMax &&
      (ticks.includes(weight) || weight === mobility),
  );
  const displaySeries = sourceSeries.map((s) => ({
    ...s,
    values: plotWeights.map((weight) => s.values[weights.indexOf(weight)]),
  }));
  const left = 35,
    right = 397,
    top = 39,
    bottom = 198;
  const maxRank = Math.max(5, ...displaySeries.flatMap((s) => s.values));
  const x = (weight) =>
    left + ((weight - domainMin) / (domainMax - domainMin)) * (right - left);
  const y = (rank) => top + ((rank - 1) / (maxRank - 1)) * (bottom - top);
  const nearestIndex = (weight) =>
    plotWeights.reduce(
      (best, value, i) =>
        Math.abs(value - weight) < Math.abs(plotWeights[best] - weight)
          ? i
          : best,
      0,
    );
  const activeIndex =
    hoverIndex !== null && hoverIndex < plotWeights.length ? hoverIndex : null;
  const tooltipRows =
    activeIndex === null
      ? []
      : displaySeries
          .map((s) => ({ ...s, rank: s.values[activeIndex] }))
          .sort((a, b) => a.rank - b.rank);
  const badgeX = Math.max(left + 64, Math.min(right - 64, x(mobility)));

  return (
    <section className="surface lower-panel rank-chart-panel">
      <PanelTitle info="DEMO M·S 점수의 가중치별 순위입니다. 현재 가중치는 항상 계산 지점에 포함합니다. 선은 표시한 시나리오 지점을 연결하며 실제 연구 결과는 아닙니다.">
        가중치에 따른 순위 변화
      </PanelTitle>
      <div className="rank-chart-layout interactive-rank-chart">
        <svg
          className="rank-chart"
          viewBox="0 0 420 250"
          role="group"
          aria-label={`DEMO Mobility 가중치 ${domainMin}–${domainMax}%에 따른 후보지 순위 변화`}
          onPointerMove={(e) => {
            const box = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - box.left) / box.width) * 420;
            const weight = Math.max(
              domainMin,
              Math.min(
                domainMax,
                domainMin +
                  ((px - left) / (right - left)) * (domainMax - domainMin),
              ),
            );
            setHoverIndex(nearestIndex(weight));
          }}
          onPointerLeave={() => setHoverIndex(null)}
        >
          <text x="14" y="30" fontSize="16" fill="#71816c">
            순위
          </text>
          {Array.from({ length: maxRank }, (_, i) => i + 1).map((rank) => (
            <g key={rank}>
              <line
                x1={left}
                x2={right}
                y1={y(rank)}
                y2={y(rank)}
                stroke="#e5ebe3"
                strokeDasharray="3 4"
              />
              <text
                x="19"
                y={y(rank) + 4}
                fill="#71816c"
                textAnchor="middle"
                fontSize="16"
              >
                {rank}
              </text>
            </g>
          ))}
          <rect
            x={x(mobility) - 6}
            y={top - 7}
            width="12"
            height={bottom - top + 14}
            fill="#e8f1e5"
            rx="3"
          />
          <line
            className="current-weight-line"
            x1={x(mobility)}
            x2={x(mobility)}
            y1={top - 7}
            y2={bottom + 7}
            stroke="#78a27a"
            strokeDasharray="3 4"
          />
          {displaySeries.map((s) => (
            <g
              key={s.id || s.name}
              opacity={!selected || selected === s.id ? 1 : 0.7}
            >
              <polyline
                points={s.values
                  .map((rank, i) => `${x(plotWeights[i])},${y(rank)}`)
                  .join(" ")}
                stroke={s.color}
                strokeWidth={selected === s.id ? 2.6 : 1.8}
                fill="none"
                strokeLinejoin="round"
              />
              {s.values.map((rank, i) => (
                <circle
                  key={i}
                  cx={x(plotWeights[i])}
                  cy={y(rank)}
                  r={selected === s.id ? 3.6 : 3}
                  fill="white"
                  stroke={s.color}
                  strokeWidth="1.6"
                />
              ))}
            </g>
          ))}
          {activeIndex !== null && (
            <line
              x1={x(plotWeights[activeIndex])}
              x2={x(plotWeights[activeIndex])}
              y1={top}
              y2={bottom}
              stroke="#9aa891"
              strokeDasharray="2 3"
            />
          )}
          {ticks.map((weight) => (
            <text
              key={weight}
              x={x(weight)}
              y="223"
              fill="#71816c"
              textAnchor="middle"
              fontSize="16"
            >
              {weight}%
            </text>
          ))}
          {plotWeights.map((weight, i) => (
            <rect
              key={weight}
              className="chart-hover-column"
              x={i === 0 ? left - 10 : (x(plotWeights[i - 1]) + x(weight)) / 2}
              y={top - 7}
              width={
                (i === plotWeights.length - 1
                  ? right + 10
                  : (x(weight) + x(plotWeights[i + 1])) / 2) -
                (i === 0 ? left - 10 : (x(plotWeights[i - 1]) + x(weight)) / 2)
              }
              height={bottom - top + 14}
              fill="transparent"
              tabIndex="0"
              role="button"
              aria-label={`가중치 ${weight}%의 후보지 순위 보기`}
              onFocus={() => setHoverIndex(i)}
              onBlur={() => setHoverIndex(null)}
              onPointerEnter={() => setHoverIndex(i)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setHoverIndex(null);
                if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                  e.preventDefault();
                  const nodes = e.currentTarget
                    .closest("svg")
                    .querySelectorAll(".chart-hover-column");
                  nodes[
                    Math.max(
                      0,
                      Math.min(
                        plotWeights.length - 1,
                        i + (e.key === "ArrowRight" ? 1 : -1),
                      ),
                    )
                  ]?.focus();
                }
              }}
            />
          ))}
          <g
            className="chart-current-badge"
            transform={`translate(${badgeX} 1)`}
            aria-hidden="true"
          >
            <rect x="-62" y="0" width="124" height="21" rx="3" fill="#27866b" />
            <path d="M-4 21L0 26L4 21" fill="#27866b" />
            <text
              x="0"
              y="15"
              fill="#fff"
              textAnchor="middle"
              fontSize="13"
              fontWeight="550"
            >
              현재 가중치: {mobility}%
            </text>
          </g>
          <text
            x="216"
            y="247"
            fill="#7b8973"
            textAnchor="middle"
            fontSize="16"
          >
            가중치 (Mobility 비중)
          </text>
        </svg>
        <div className="chart-legend">
          {displaySeries.map((s) => (
            <button
              key={s.id || s.name}
              data-active={selected === s.id}
              onClick={() => s.id && onSelect?.(s.id)}
              aria-pressed={selected === s.id}
              aria-label={`${s.name} 순위 강조`}
              title={s.name}
            >
              <i style={{ background: s.color }} />
              {s.name}
            </button>
          ))}
        </div>
        {activeIndex !== null && (
          <div
            className="chart-tooltip"
            role="status"
            aria-label="가중치별 순위 상세"
          >
            <b>
              이동 {plotWeights[activeIndex]}% · 공간{" "}
              {100 - plotWeights[activeIndex]}%
            </b>
            {tooltipRows.map((s) => (
              <div
                key={s.id || s.name}
                className={selected === s.id ? "selected-tooltip-row" : ""}
              >
                <span>
                  <i style={{ background: s.color }} />
                  {s.name}
                </span>
                <strong>{s.rank}위</strong>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="panel-footnote rank-chart-status">
        <span>표시한 가중치별 DEMO 순위</span>
        <span>
          현재 <b>M {mobility}%</b>
        </span>
      </div>
    </section>
  );
}

export function BootstrapTable({
  candidates = DEMO_CANDIDATES,
  selected,
  onSelect,
}) {
  const rows = candidates.slice(0, 5),
    scrollRef = useSelectedRowScroll(selected, candidates);
  return (
    <section className="surface lower-panel bootstrap-panel">
      <PanelTitle info="별도 정의된 DEMO 결과입니다. 실제 Bootstrap 재표본추출이나 통계적 검증을 실행한 결과가 아닙니다.">
        Bootstrap 안정성 분석
      </PanelTitle>
      <div className="table-wrap analysis-table-scroll" ref={scrollRef}>
        <table className="bootstrap-table">
          <thead>
            <tr>
              <th scope="col">후보지</th>
              <th scope="col">평균 순위</th>
              <th scope="col">Top-5 선정확률</th>
              <th scope="col">
                변동성 <small>σ</small>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr
                key={c.id}
                className={selected === c.id ? "selected-row" : ""}
                onClick={() => onSelect?.(c.id)}
                data-candidate-id={c.id}
              >
                <td>
                  <button
                    aria-pressed={selected === c.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect?.(c.id);
                    }}
                  >
                    {c.short}
                  </button>
                </td>
                <td>{c.mean}</td>
                <td>
                  <span className="stability-rate">
                    <b className="bootstrap-probability-numeral">
                      {(Number(c.top5) * 100).toFixed(1)}%
                    </b>
                    <i
                      style={{
                        "--rate": `${Number(c.top5) * 100}%`,
                        width: 44,
                      }}
                      aria-hidden="true"
                    />
                  </span>
                </td>
                <td>{c.sigma}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel-footnote">
        별도 DEMO 결과 · 실제 재표본추출 미실행
      </div>
    </section>
  );
}
