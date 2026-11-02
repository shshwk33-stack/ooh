import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  CalendarDays,
  ChartColumnIncreasing,
  Check,
  ChevronDown,
  CircleCheck,
  Database,
  Info,
  MapPin,
  MapPinned,
  Route,
  ShieldCheck,
  Trophy,
  Truck,
  Users,
} from "lucide-react";
import "./UnifiedPanels.css";

const finite = (value) => typeof value === "number" && Number.isFinite(value);
const score = (value) => (finite(value) ? value.toFixed(3) : "—");
const number = (value, digits = 0) =>
  finite(value)
    ? value.toLocaleString("ko-KR", { maximumFractionDigits: digits })
    : "—";
const percent = (value) =>
  finite(value) ? `${(value * 100).toFixed(1)}%` : "—";
const sourceLabel = (kind) =>
  ({
    SYNTHETIC: "시나리오 입력",
    OBSERVED_GPS: "실측 위치자료",
    PUBLIC_AGGREGATE: "공개 집계자료",
    ESTIMATED: "추정자료",
    DERIVED: "파생 분석결과",
  })[kind] || "입력 자료";
const byCandidate = (result, id) =>
  result?.results?.find((row) => row.candidateId === id);
const weightOf = (analysis) =>
  Number(
    analysis.mobilityWeight ??
      analysis.filters?.mobility ??
      analysis.weight ??
      60,
  );
const stabilityTitle = (status) =>
  ({
    weight_mismatch: "현재 가중치의 결과가 없습니다",
    period_mismatch: "분석기간이 다른 결과입니다",
    candidate_mismatch: "후보집합이 다른 결과입니다",
  })[status] || "안정성 결과 연결 대기";

function RoadIcon({ size = 28 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.45"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M7 3H10L6 25H2L7 3ZM18 3H21L26 25H22L18 3Z" />
      <path d="M14 3V7M14 11V16M14 20V25" />
    </svg>
  );
}
function PanelHeading({ children, note, action }) {
  return (
    <div className="unified-panel-heading">
      <h2>{children}</h2>
      <div>
        {note && (
          <span
            className="unified-info"
            tabIndex={0}
            role="note"
            aria-label={note}
          >
            <Info size={14} />
            <span>{note}</span>
          </span>
        )}
        {action}
      </div>
    </div>
  );
}
function Availability({ title, children, compact = false }) {
  return (
    <div className={`unified-availability ${compact ? "compact" : ""}`}>
      <span className="unified-availability-icon">
        <Database size={compact ? 17 : 21} />
      </span>
      <b>{title}</b>
      <p>{children}</p>
    </div>
  );
}

export function UnifiedKpis({ dataset, analysis }) {
  const k = analysis.kpis || analysis;
  const stability = k.stability;
  const items = [
    {
      label: "분석 도로 구간 수",
      value: number(k.roadCount ?? analysis.roadCount),
      unit: finite(k.roadCount ?? analysis.roadCount) ? "구간" : "",
      note: finite(k.roadCount ?? analysis.roadCount)
        ? "연결된 도로 링크 기준"
        : "도로 자료 연결 대기",
      icon: RoadIcon,
    },
    {
      label: "분석 후보지역 수",
      value: number(k.candidateCount ?? analysis.candidates?.length),
      unit: "개",
      note: `${number(k.unitCount ?? dataset.geometry?.units?.features?.length)}개 행정동 · 후보지역 평가`,
      icon: MapPinned,
    },
    {
      label: "최고 위치가치 점수",
      value: score(k.highest ?? analysis.highest),
      note: "입력 M·S의 가중합 · 0–1",
      icon: Trophy,
      accent: true,
      testid: "unified-highest",
    },
    {
      label: "평균 위치가치 점수",
      value: score(k.average ?? analysis.average),
      note: finite(k.average ?? analysis.average)
        ? `점수 확보 ${number(k.scoredCount ?? analysis.candidates?.filter((c) => finite(c.score)).length)}개 후보 평균`
        : "점수 입력 대기",
      icon: ChartColumnIncreasing,
      testid: "unified-average",
    },
    {
      label: "상위 후보지 선정 안정성",
      value: finite(stability) ? percent(stability) : "—",
      note: finite(stability)
        ? `Top-${analysis.bootstrap?.topK || 5} · 현재 가중치 결과`
        : "재표본추출 결과 연결 대기",
      icon: ShieldCheck,
    },
  ];
  return (
    <section
      className="kpi-grid unified-kpis"
      aria-label="위치가치 분석 핵심 지표"
    >
      {items.map(({ label, value, unit, note, icon: Icon, accent, testid }) => (
        <article
          key={label}
          className={`kpi-card ${accent ? "kpi-accent" : ""}`}
        >
          <div className="kpi-icon">
            <Icon size={28} />
          </div>
          <div className="kpi-copy">
            <h2>{label}</h2>
            <div className="kpi-value" data-testid={testid}>
              {value}
              <small>{unit}</small>
            </div>
            <p>{note}</p>
          </div>
        </article>
      ))}
    </section>
  );
}

