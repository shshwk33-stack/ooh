import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  ChartColumnIncreasing,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  CircleCheck,
  Clock3,
  Database,
  FileChartColumn,
  FlaskConical,
  Info,
  Layers3,
  Map,
  MapPin,
  MapPinned,
  Menu,
  Play,
  Route,
  RotateCcw,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Trophy,
  Truck,
  Users,
  X,
} from "lucide-react";
import DesignMap from "./DesignMap";
import CandidateDetail from "./CandidateDetail";
import { deriveDemo, rankAtWeight } from "./demoModel";
import { PRESETS } from "./demo";
import ResearchWorkspace from "./ResearchWorkspace";
import {
  BootstrapTable,
  ComparisonTable,
  DemoBadge,
  PanelTitle,
  RankChart,
} from "./AnalysisPanels";

const navigation = [
  { id: "dashboard", label: "분석 대시보드", icon: ChartColumnIncreasing },
  { id: "spatial", label: "공간 분석", suffix: "GIS", icon: Map },
  { id: "scenarios", label: "시나리오 비교", icon: Layers3 },
  { id: "sensitivity", label: "민감도 및 강건성 분석", icon: Activity },
  { id: "data", label: "데이터 관리", icon: Database },
  { id: "reports", label: "분석 결과 및 보고서", icon: FileChartColumn },
];
const initialLayers = {
  roads: true,
  vehicle: true,
  milk: false,
  population: true,
  value: true,
  candidates: true,
  poi: false,
};
const initialSettings = {
  region: "서울특별시 마포구",
  year: "2024년",
  period: "평일",
  time: "전체 시간대 (06:00–22:00)",
  scenario: "밀크런 (기본 시나리오)",
};