function Indicator({ icon: Icon, label, value, unit, digits = 0 }) {
  return (
    <div>
      <dt>
        <Icon size={14} />
        {label}
      </dt>
      <dd>
        <b>{number(value, digits)}</b>
        {unit && <small>{unit}</small>}
      </dd>
    </div>
  );
}
function ScoreMeter({ label, value, color }) {
  return (
    <div className="unified-score-meter">
      <div>
        <span>{label}</span>
        <b>{score(value)}</b>
      </div>
      <i>
        <span
          style={{
            width: finite(value) ? `${value * 100}%` : "0%",
            background: color,
          }}
        />
      </i>
    </div>
  );
}
function BootstrapSummary({ analysis, candidate }) {
  const result = byCandidate(analysis.bootstrap, candidate?.id);
  if (!result)
    return (
      <Availability title={stabilityTitle(analysis.bootstrapStatus)} compact>
        운행일·차량 단위로 산출한 재표본추출 결과를 연결하면 평균 순위와
        선정확률이 표시됩니다.
      </Availability>
    );
  return (
    <>
      <div className="unified-stat-grid">
        <div>
          <span>평균 순위</span>
          <b>{number(result.meanRank, 2)}</b>
        </div>
        <div>
          <span>Top-{analysis.bootstrap.topK} 선정확률</span>
          <b>{percent(result.topKProbability)}</b>
        </div>
        <div>
          <span>순위 표준편차</span>
          <b>{number(result.rankSD, 2)}</b>
        </div>
      </div>
      <dl className="unified-detail-metadata">
        <div>
          <dt>재표본 단위</dt>
          <dd>{analysis.bootstrap.resampleUnit}</dd>
        </div>
        <div>
          <dt>반복 횟수</dt>
          <dd>{number(analysis.bootstrap.iterations)}회</dd>
        </div>
        <div>
          <dt>난수 시드</dt>
          <dd>{analysis.bootstrap.seed}</dd>
        </div>
      </dl>
    </>
  );
}

export function UnifiedDetail({
  dataset,
  analysis,
  candidate,
  onSelect,
  mobility,
}) {
  const [tab, setTab] = useState("overview");
  const c = candidate || analysis.selectedCandidate || analysis.candidates?.[0];
  const tabs = [
    ["overview", "개요"],
    ["mobility", "이동특성"],
    ["spatial", "공간특성"],
    ["stability", "안정성"],
  ];
  const weight = finite(mobility) ? mobility : weightOf(analysis);
  if (!c)
    return (
      <section className="surface unified-detail">
        <PanelHeading>
          <MapPin size={16} /> 선택 후보지 상세 분석
        </PanelHeading>
        <Availability title="후보지역을 연결하세요">
          후보지의 ID·좌표·M/S 점수를 입력하면 지도와 분석 결과가 함께
          표시됩니다.
        </Availability>
      </section>
    );
  const source = dataset.meta?.sources?.find((s) => s.id === c.sourceId);
  const m = finite(c.mobilityContribution) ? c.mobilityContribution : null,
    s = finite(c.spatialContribution) ? c.spatialContribution : null;
  const total = finite(m) && finite(s) ? m + s : null;
  const share = total > 0 ? (m / total) * 100 : 0;
  const metrics = c.metrics || {},
    metricUnits = c.metricUnits || {};
  const rawRanks = (analysis.sensitivity || [])
    .map((item) => item.rows?.find((row) => row.id === c.id)?.rank)
    .filter(finite);
  const unit = dataset.geometry?.units?.features?.find(
    (f) => String(f.properties?.code) === String(c.unitCode),
  );
  const interpretation = finite(c.score)
    ? `M ${score(m)} + S ${score(s)} = V ${score(c.score)} · 종합 ${c.rank}위.`
    : "M·S 입력이 부족해 통합 위치가치는 계산하지 않았습니다.";
  function changeTab(id, event) {
    setTab(id);
    if (event)
      requestAnimationFrame(() =>
        document.getElementById(`unified-detail-tab-${id}`)?.focus(),
      );
  }
  return (
    <section
      className="surface unified-detail"
      aria-label="선택 후보지 상세 분석"
    >
      <PanelHeading>
        <MapPin size={16} /> 선택 후보지 상세 분석
      </PanelHeading>
      <div className="unified-detail-body">
        <div className="unified-candidate-heading">
          <span className="unified-rank-mark">{c.rank || "—"}</span>
          <div>
            <h3 data-testid="unified-selected-name">{c.name}</h3>
            <p>{unit?.properties?.name || c.unitCode || c.id}</p>
          </div>
          {c.rank && (
            <span className="unified-rank-status">종합 {c.rank}위</span>
          )}
        </div>
        <div
          className="unified-detail-tabs"
          role="tablist"
          aria-label="후보지 상세 탭"
        >
          {tabs.map(([id, label], index) => (
            <button
              id={`unified-detail-tab-${id}`}
              key={id}
              role="tab"
              aria-selected={tab === id}
              aria-controls={`unified-detail-panel-${id}`}
              tabIndex={tab === id ? 0 : -1}
              onClick={() => changeTab(id)}
              onKeyDown={(e) => {
                if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                  e.preventDefault();
                  changeTab(
                    tabs[(index + (e.key === "ArrowRight" ? 1 : 3)) % 4][0],
                    e,
                  );
                }
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div
          className="unified-detail-content"
          id={`unified-detail-panel-${tab}`}
          role="tabpanel"
          aria-labelledby={`unified-detail-tab-${tab}`}
        >
          {tab === "overview" && (
            <>
              <div className="unified-score-grid">
                <div className="integrated">
                  <span>위치가치 점수 (V)</span>
                  <strong data-testid="unified-detail-score">
                    {score(c.score)}
                  </strong>
                </div>
                <div className="mobility">
                  <span>Mobility (M)</span>
                  <strong>{score(c.mobility)}</strong>
                </div>
                <div className="spatial">
                  <span>Spatial (S)</span>
                  <strong>{score(c.spatial)}</strong>
                </div>
              </div>
              <div className="unified-stack-title">
                <b>점수 구성</b>
                <span>
                  가중치 {weight} : {100 - weight}
                </span>
              </div>
              <div
                className="unified-stack"
                role="img"
                aria-label={`가중 기여값: 이동 ${score(m)}, 공간 ${score(s)}`}
              >
                <i style={{ width: `${share}%` }} />
                <i style={{ width: total > 0 ? `${100 - share}%` : "0%" }} />
              </div>
              <div className="unified-stack-labels">
                <span>
                  이동특성 <b>{score(m)}</b>
                </span>
                <span>
                  공간특성 <b>{score(s)}</b>
                </span>
              </div>
              <h4 className="unified-detail-section-title">주요 분석 지표</h4>
              <dl className="unified-indicators">
                <Indicator
                  icon={Truck}
                  label="차량 활동량"
                  value={metrics.traffic}
                  unit={metricUnits.traffic}
                />
                <Indicator
                  icon={Users}
                  label="인구 활동량"
                  value={metrics.population}
                  unit={metricUnits.population}
                />
                <Indicator
                  icon={MapPinned}
                  label="주변 POI"
                  value={metrics.poi}
                  unit={metricUnits.poi}
                />
                <Indicator
                  icon={Activity}
                  label="상권 활동지수"
                  value={metrics.activity}
                  unit={metricUnits.activity}
                  digits={3}
                />
              </dl>
              <div className="unified-selection-reason">
                <h4>
                  <CircleCheck size={14} /> 평가 해석
                </h4>
                <p>{interpretation}</p>
              </div>
            </>
          )}
          {tab === "mobility" && (
            <>
              <div className="unified-profile-heading">
                <span>MOBILITY SCORE</span>
                <strong>{score(c.mobility)}</strong>
              </div>
              <ScoreMeter
                label="이동특성 점수"
                value={c.mobility}
                color="#27866b"
              />
              <dl className="unified-indicators">
                <Indicator
                  icon={Truck}
                  label="차량 활동량"
                  value={metrics.traffic}
                  unit={metricUnits.traffic}
                />
                <Indicator
                  icon={Route}
                  label="방문 빈도"
                  value={metrics.visitCount}
                  unit={metricUnits.visitCount}
                />
                <Indicator
                  icon={CalendarDays}
                  label="누적 체류시간"
                  value={metrics.dwellMinutes}
                  unit={metricUnits.dwellMinutes}
                />
                <Indicator
                  icon={Activity}
                  label="반복 방문율"
                  value={metrics.repeatRate}
                  unit={metricUnits.repeatRate}
                  digits={3}
                />
              </dl>
              <div className="unified-contribution-card">
                <span>현재 가중 기여값</span>
                <strong>{score(m)}</strong>
                <p>M × {weight}%</p>
              </div>
              <p className="unified-detail-note">
                연결된 이동 지표만 표시합니다. GPS 좌표 개수를 방문 횟수나
                체류시간으로 치환하지 않습니다.
              </p>
            </>
          )}
          {tab === "spatial" && (
            <>
              <div className="unified-profile-heading spatial">
                <span>SPATIAL SCORE</span>
                <strong>{score(c.spatial)}</strong>
              </div>
              <ScoreMeter
                label="공간특성 점수"
                value={c.spatial}
                color="#d99b2f"
              />
              <dl className="unified-indicators">
                <Indicator
                  icon={Users}
                  label="인구 활동량"
                  value={metrics.population}
                  unit={metricUnits.population}
                />
                <Indicator
                  icon={MapPinned}
                  label="주변 POI"
                  value={metrics.poi}
                  unit={metricUnits.poi}
                />
                <Indicator
                  icon={Activity}
                  label="상권 활동지수"
                  value={metrics.activity}
                  unit={metricUnits.activity}
                  digits={3}
                />
              </dl>
              <div className="unified-contribution-card spatial">
                <span>현재 가중 기여값</span>
                <strong>{score(s)}</strong>
                <p>S × {100 - weight}%</p>
              </div>
              <p className="unified-detail-note">
                공간점수는 입력 자료의 비교 기준과 정규화 정의를 따릅니다.
                자료의 시간·공간 해상도는 데이터 관리에서 확인할 수 있습니다.
              </p>
            </>
          )}
          {tab === "stability" && (
            <>
              <h4 className="unified-detail-section-title">
                가중치 조건별 순위
              </h4>
              <div className="unified-stat-grid">
                <div>
                  <span>최고 순위</span>
                  <b>{rawRanks.length ? Math.min(...rawRanks) : "—"}</b>
                </div>
                <div>
                  <span>최저 순위</span>
                  <b>{rawRanks.length ? Math.max(...rawRanks) : "—"}</b>
                </div>
                <div>
                  <span>비교 조건</span>
                  <b>
                    {rawRanks.length}
                    <small>개</small>
                  </b>
                </div>
              </div>
              <p className="unified-detail-note">
                M 비중 0–100%, 5%p 간격의 가중치 민감도입니다.
              </p>
              <h4 className="unified-detail-section-title">
                재표본추출 안정성
              </h4>
              <BootstrapSummary analysis={analysis} candidate={c} />
            </>
          )}
        </div>
        <div className="unified-detail-footer">
          <span
            className={`unified-source-tag ${source?.kind === "SYNTHETIC" ? "scenario" : ""}`}
            title={`${source?.kind || ""} · ${source?.label || c.sourceId}`}
          >
            {sourceLabel(source?.kind)}
          </span>
          <label>
            후보지
            <select
              aria-label="상세 후보지 선택"
              value={c.id}
              onChange={(e) => onSelect?.(e.target.value)}
            >
              {analysis.candidates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.short || item.name}
                </option>
              ))}
            </select>
            <ChevronDown size={10} />
          </label>
        </div>
      </div>
    </section>
  );
}

function ComparisonPanel({ analysis, selectedId, onSelect }) {
  const candidates = analysis.candidates || [];
  const top = candidates.slice(0, 5),
    extra = candidates.find(
      (c) => c.id === selectedId && !top.some((item) => item.id === c.id),
    );
  const rows = extra ? [...top, extra] : top;
  const ref = useRef(null);
  useEffect(() => {
    const row = ref.current?.querySelector(
      `[data-unified-candidate="${CSS.escape(selectedId || "")}"]`,
    );
    if (!row) return;
    const box = ref.current.getBoundingClientRect(),
      rect = row.getBoundingClientRect();
    if (rect.bottom > box.bottom)
      ref.current.scrollTop += rect.bottom - box.bottom + 3;
    else if (rect.top < box.top + 30)
      ref.current.scrollTop -= box.top + 30 - rect.top;
  }, [selectedId, analysis.candidates]);
  return (
    <section className="surface unified-lower-panel">
      <PanelHeading note="Static은 공간점수 단독, Mobility는 이동점수 단독, Integrated는 현재 가중합입니다.">
        모델별 후보지역 비교 <small>(Top-5)</small>
      </PanelHeading>
      <div className="unified-table-scroll" ref={ref}>
        <table className="unified-comparison-table">
          <thead>
            <tr>
              <th>순위</th>
              <th>후보지</th>
              <th>Static (S)</th>
              <th>Mobility (M)</th>
              <th>Integrated (V)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr
                key={c.id}
                data-unified-candidate={c.id}
                className={c.id === selectedId ? "selected" : ""}
                onClick={() => onSelect?.(c.id)}
              >
                <td>{c.rank || "—"}</td>
                <th>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect?.(c.id);
                    }}
                    aria-pressed={c.id === selectedId}
                  >
                    {c.short || c.name}
                  </button>
                </th>
                <td>{score(c.spatial)}</td>
                <td>{score(c.mobility)}</td>
                <td>
                  <b>{score(c.score)}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <p className="unified-table-empty">연결된 후보지역이 없습니다.</p>
        )}
      </div>
      <p className="unified-panel-caption">
        동일 후보집합 · 현재 가중치 기준{extra ? " · 선택 후보 포함" : ""}
      </p>
    </section>
  );
}