function Sidebar({
  active,
  onNavigate,
  settings,
  onGuide,
  mobileOpen,
  setMobileOpen,
  research = false,
}) {
  return (
    <aside className={"sidebar " + (mobileOpen ? "mobile-open" : "")}>
      <a
        className="brand"
        href="#dashboard"
        onClick={(e) => {
          e.preventDefault();
          onNavigate("dashboard");
        }}
      >
        <div className="brand-mark">
          <Layers3 size={33} strokeWidth={1.8} />
        </div>
        <div>
          <b>TRANSIT ATLAS</b>
          <span>From Movement to Meaning.</span>
        </div>
      </a>
      <div className="sidebar-nav">
        <div className="sidebar-eyebrow">분석 워크스페이스</div>
        <nav aria-label="주요 메뉴">
          {navigation.map(({ id, label, suffix, icon: Icon }) => (
            <button
              key={id}
              className={active === id ? "active" : ""}
              aria-current={active === id ? "page" : undefined}
              onClick={() => {
                onNavigate(id);
                setMobileOpen(false);
              }}
            >
              <Icon size={17} strokeWidth={1.65} />
              <span>
                {research && id === "scenarios" ? "운행조건 비교" : research && id === "sensitivity" ? "모델 및 검증 현황" : label}
                {suffix && <small> ({suffix})</small>}
              </span>
            </button>
          ))}
        </nav>
      </div>
      <section className="sidebar-research">
        <h2>
          <Settings2 size={14} /> 연구지역 정보 <DemoBadge />
        </h2>
        <dl>
          <div>
            <MapPin size={13} />
            <dt>연구지역</dt>
            <dd>
              {settings.region === "서울특별시 마포구"
                ? "서울특별시 마포구"
                : settings.region}
            </dd>
          </div>
          <div>
            <CalendarDays size={13} />
            <dt>기준연도</dt>
            <dd>{settings.year}</dd>
          </div>
          <div>
            <Clock3 size={13} />
            <dt>{research ? "운행기간" : "분석기간"}</dt>
            <dd>
              {settings.period} ·{" "}
              {settings.time.startsWith("전체 시간대") ? "전체" : settings.time}
            </dd>
          </div>
          <div>
            <Layers3 size={13} />
            <dt>데이터 출처</dt>
            <dd>{research ? "KOSTAT 공개 경계" : "View-T + 공간정보"}</dd>
          </div>
          <div>
            <Database size={13} />
            <dt>데이터 유형</dt>
            <dd>{research ? "공개 경계 · 합성 GPS" : "디자인용 예시"}</dd>
          </div>
        </dl>
      </section>
      <section className="sidebar-system">
        <h2>
          <Activity size={14} /> 시스템 상태
        </h2>
        <div>
          <span className="status-light" />
          <span>{research ? "공간자료 검증" : "DEMO 데이터"}</span>
          <b>정상</b>
        </div>
        <div>
          <span className="status-light" />
          <span>{research ? "GPS 입력 검증" : "UI 점수 계산"}</span>
          <b>정상</b>
        </div>
        <div>
          <span className="status-light" />
          <span>지도 조작</span>
          <b>정상</b>
        </div>
      </section>
      <div className="sidebar-bottom">
        <button onClick={onGuide}>
          <BookOpen size={16} /> 분석 가이드 <ArrowUpRight size={12} />
        </button>
        <div>
          <span>TRANSIT ATLAS</span>
          <small>UI EDITION · 2.0</small>
        </div>
      </div>
    </aside>
  );
}
function HeaderSelect({ label, value, onChange, options, icon: Icon }) {
  return (
    <label className="header-select" title={label}>
      <Icon size={14} />
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <ChevronDown size={10} />
    </label>
  );
}
function RoadIcon({ size = 27, strokeWidth = 1.5 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M7 3H10L6 25H2L7 3ZM18 3H21L26 25H22L18 3Z" />
      <path d="M14 3V7M14 11V16M14 20V25" />
    </svg>
  );
}
function KPI({ icon: Icon, label, value, unit, note, accent }) {
  return (
    <article className={"kpi-card " + (accent ? "kpi-accent" : "")}>
      <div className="kpi-icon">
        <Icon size={27} strokeWidth={1.45} />
      </div>
      <div className="kpi-copy">
        <h2>{label}</h2>
        <div className="kpi-value">
          {value}
          <small>{unit}</small>
        </div>
        <p>{note}</p>
      </div>
      <DemoBadge />
    </article>
  );
}
function SettingsPanel({
  mobility,
  setMobility,
  settings,
  setSetting,
  onApply,
  applied,
  onReset,
}) {
  return (
    <section className="surface settings-panel">
      <div className="settings-title">
        <h2>분석 설정</h2>
        <SlidersHorizontal size={17} />
      </div>
      <div className="settings-section-heading">
        <b>가중치 설정</b>
        <span>
          V = w<sub>M</sub>·M + w<sub>S</sub>·S
        </span>
      </div>
      <div className="weight-field">
        <label htmlFor="mobility-weight">
          Mobility <span>(이동 특성)</span>
        </label>
        <div className="weight-number">
          <small>이동 특성 비중</small>
          <b>
            {mobility}
            <span>%</span>
          </b>
        </div>
        <input
          id="mobility-weight"
          aria-label="Mobility 가중치"
          type="range"
          min="0"
          max="100"
          step="5"
          value={mobility}
          onChange={(e) => setMobility(+e.target.value)}
          style={{ "--progress": `${mobility}%` }}
        />
      </div>
      <div className="weight-field spatial-weight">
        <label htmlFor="spatial-weight">
          Spatial <span>(공간 특성)</span>
        </label>
        <div className="weight-number">
          <small>공간 특성 비중</small>
          <b>
            {100 - mobility}
            <span>%</span>
          </b>
        </div>
        <input
          id="spatial-weight"
          aria-label="Spatial 가중치"
          type="range"
          min="0"
          max="100"
          step="5"
          value={100 - mobility}
          onChange={(e) => setMobility(100 - +e.target.value)}
          style={{ "--progress": `${100 - mobility}%` }}
        />
      </div>
      <div className="settings-divider" />
      <label className="control-label">가중치 프리셋</label>
      <div className="preset-grid">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            className={mobility === p.mobility ? "active" : ""}
            aria-pressed={mobility === p.mobility}
            onClick={() => setMobility(p.mobility)}
          >
            <span>{p.label}</span>
            <small>
              {p.mobility} : {100 - p.mobility}
            </small>
          </button>
        ))}
      </div>
      <label className="control-label" htmlFor="scenario-select">
        분석 시나리오
      </label>
      <div className="control-select scenario-control">
        <Truck size={13} />
        <select
          id="scenario-select"
          aria-label="분석 시나리오"
          value={settings.scenario}
          onChange={(e) => setSetting("scenario", e.target.value)}
        >
          <option>밀크런 (기본 시나리오)</option>
          <option>도심 순환 시나리오</option>
          <option>거점 집중 시나리오</option>
        </select>
        <ChevronDown size={10} />
      </div>
      <label className="control-label" htmlFor="time-select">
        분석 시간대
      </label>
      <div className="control-select time-control">
        <Clock3 size={13} />
        <select
          id="time-select"
          aria-label="분석 시간대"
          value={settings.time}
          onChange={(e) => setSetting("time", e.target.value)}
        >
          <option>전체 시간대 (06:00–22:00)</option>
          <option>오전 (06–12시)</option>
          <option>오후 (12–18시)</option>
          <option>저녁 (18–24시)</option>
        </select>
        <ChevronDown size={10} />
      </div>
      <div className="settings-actions">
        <button className="apply-button" onClick={onApply}>
          {applied ? (
            <Check size={14} />
          ) : (
            <Play size={14} fill="currentColor" />
          )}
          {applied ? "미리보기 적용됨" : "분석 미리보기"}
        </button>
        <button
          className="settings-reset"
          aria-label="DEMO 설정 초기화"
          title="설정 초기화"
          onClick={onReset}
        >
          <RotateCcw size={15} />
        </button>
      </div>
      <p className="settings-note">
        DEMO 가중합을 즉시 반영합니다.
        <br />
        실제 연구 엔진은 연결되지 않았습니다.
      </p>
    </section>
  );
}
export default function App() {
  const [workspace, setWorkspace] = useState("research");
  const [active, setActive] = useState("dashboard"),
    [mobility, setMobility] = useState(60),
    [mapMode, setMapMode] = useState("value"),
    [settings, setSettings] = useState(initialSettings),
    [layers, setLayers] = useState(initialLayers),
    [selected, setSelected] = useState("TA-001"),
    [modal, setModal] = useState(null),
    [mobileOpen, setMobileOpen] = useState(false),
    [applied, setApplied] = useState(false),
    [toast, setToast] = useState(""),
    [exportOpen, setExportOpen] = useState(false);
  const modalRef = useRef(null),
    mapSection = useRef(null),
    bottomSection = useRef(null);
  const demo = useMemo(() => deriveDemo(mobility), [mobility]);
  const candidate =
    demo.candidates.find((c) => c.id === selected) || demo.candidates[0];
  const chartWeights = Array.from({ length: 21 }, (_, i) => i * 5);
  const plottedCandidates = demo.rankSeries.some((s) => s.id === selected)
    ? demo.rankSeries
    : [
        ...demo.rankSeries,
        { id: candidate.id, name: candidate.short, color: "#6c839c" },
      ];
  const chartSeries = plottedCandidates.map((series) => ({
    ...series,
    values: chartWeights.map((w) => rankAtWeight(series.id, w)),
  }));
  function setSetting(key, value) {
    setSettings((s) => ({ ...s, [key]: value }));
    setApplied(false);
  }
  function updateMobility(n) {
    setMobility(n);
    setApplied(false);
  }
  function navigate(id) {
    setActive(id);
    if (id === "spatial")
      requestAnimationFrame(() =>
        mapSection.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        }),
      );
    else if (id === "sensitivity")
      requestAnimationFrame(() =>
        bottomSection.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        }),
      );
    else window.scrollTo({ top: 0, behavior: "smooth" });
  }
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 3000);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (!modal) return;
    const before = document.activeElement;
    const el = modalRef.current;
    el?.querySelector("button")?.focus();
    const fn = (e) => {
      if (e.key === "Escape") setModal(null);
      if (e.key === "Tab") {
        const nodes = el?.querySelectorAll("button,a,select,input");
        if (!nodes?.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", fn);
    return () => {
      document.removeEventListener("keydown", fn);
      before?.focus();
    };
  }, [modal]);
  useEffect(() => {
    if (!exportOpen) return;
    const close = (e) => {
      if (!e.target.closest(".export-wrapper")) setExportOpen(false);
    };
    const key = (e) => {
      if (e.key === "Escape") setExportOpen(false);
    };
    document.addEventListener("click", close);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", key);
    };
  }, [exportOpen]);
  function exportDemo() {
    const csv =
      "\uFEFF데이터유형,순위,후보지,위치가치,Mobility,Spatial,M가중치,S가중치\n" +
      demo.candidates
        .map((c) =>
          [
            "DEMO",
            c.rank,
            c.name,
            c.value,
            c.mobility,
            c.spatial,
            mobility + "%",
            100 - mobility + "%",
          ].join(","),
        )
        .join("\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8;" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "TRANSIT_ATLAS_DEMO.csv";
    a.click();
    URL.revokeObjectURL(url);
    setExportOpen(false);
    setToast("DEMO 예시 데이터를 CSV로 저장했습니다.");
  }
  const showDashboard = ["dashboard", "spatial", "sensitivity"].includes(
    active,
  );
  if (workspace === "research") {
    return <ResearchWorkspace Sidebar={Sidebar} HeaderSelect={HeaderSelect}
      onOpenDemo={() => setWorkspace("demo")} />;
  }
  return (
    <div className="atlas-app">
      <Sidebar
        active={active}
        onNavigate={navigate}
        settings={settings}
        onGuide={() => setModal("guide")}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />
      {mobileOpen && (
        <button
          className="sidebar-scrim"
          aria-label="메뉴 닫기"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <div className="main-layout">
        <header className="app-header">
          <div className="heading-group">
            <button
              className="mobile-menu"
              aria-label="메뉴 열기"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <Menu size={20} />
            </button>
            <div>
              <h1>Transit OOH Analytics</h1>
              <p>
                배송차량 이동특성과 도시 공간정보를 결합한 잠재적 광고 위치가치
                분석
              </p>
            </div>
          </div>
          <div className="header-controls">
            <HeaderSelect
              label="분석지역"
              icon={MapPin}
              value={settings.region}
              onChange={(v) => setSetting("region", v)}
              options={["서울특별시 마포구", "홍대입구 권역", "공덕 권역"]}
            />
            <HeaderSelect
              label="기준연도"
              icon={CalendarDays}
              value={settings.year}
              onChange={(v) => setSetting("year", v)}
              options={["2024년", "2025년", "2026년"]}
            />
            <HeaderSelect
              label="분석기간"
              icon={CalendarDays}
              value={settings.period}
              onChange={(v) => setSetting("period", v)}
              options={["평일", "주말", "전체"]}
            />
            <button
              className="source-button"
              onClick={() => setModal("sources")}
            >
              <Layers3 size={14} />
              <span>View-T + Spatial</span>
              <ChevronDown size={10} />
            </button>
            <button
              className="header-info"
              aria-label="데이터 및 화면 안내"
              onClick={() => setModal("sources")}
            >
              <Info size={19} />
            </button>
          </div>
        </header>
        <main>
          <div className="workspace-mode-bar demo-workspace-mode-bar">
            <div className="workspace-mode-switch" aria-label="워크스페이스 선택">
              <button onClick={() => setWorkspace("research")}>공개자료 · 운행 탐색</button>
              <button className="selected" aria-pressed="true">예시 점수 비교</button>
            </div>
            <span className="workspace-scope-note">DEMO 입력 · 기존 가중치 계산 화면</span>
          </div>
          <div className="workspace-strip">
            <div>
              <span className="workspace-dot" /> RESEARCH WORKSPACE <i />{" "}
              {navigation.find((n) => n.id === active)?.label}
            </div>
            <div>
              <span className="demo-mode">
                <FlaskConical size={11} /> DEMO · 예시 데이터
              </span>
              <div className="export-wrapper">
                <button
                  className="export-toggle"
                  aria-expanded={exportOpen}
                  onClick={() => setExportOpen(!exportOpen)}
                >
                  <ArrowDownToLine size={12} /> 내보내기{" "}
                  <ChevronDown size={9} />
                </button>
                {exportOpen && (
                  <div className="export-menu">
                    <button onClick={exportDemo}>예시 데이터 CSV</button>
                    <button
                      onClick={() => {
                        setExportOpen(false);
                        window.print();
                      }}
                    >
                      화면 인쇄 / PDF 저장
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
          {showDashboard ? (
            <>
              <section className="kpi-grid" aria-label="DEMO 핵심 지표">
                <KPI
                  icon={RoadIcon}
                  label="분석 도로 구간 수"
                  value={String(demo.roadCount)}
                  unit="구간"
                  note="도로망 규모 예시"
                />
                <KPI
                  icon={MapPinned}
                  label="분석 후보지역 수"
                  value={String(demo.candidates.length)}
                  unit="개"
                  note="후보지역 설정 예시"
                />
                <KPI
                  icon={Trophy}
                  label="최고 위치가치 점수"
                  value={demo.highest}
                  note="정규화 점수 · 0–1"
                  accent
                />
                <KPI
                  icon={ChartColumnIncreasing}
                  label="평균 위치가치 점수"
                  value={demo.average}
                  note="후보지역 평균 예시"
                />
                <KPI
                  icon={ShieldCheck}
                  label="상위 후보지 선정 안정성"
                  value={demo.stability}
                  note="현재 Top 5 · 별도 DEMO 결과 평균"
                />
              </section>
              <section
                className={
                  "main-analysis-grid " +
                  (active === "spatial" ? "spatial-view" : "")
                }
                ref={mapSection}
                aria-label="GIS 지도 및 분석 설정"
              >
                <SettingsPanel
                  mobility={mobility}
                  setMobility={updateMobility}
                  settings={settings}
                  setSetting={setSetting}
                  applied={applied}
                  onReset={() => {
                    setMobility(60);
                    setSettings(initialSettings);
                    setLayers(initialLayers);
                    setSelected("TA-001");
                    setMapMode("value");
                    setApplied(false);
                    setToast("기본 DEMO 설정으로 초기화했습니다.");
                  }}
                  onApply={() => {
                    setApplied(true);
                    setToast("선택한 조건을 미리보기에 적용했습니다.");
                  }}
                />
                <section className="surface map-panel">
                  <div className="map-panel-title">
                    <h2>
                      GIS 공간 분석 <span>|</span>{" "}
                      <small>도로별 이동·공간특성 및 위치가치</small>
                    </h2>
                    <button
                      onClick={() => setModal("map")}
                      aria-label="지도 안내"
                    >
                      <Info size={13} />
                    </button>
                  </div>
                  <DesignMap
                    mode={mapMode}
                    onModeChange={setMapMode}
                    candidates={demo.candidates}
                    selected={selected}
                    onSelect={setSelected}
                    layers={layers}
                    setLayers={setLayers}
                  />
                </section>
                <CandidateDetail
                  candidate={candidate}
                  candidates={demo.candidates}
                  mobility={mobility}
                  onSelect={setSelected}
                />
              </section>
              <section
                className="bottom-analysis-grid"
                ref={bottomSection}
                aria-label="DEMO 모델 비교와 안정성"
              >
                <ComparisonTable
                  candidates={demo.candidates}
                  selected={selected}
                  onSelect={setSelected}
                />
                <RankChart
                  mobility={mobility}
                  series={chartSeries}
                  weights={chartWeights}
                  selected={selected}
                  onSelect={setSelected}
                />
                <BootstrapTable
                  candidates={demo.candidates}
                  selected={selected}
                  onSelect={setSelected}
                />
              </section>
            </>
          ) : active === "scenarios" ? (
            <ScenarioPage
              mobility={mobility}
              onApply={(n) => {
                updateMobility(n);
                setActive("dashboard");
                setToast("가중치 프리셋을 선택했습니다.");
              }}
            />
          ) : active === "data" ? (
            <DataPage onSources={() => setModal("sources")} />
          ) : (
            <ReportsPage onExport={exportDemo} onPrint={() => window.print()} />
          )}
          <footer className="app-footer">
            <span>
              TRANSIT ATLAS <i /> From Movement to Meaning.
            </span>
            <div>
              <span>화면의 모든 수치와 지도는 디자인용 예시입니다.</span>
              <button onClick={() => setModal("sources")}>
                데이터 명세 <ArrowUpRight size={10} />
              </button>
            </div>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CircleCheck size={15} />
          {toast}
        </div>
      )}
      {modal && (
        <div className="modal-backdrop" onClick={() => setModal(null)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={
              modal === "guide"
                ? "분석 가이드"
                : modal === "map"
                  ? "지도 안내"
                  : "데이터 명세"
            }
            ref={modalRef}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              aria-label="닫기"
              onClick={() => setModal(null)}
            >
              <X size={19} />
            </button>
            <span className="modal-eyebrow">TRANSIT ATLAS · UI EDITION</span>
            <h2>
              {modal === "guide"
                ? "대시보드 사용 가이드"
                : modal === "map"
                  ? "GIS 디자인 지도 안내"
                  : "데이터 구성과 표현 범위"}
            </h2>
            <DemoBadge />
            {modal === "guide" ? (
              <>
                <p>설정과 지도, 후보지 상세를 함께 탐색하는 대시보드입니다.</p>
                <div className="guide-item">
                  <b>01</b>
                  <div>
                    <h3>분석 조건 선택</h3>
                    <p>
                      Mobility·Spatial 슬라이더, 프리셋, 시나리오와 시간대를
                      선택하세요. 선택한 값은 설정 미리보기에 반영됩니다.
                    </p>
                  </div>
                </div>
                <div className="guide-item">
                  <b>02</b>
                  <div>
                    <h3>지도 레이어 탐색</h3>
                    <p>
                      레이어 제어에서 표시 항목을 바꾸고 지도를 확대·축소하거나
                      드래그할 수 있습니다.
                    </p>
                  </div>
                </div>
                <div className="guide-item">
                  <b>03</b>
                  <div>
                    <h3>후보지역 비교</h3>
                    <p>
                      지도 마커, 비교표의 후보지 이름 또는 상세 패널의 선택
                      메뉴로 후보지를 바꾸세요.
                    </p>
                  </div>
                </div>
                <div className="guide-item">
                  <b>04</b>
                  <div>
                    <h3>화면과 예시 데이터 저장</h3>
                    <p>
                      내보내기 메뉴에서 DEMO CSV 또는 인쇄용 화면을 저장할 수
                      있습니다.
                    </p>
                  </div>
                </div>
              </>
            ) : modal === "map" ? (
              <>
                <p>
                  이 지도는 마포구 사례를 연상하도록 직접 구성한 SVG
                  개념도입니다. 실제 행정 경계·도로 좌표·통행량을 연결하지
                  않았습니다.
                </p>
                <ul className="plain-list">
                  <li>
                    도로망, 차량 경로, 밀크런 경로, 인구·위치가치 히트맵, 후보지
                    마커를 각각 표시합니다.
                  </li>
                  <li>
                    색상과 이동 경로는 디자인 표현이며 관측값·예측 결과를
                    의미하지 않습니다.
                  </li>
                  <li>
                    축척은 지도 컨트롤의 표현 예시이며 실제 거리 측정에 사용할
                    수 없습니다.
                  </li>
                </ul>
              </>
            ) : (
              <>
                <p>
                  이번 화면은 API·연구 엔진과 분리된 프런트엔드입니다. 점수와
                  순위는 프런트엔드 DEMO 가중합으로 갱신됩니다. 실제 연구 계산은
                  실행하지 않습니다.
                </p>
                <div className="source-table">
                  <div>
                    <b>View-T + Spatial</b>
                    <span>
                      향후 자료 구성을 나타내는 UI 라벨 · 실제 연동 없음
                    </span>
                  </div>
                  <div>
                    <b>지도·도로·경로</b>
                    <span>자체 제작 SVG 개념도 · 실제 지리정보 미사용</span>
                  </div>
                  <div>
                    <b>KPI·후보지 지표</b>
                    <span>
                      DEMO 샘플에서 일관되게 계산 · 실측 데이터와 구분
                    </span>
                  </div>
                  <div>
                    <b>모델 비교·순위 변화</b>
                    <span>프런트엔드 DEMO 가중합과 순위 · 연구모델 미실행</span>
                  </div>
                  <div>
                    <b>Bootstrap 안정성</b>
                    <span>재표본추출 미실행 · 선정률과 변동성은 예시</span>
                  </div>
                  <div>
                    <b>가중치·기간·지역</b>
                    <span>가중합 점수와 순위 갱신 · 기간·지역은 UI 조건</span>
                  </div>
                </div>
              </>
            )}
            <div className="modal-note">
              <Info size={14} />
              <span>
                실제 연구 결과로 활용하려면 별도 데이터 연결과 모델 검증이
                필요합니다.
              </span>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
function ScenarioPage({ mobility, onApply }) {
  return (
    <section className="secondary-page">
      <div className="secondary-heading">
        <div>
          <span>SCENARIO COMPARISON</span>
          <h2>동일한 공간, 서로 다른 분석 관점</h2>
          <p>가중치 프리셋의 구성과 적용 상태를 비교합니다.</p>
        </div>
        <DemoBadge />
      </div>
      <div className="scenario-cards">
        {PRESETS.filter((p) => p.id !== "balanced").map((p, i) => (
          <article className="surface scenario-card" key={p.id}>
            <span className="scenario-number">0{i + 1}</span>
            <h3>{p.label}</h3>
            <p>
              {i === 0
                ? "공간의 잠재력에 집중합니다."
                : i === 1
                  ? "이동과 공간 특성을 함께 봅니다."
                  : "배송차량의 이동 특성에 집중합니다."}
            </p>
            <div className="scenario-weight">
              <span>
                M <b>{p.mobility}%</b>
              </span>
              <span>
                S <b>{100 - p.mobility}%</b>
              </span>
            </div>
            <div className="scenario-result">
              <span>최상위 후보</span>
              <b>{deriveDemo(p.mobility).candidates[0].short}</b>
              <strong>{deriveDemo(p.mobility).highest}</strong>
            </div>
            <div className="scenario-weight-bar">
              <i style={{ width: p.mobility + "%" }} />
            </div>
            <ul>
              <li>
                <span>자료 유형</span>
                <b>DEMO</b>
              </li>
              <li>
                <span>시나리오</span>
                <b>밀크런 가상 운행</b>
              </li>
              <li>
                <span>적용 상태</span>
                <b>{mobility === p.mobility ? "현재 설정" : "선택 가능"}</b>
              </li>
            </ul>
            <button onClick={() => onApply(p.mobility)}>
              {mobility === p.mobility
                ? "현재 설정으로 보기"
                : "이 가중치 선택"}
              <ArrowRight size={13} />
            </button>
          </article>
        ))}
      </div>
      <div className="surface scenario-note">
        <Info size={15} />
        <span>
          시나리오 선택 시 DEMO 점수와 순위를 다시 표시합니다. 연구 엔진과의
          연결은 후속 단계입니다.
        </span>
      </div>
    </section>
  );
}
function DataPage({ onSources }) {
  const rows = [
    ["도로 네트워크", "도로 구간·통행량", "SVG 디자인 레이어"],
    ["차량 이동정보", "방문·체류·반복 이동", "가상 경로"],
    ["공간정보", "인구·시설·상권", "고정 예시 지표"],
    ["후보지역", "위치가치·순위", "8개 예시 후보"],
    ["분석 결과", "모델 비교·민감도·안정성", "디자인용 표·그래프"],
  ];
  return (
    <section className="secondary-page">
      <div className="secondary-heading">
        <div>
          <span>DATA MANAGEMENT</span>
          <h2>데이터 구성 현황</h2>
          <p>화면에서 사용한 디자인 자료와 적용 범위를 확인합니다.</p>
        </div>
        <button className="outline-button" onClick={onSources}>
          <Database size={13} /> 데이터 명세
        </button>
      </div>
      <div className="data-summary-grid">
        <div className="surface">
          <Database size={23} />
          <b>로컬 예시 자료</b>
          <span>외부 API 미연결</span>
        </div>
        <div className="surface">
          <ShieldCheck size={23} />
          <b>연구모델 분리</b>
          <span>기존 분석 코드 미사용</span>
        </div>
        <div className="surface">
          <Layers3 size={23} />
          <b>7개 시각화 레이어</b>
          <span>화면 내 On / Off</span>
        </div>
      </div>
      <section className="surface data-table-panel">
        <PanelTitle>화면 데이터 목록</PanelTitle>
        <table className="data-table">
          <thead>
            <tr>
              <th>자료 구분</th>
              <th>표현 항목</th>
              <th>적용 형태</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([a, b, c]) => (
              <tr key={a}>
                <td>{a}</td>
                <td>{b}</td>
                <td>{c}</td>
                <td>
                  <DemoBadge />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </section>
  );
}
function ReportsPage({ onExport, onPrint }) {
  return (
    <section className="secondary-page">
      <div className="secondary-heading">
        <div>
          <span>ANALYSIS & REPORTS</span>
          <h2>분석 결과 및 보고서</h2>
          <p>완성된 화면과 예시 결과를 검토 가능한 형태로 저장합니다.</p>
        </div>
        <DemoBadge />
      </div>
      <div className="report-grid">
        <article className="surface report-card">
          <FileChartColumn size={34} strokeWidth={1.3} />
          <div>
            <span>SCREEN REPORT</span>
            <h3>대시보드 화면 보고서</h3>
            <p>현재 화면을 인쇄하거나 브라우저에서 PDF로 저장합니다.</p>
          </div>
          <button onClick={onPrint}>
            인쇄 / PDF 저장 <ArrowUpRight size={14} />
          </button>
        </article>
        <article className="surface report-card">
          <Database size={34} strokeWidth={1.3} />
          <div>
            <span>DEMO DATA</span>
            <h3>후보지역 비교 데이터</h3>
            <p>
              예시 후보지역과 현재 가중치로 계산한 DEMO 점수를 CSV 파일로
              저장합니다.
            </p>
          </div>
          <button onClick={onExport}>
            DEMO CSV 저장 <ArrowDownToLine size={14} />
          </button>
        </article>
      </div>
    </section>
  );
}