const COLORS = [
  "#27866b",
  "#da9a2a",
  "#4a8ed0",
  "#9b78bc",
  "#919e94",
  "#ba8075",
  "#5d9ca0",
  "#b1a06c",
];
function RankPanel({
  analysis,
  selectedId,
  onSelect,
  mobility,
  onWeightChange,
}) {
  const [hover, setHover] = useState(null);
  const weight = finite(mobility) ? mobility : weightOf(analysis);
  const expanded = weight < 30 || weight > 80;
  const ticks = expanded ? [0, 20, 40, 60, 80, 100] : [30, 40, 50, 60, 70, 80];
  const lo = ticks[0],
    hi = ticks[ticks.length - 1];
  const weights =
    analysis.weights || Array.from({ length: 21 }, (_, i) => i * 5);
  const base = analysis.rankSeries || [];
  const candidate = analysis.candidates.find((c) => c.id === selectedId);
  const series =
    base.some((s) => s.id === selectedId) || !candidate
      ? base
      : [
          ...base,
          {
            id: candidate.id,
            name: candidate.short || candidate.name,
            color: COLORS[base.length % COLORS.length],
            values: (analysis.sensitivity || []).map(
              (s) => s.rows.find((c) => c.id === candidate.id)?.rank ?? null,
            ),
          },
        ];
  const plot = weights.filter((w) => w >= lo && w <= hi);
  const maxRank = Math.max(
    5,
    ...series.flatMap((s) => s.values.filter(finite)),
  );
  const left = 32,
    right = 330,
    top = 32,
    bottom = 156,
    x = (w) => left + ((w - lo) / (hi - lo)) * (right - left),
    y = (r) => top + ((r - 1) / Math.max(1, maxRank - 1)) * (bottom - top);
  const hoverRows =
    hover == null
      ? []
      : series
          .map((s) => ({ ...s, rank: s.values[weights.indexOf(hover)] }))
          .filter((s) => finite(s.rank))
          .sort((a, b) => a.rank - b.rank);
  const nearest = (raw) =>
    plot.reduce(
      (best, w) => (Math.abs(raw - w) < Math.abs(raw - best) ? w : best),
      plot[0],
    );
  return (
    <section className="surface unified-lower-panel unified-rank-panel">
      <PanelHeading note="같은 M/S 입력에서 이동특성 비중만 바꾸어 후보지 순위를 재계산합니다.">
        가중치에 따른 순위 변화
      </PanelHeading>
      <div className="unified-rank-layout">
        <svg
          viewBox="0 0 350 200"
          className="unified-rank-chart"
          role="group"
          aria-label="Mobility 가중치에 따른 후보지 순위"
          onPointerMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            setHover(
              nearest(
                lo +
                  ((((e.clientX - rect.left) / rect.width) * 350 - left) /
                    (right - left)) *
                    (hi - lo),
              ),
            );
          }}
          onPointerLeave={() => setHover(null)}
        >
          <rect
            x={Math.max(left, x(weight) - 6)}
            y={top - 4}
            width="12"
            height={bottom - top + 8}
            fill="#eaf2e5"
          />
          {Array.from({ length: maxRank }, (_, i) => i + 1).map((rank) => (
            <g key={rank}>
              <line
                x1={left}
                x2={right}
                y1={y(rank)}
                y2={y(rank)}
                stroke="#e4ebe4"
                strokeDasharray="3 4"
              />
              <text x="16" y={y(rank) + 3} fill="#758779" fontSize="10">
                {rank}
              </text>
            </g>
          ))}
          {ticks.map((w) => (
            <g key={w}>
              <text
                x={x(w)}
                y={bottom + 21}
                textAnchor="middle"
                fontSize="10"
                fill="#63796a"
              >
                {w}%
              </text>
              <rect
                x={x(w) - 16}
                y={top - 7}
                width="32"
                height={bottom - top + 13}
                fill="transparent"
                role="button"
                tabIndex={0}
                aria-label={`이동 가중치 ${w}% 적용`}
                onClick={() => onWeightChange?.(w)}
                onFocus={() => setHover(w)}
                onBlur={() => setHover(null)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onWeightChange?.(w);
                  }
                  if (e.key === "Escape") setHover(null);
                }}
              />
            </g>
          ))}
          {series.map((s, index) => {
            const parts = [];
            let current = [];
            for (const w of plot) {
              const rank = s.values[weights.indexOf(w)];
              if (finite(rank)) {
                current.push([x(w), y(rank)]);
              } else if (current.length) {
                parts.push(current);
                current = [];
              }
            }
            if (current.length) parts.push(current);
            const selected = s.id === selectedId,
              color = s.color || COLORS[index % COLORS.length];
            return (
              <g
                key={s.id}
                opacity={selected || !selectedId ? 1 : 0.74}
                pointerEvents="none"
              >
                {parts.map((part, j) => (
                  <polyline
                    key={j}
                    points={part.map((p) => p.join(",")).join(" ")}
                    fill="none"
                    stroke={color}
                    strokeWidth={selected ? 2.5 : 1.6}
                  />
                ))}
                {ticks.map((w) => {
                  const rank = s.values[weights.indexOf(w)];
                  return finite(rank) ? (
                    <circle
                      key={w}
                      cx={x(w)}
                      cy={y(rank)}
                      r={selected ? 3 : 2.3}
                      fill="#fff"
                      stroke={color}
                      strokeWidth="1.5"
                    />
                  ) : null;
                })}
              </g>
            );
          })}
          <line
            x1={x(weight)}
            x2={x(weight)}
            y1={top - 4}
            y2={bottom + 4}
            stroke="#8eb39a"
            strokeDasharray="3 3"
          />
          <text
            x={(left + right) / 2}
            y="197"
            textAnchor="middle"
            fontSize="10"
            fill="#617867"
          >
            가중치 (Mobility 비중)
          </text>
          <text
            x={Math.max(left + 37, Math.min(right - 37, x(weight)))}
            y="15"
            textAnchor="middle"
            fill="#276947"
            fontSize="10"
            fontWeight="650"
          >
            현재 {weight}%
          </text>
        </svg>
        <div className="unified-chart-legend">
          {series.map((s, index) => (
            <button
              key={s.id}
              className={s.id === selectedId ? "selected" : ""}
              onClick={() => onSelect?.(s.id)}
              aria-label={`${s.name} 순위 강조`}
              aria-pressed={s.id === selectedId}
            >
              <i
                style={{ background: s.color || COLORS[index % COLORS.length] }}
              />
              {s.name}
            </button>
          ))}
        </div>
        {hover != null && (
          <div
            className="unified-chart-tooltip"
            role="status"
            aria-label="가중치별 순위 상세"
          >
            <b>Mobility {hover}%</b>
            {hoverRows.map((s) => (
              <span key={s.id}>
                <i style={{ background: s.color }} />
                {s.name}
                <strong>{s.rank}위</strong>
              </span>
            ))}
          </div>
        )}
      </div>
      {!series.length && (
        <p className="unified-chart-empty">
          M·S 점수가 연결되면 순위 변화가 표시됩니다.
        </p>
      )}
    </section>
  );
}

function StabilityPanel({ analysis, selectedId, onSelect }) {
  const result = analysis.bootstrap;
  return (
    <section className="surface unified-lower-panel unified-bootstrap-panel">
      <PanelHeading note="독립 표본 단위의 재표본추출 결과가 현재 가중치·기간과 일치할 때 표시합니다.">
        Bootstrap 안정성 분석{" "}
        {result && <small>{number(result.iterations)}회</small>}
      </PanelHeading>
      {result ? (
        <>
          <div className="unified-table-scroll">
            <table className="unified-bootstrap-table">
              <thead>
                <tr>
                  <th>후보지</th>
                  <th>평균 순위</th>
                  <th>Top-{result.topK} 선정확률</th>
                  <th>순위 변동성</th>
                </tr>
              </thead>
              <tbody>
                {result.results
                  .slice()
                  .sort((a, b) => a.meanRank - b.meanRank)
                  .map((row) => {
                    const c = analysis.candidates.find(
                      (c) => c.id === row.candidateId,
                    );
                    return (
                      <tr
                        key={row.candidateId}
                        className={
                          selectedId === row.candidateId ? "selected" : ""
                        }
                        onClick={() => onSelect?.(row.candidateId)}
                      >
                        <th>
                          <button onClick={() => onSelect?.(row.candidateId)}>
                            {c?.short || c?.name || row.candidateId}
                          </button>
                        </th>
                        <td>{number(row.meanRank, 2)}</td>
                        <td>
                          <span className="unified-probability">
                            <i
                              style={{ width: `${row.topKProbability * 100}%` }}
                            />
                            <b>{percent(row.topKProbability)}</b>
                          </span>
                        </td>
                        <td>{number(row.rankSD, 2)}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
          <p className="unified-panel-caption">
            재표본 단위 {result.resampleUnit} · Seed {result.seed}
          </p>
        </>
      ) : (
        <div className="unified-bootstrap-empty">
          <div className="unified-empty-symbol">
            <ShieldCheck size={25} strokeWidth={1.4} />
          </div>
          <b>{stabilityTitle(analysis.bootstrapStatus)}</b>
          <p>평균 순위 · Top-K 선정확률 · 순위 변동성</p>
          <span>검증된 결과를 연결하면 현재 후보지역에 적용됩니다.</span>
        </div>
      )}
    </section>
  );
}

export function UnifiedAnalysisPanels({
  dataset,
  analysis,
  selectedId,
  onSelect,
  mobility,
  onWeightChange,
}) {
  return (
    <section
      className="unified-analysis-panels"
      aria-label="모델 비교와 민감도 및 안정성"
    >
      <ComparisonPanel
        analysis={analysis}
        selectedId={selectedId}
        onSelect={onSelect}
      />
      <RankPanel
        analysis={analysis}
        selectedId={selectedId}
        onSelect={onSelect}
        mobility={mobility}
        onWeightChange={onWeightChange}
      />
      <StabilityPanel
        analysis={analysis}
        selectedId={selectedId}
        onSelect={onSelect}
      />
    </section>
  );
}
