import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  ChartColumnIncreasing,
  Check,
  ChevronDown,
  CircleCheck,
  Clock3,
  Database,
  FileChartColumn,
  FileJson,
  Info,
  Layers3,
  Link2,
  Map,
  MapPin,
  Menu,
  Play,
  RotateCcw,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Truck,
  Upload,
  X,
} from "lucide-react";
import { DEFAULT_WORKSPACE } from "./workspaceData";
import {
  deriveWorkspace,
  exportWorkspaceCsv,
  exportWorkspaceJson,
} from "./workspaceModel";
import {
  validateWorkspace,
  parseWorkspaceJson,
  importCandidatesCsv,
  exportCandidatesTemplate,
  fetchWorkspace,
} from "./workspaceContract";
import UnifiedMap from "./UnifiedMap";
import {
  UnifiedKpis,
  UnifiedDetail,
  UnifiedAnalysisPanels,
} from "./UnifiedPanels";

const NAV = [
  ["dashboard", "분석 대시보드", ChartColumnIncreasing],
  ["spatial", "공간 분석 (GIS)", Map],
  ["scenarios", "시나리오 비교", Layers3],
  ["sensitivity", "민감도 및 강건성 분석", Activity],
  ["data", "데이터 관리", Database],
  ["reports", "분석 결과 및 보고서", FileChartColumn],
];
const PRESETS = [
  ["공간 중심", 30],
  ["균형", 50],
  ["기존 기준", 60],
  ["이동 중심", 80],
];
const TYPES = {
  OBSERVED_GPS: "실측 위치기록",
  PUBLIC_AGGREGATE: "공개 자료",
  ESTIMATED: "추정 자료",
  SYNTHETIC: "시나리오 자료",
  DERIVED: "파생 결과",
};
const DEFAULT_FILTERS = { vehicle: "all", day: "all", time: "all" };
const MAX_BYTES = 10 * 1024 * 1024;
const format = (n, d = 3) => (n == null ? "—" : Number(n).toFixed(d));
const localDate = (period) => new Intl.DateTimeFormat("en-CA", {timeZone: period.timezone, year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date(period.start));
function save(name, body, type = "application/json;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function FieldSelect({ label, value, options, onChange, icon: Icon }) {
  return (
    <label className="uw-field">
      <span>{label}</span>
      <div>
        {Icon && <Icon size={14} />}
        <select
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {options.map(([id, text]) => (
            <option value={id} key={id}>
              {text}
            </option>
          ))}
        </select>
        <ChevronDown size={11} />
      </div>
    </label>
  );
}
function Sidebar({
  active,
  onNavigate,
  dataset,
  mobileOpen,
  setMobileOpen,
  onGuide,
  connection,
}) {
  const candidatesSource = dataset.meta.sources.find((s) =>
    dataset.candidates.some((c) => c.sourceId === s.id),
  );
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
          <Layers3 size={33} strokeWidth={1.65} />
        </div>
        <div>
          <b>TRANSIT ATLAS</b>
          <span>From Movement to Meaning.</span>
        </div>
      </a>
      <div className="sidebar-nav">
        <div className="sidebar-eyebrow">분석 워크스페이스</div>
        <nav aria-label="주요 메뉴">
          {NAV.map(([id, label, Icon]) => (
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
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </div>
      <section className="sidebar-research">
        <h2>
          <Settings2 size={14} />
          연구지역 정보
        </h2>
        <dl>
          <div>
            <MapPin size={13} />
            <dt>연구지역</dt>
            <dd>{dataset.meta.region}</dd>
          </div>
          <div>
            <CalendarDays size={13} />
            <dt>분석기간</dt>
            <dd>{localDate(dataset.meta.period)}</dd>
          </div>
          <div>
            <Clock3 size={13} />
            <dt>기준시간</dt>
            <dd>{dataset.meta.period.timezone}</dd>
          </div>
          <div>
            <Layers3 size={13} />
            <dt>공간 분석 단위</dt>
            <dd>{dataset.geometry.units.features.length}개 행정동</dd>
          </div>
          <div>
            <Database size={13} />
            <dt>입력 구성</dt>
            <dd>{TYPES[candidatesSource?.kind] || "자료 명세 확인"}</dd>
          </div>
        </dl>
      </section>
      <section className="sidebar-system">
        <h2>
          <Activity size={14} />
          시스템 상태
        </h2>
        <div>
          <span className="status-light" />
          <span>입력 자료</span>
          <b>검증 완료</b>
        </div>
        <div>
          <span className="status-light" />
          <span>분석 계산</span>
          <b>정상</b>
        </div>
        <div>
          <span
            className={
              "status-light " + (connection === "API" ? "uw-live-light" : "")
            }
          />
          <span>연결 방식</span>
          <b>{connection}</b>
        </div>
      </section>
      <div className="sidebar-bottom">
        <button onClick={onGuide}>
          <BookOpen size={16} />
          분석 가이드
          <ArrowUpRight size={12} />
        </button>
      </div>
    </aside>
  );
}
function Settings({
  dataset,
  analysis,
  mobility,
  setMobility,
  filters,
  setFilters,
  onReset,
  onSave,
}) {
  const gps = dataset.gps.positions;
  const vehicles = analysis.availableVehicles || analysis.vehicles || [];
  const days = analysis.availableDays || analysis.days || [];
  return (
    <section className="surface uw-settings">
      <div className="uw-panel-heading">
        <h2>분석 설정</h2>
        <SlidersHorizontal size={16} />
      </div>
      <div className="uw-settings-body">
        <div className="uw-setting-title">
          <b>가중치 설정</b>
          <span>V = αM + (1−α)S</span>
        </div>
        <div className="uw-weight">
          <label htmlFor="uw-mobility">
            Mobility <span>(이동특성)</span>
            <strong>
              {mobility}
              <small>%</small>
            </strong>
          </label>
          <input
            id="uw-mobility"
            aria-label="Mobility 가중치"
            type="range"
            min="0"
            max="100"
            value={mobility}
            style={{ "--progress": mobility + "%" }}
            onChange={(e) => setMobility(Number(e.target.value))}
          />
        </div>
        <div className="uw-weight spatial">
          <label htmlFor="uw-spatial">
            Spatial <span>(공간특성)</span>
            <strong>
              {100 - mobility}
              <small>%</small>
            </strong>
          </label>
          <input
            id="uw-spatial"
            aria-label="Spatial 가중치"
            type="range"
            min="0"
            max="100"
            value={100 - mobility}
            style={{ "--progress": 100 - mobility + "%" }}
            onChange={(e) => setMobility(100 - Number(e.target.value))}
          />
        </div>
        <div className="uw-settings-divider" />
        <h3>가중치 프리셋</h3>
        <div className="uw-preset-grid">
          {PRESETS.map(([name, w]) => (
            <button
              key={w}
              className={w === mobility ? "active" : ""}
              aria-pressed={w === mobility}
              aria-label={`${name} ${w} : ${100 - w}`}
              onClick={() => setMobility(w)}
            >
              <span>{name}</span>
              <small>
                {w} : {100 - w}
              </small>
            </button>
          ))}
        </div>
        <div className="uw-settings-divider" />
        <h3>운행 조건</h3>
        <FieldSelect
          label="시간대"
          icon={Clock3}
          value={filters.time}
          options={[
            ["all", "전체 시간대"],
            ["morning", "오전 (00:00–12:00)"],
            ["afternoon", "오후 (12:00–24:00)"],
          ]}
          onChange={(v) => setFilters((f) => ({ ...f, time: v }))}
        />
        <details className="uw-gps-details">
          <summary>
            <span>차량·운행일 선택</span>
            <ChevronDown size={11} />
          </summary>
          <FieldSelect
            label="운행 차량"
            icon={Truck}
            value={filters.vehicle}
            options={[
              ["all", "전체 차량"],
              ...vehicles.map((v) => [v, v.replace("SYNTH-VEH-", "차량 ")]),
            ]}
            onChange={(v) => setFilters((f) => ({ ...f, vehicle: v }))}
          />
          <FieldSelect
            label="운행일"
            icon={CalendarDays}
            value={filters.day}
            options={[["all", "전체 운행일"], ...days.map((d) => [d, d])]}
            onChange={(v) => setFilters((f) => ({ ...f, day: v }))}
          />
        </details>
        <p className="uw-condition-note">
          운행 조건은 GPS 조회에 적용됩니다. 후보지 M/S는 입력된 평가기간을
          기준으로 합니다.
        </p>
      </div>
      <div className="uw-settings-actions">
        <button className="uw-primary" onClick={onSave}>
          <Check size={14} />
          조건 저장
        </button>
        <button
          className="uw-reset"
          aria-label="분석 조건 초기화"
          onClick={onReset}
        >
          <RotateCcw size={15} />
        </button>
      </div>
    </section>
  );
}
function DataPage({
  dataset,
  connection,
  apiUrl,
  setApiUrl,
  connecting,
  error,
  onConnect,
  onImportJson,
  onImportCsv,
  onReset,
  onExport,
}) {
  const json = useRef(),
    csv = useRef();
  return (
    <section className="uw-secondary">
      <div className="uw-page-heading">
        <div>
          <span>DATA CONNECTIONS</span>
          <h2>데이터 연결 관리</h2>
          <p>
            분석 JSON·후보지역 CSV·API 응답은 공통 입력 규격으로 검증한 후
            반영됩니다.
          </p>
        </div>
        <button onClick={onExport}>
          <ArrowDownToLine size={14} />
          현재 데이터 저장
        </button>
      </div>
      <div className="uw-connection-grid">
        <article className="surface uw-connection-card">
          <div className="uw-connection-icon">
            <Upload size={22} />
          </div>
          <h3>파일 가져오기</h3>
          <p>
            전체 공간·후보지 자료는 JSON으로, 후보지 좌표와 M/S는 CSV로
            연결합니다.
          </p>
          <input
            ref={json}
            data-testid="import-json"
            aria-label="분석 JSON 가져오기"
            type="file"
            accept=".json,.geojson,application/json"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) await onImportJson(file);
              e.target.value = "";
            }}
            hidden
          />
          <input
            ref={csv}
            data-testid="import-csv"
            aria-label="후보지역 CSV 가져오기"
            type="file"
            accept=".csv,text/csv"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) await onImportCsv(file);
              e.target.value = "";
            }}
            hidden
          />
          <div className="uw-file-buttons">
            <button onClick={() => json.current.click()}>
              <FileJson size={14} />
              분석 JSON 가져오기
            </button>
            <button onClick={() => csv.current.click()}>
              <Upload size={14} />
              후보지역 CSV 가져오기
            </button>
          </div>
          <button
            className="uw-template-link"
            onClick={() =>
              save(
                "TRANSIT_ATLAS_CANDIDATES_TEMPLATE.csv",
                exportCandidatesTemplate(),
                "text/csv;charset=utf-8",
              )
            }
          >
            입력 양식 CSV 저장 <ArrowDownToLine size={12} />
          </button>
        </article>
        <article className="surface uw-connection-card">
          <div className="uw-connection-icon">
            <Link2 size={22} />
          </div>
          <h3>분석 API 연결</h3>
          <p>
            분석 서버에서 제공하는 통합 데이터 JSON 주소를 입력하세요. 응답을
            검증한 뒤 현재 자료를 교체합니다.
          </p>
          <label className="uw-api-label" htmlFor="uw-api-url">
            API 주소
          </label>
          <div className="uw-api-input">
            <input
              id="uw-api-url"
              aria-label="분석 API 주소"
              data-testid="api-url"
              type="url"
              value={apiUrl}
              placeholder="https://your-server/api/workspace"
              onChange={(e) => setApiUrl(e.target.value)}
              autoComplete="off"
              spellCheck="false"
            />
            <button
              disabled={connecting || !apiUrl.trim()}
              data-testid="api-connect"
              onClick={onConnect}
            >
              {connecting ? "연결 중…" : "API 연결"}
            </button>
          </div>
          <p className="uw-api-note">
            연결 오류나 입력 규격 불일치 시 기존 자료를 유지합니다.
          </p>
        </article>
      </div>
      {error && (
        <div role="alert" data-testid="workspace-error" className="uw-error">
          <Info size={16} />
          <span>{error}</span>
        </div>
      )}
      <section className="surface uw-catalog">
        <div className="uw-panel-heading">
          <h3>현재 연결 자료</h3>
          <span className="uw-connection-state">
            <CircleCheck size={12} />
            {connection}
          </span>
        </div>
        <div className="uw-dataset-heading">
          <div>
            <b data-testid="dataset-name">{dataset.meta.name}</b>
            <p>
              {dataset.meta.id} · v{dataset.meta.version}
            </p>
          </div>
          <button onClick={onReset}>
            기본 입력 복원 <RotateCcw size={12} />
          </button>
        </div>
        <div className="uw-table-scroll">
          <table>
            <thead>
              <tr>
                <th>자료</th>
                <th>출처 분류</th>
                <th>기준연도</th>
                <th>단위·정의</th>
                <th>출처</th>
              </tr>
            </thead>
            <tbody>
              {dataset.meta.sources.map((s) => (
                <tr key={s.id}>
                  <th>{s.label}</th>
                  <td>
                    <span
                      className={
                        "uw-type-tag " +
                        (s.kind === "SYNTHETIC" ? "scenario" : "")
                      }
                    >
                      {TYPES[s.kind]}
                    </span>
                    <small className="uw-source-code">{s.kind}</small>
                  </td>
                  <td>{s.year || "—"}</td>
                  <td>{s.unit || "자료 명세 기준"}</td>
                  <td>
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noreferrer">
                        원문 <ArrowUpRight size={11} />
                      </a>
                    ) : (
                      s.description || "입력 메타데이터"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="uw-data-counts">
          <span>
            후보지역 <b>{dataset.candidates.length}</b>
          </span>
          <span>
            행정경계 <b>{dataset.geometry.units.features.length}</b>
          </span>
          <span>
            도로 링크 <b>{dataset.geometry.roads.features.length || "—"}</b>
          </span>
          <span>
            GPS 기록 <b>{dataset.gps.positions.length}</b>
          </span>
          <span>
            Bootstrap <b>{dataset.bootstrap ? "결과 포함" : "결과 미연결"}</b>
          </span>
        </div>
      </section>
      <div className="surface uw-contract-card">
        <ShieldCheck size={21} />
        <div>
          <b>연결 규격 2.0</b>
          <p>
            후보지 좌표·M/S, 공간 레이어, GPS, 출처를 하나의 데이터 형식으로
            관리합니다. 값이 없는 지표는 빈 상태로 보존하며, 원천 분류와
            분석기간은 내보내기에도 함께 저장합니다.
          </p>
        </div>
        <button
          onClick={() =>
            save("TRANSIT_ATLAS_WORKSPACE.json", exportWorkspaceJson(dataset))
          }
        >
          JSON 구조 저장 <ArrowDownToLine size={13} />
        </button>
      </div>
    </section>
  );
}
function ScenarioPage({
  dataset,
  mobility,
  onApply,
  saved,
  onRestore,
  onRemove,
}) {
  return (
    <section className="uw-secondary">
      <div className="uw-page-heading">
        <div>
          <span>SCENARIO COMPARISON</span>
          <h2>가중치별 후보지역 비교</h2>
          <p>
            동일한 입력을 유지하고 이동·공간 비중에 따른 선정 결과를 비교합니다.
          </p>
        </div>
      </div>
      <div className="uw-scenario-grid">
        {PRESETS.map(([name, w]) => {
          const a = deriveWorkspace(dataset, {
            mobility: w,
            ...DEFAULT_FILTERS,
          });
          const top = a.candidates[0];
          return (
            <article
              className={
                "surface uw-scenario-card " + (w === mobility ? "active" : "")
              }
              key={w}
            >
              <span className="uw-scenario-caption">MOBILITY : SPATIAL</span>
              <h3>{name}</h3>
              <div className="uw-scenario-weight">
                {w}
                <i>:</i>
                {100 - w}
              </div>
              <div className="uw-scenario-result">
                <span>최상위 후보</span>
                <b>{top?.short || top?.name || "평가 가능 후보 없음"}</b>
                <strong>{format(top?.score)}</strong>
              </div>
              <button onClick={() => onApply(w)}>
                {w === mobility ? "현재 가중치" : "이 가중치 적용"}
                <ArrowRight size={14} />
              </button>
            </article>
          );
        })}
      </div>
      <section className="surface uw-saved-scenarios">
        <div className="uw-panel-heading">
          <h3>저장한 분석 조건</h3>
          <span>{saved.length}개</span>
        </div>
        {saved.length ? (
          <div>
            {saved.map((s) => (
              <article key={s.id}>
                <div>
                  <b>{s.name}</b>
                  <small>
                    {s.datasetName} · M {s.mobility}% / S {100 - s.mobility}%
                  </small>
                </div>
                <button onClick={() => onRestore(s)}>복원</button>
                <button
                  className="uw-delete-scenario"
                  aria-label={`${s.name} 삭제`}
                  onClick={() => onRemove(s.id)}
                >
                  <X size={13} />
                </button>
              </article>
            ))}
          </div>
        ) : (
          <p className="uw-empty-inline">
            분석 설정의 ‘조건 저장’에서 현재 가중치와 조회 조건을 보관할 수
            있습니다.
          </p>
        )}
      </section>
    </section>
  );
}
function ReportPage({
  dataset,
  analysis,
  mobility,
  filters,
  onCsv,
  onJson,
  onSession,
}) {
  return (
    <section className="uw-secondary">
      <div className="uw-page-heading">
        <div>
          <span>ANALYSIS REPORTS</span>
          <h2>분석 결과 내보내기</h2>
          <p>
            후보지 결과·가중치·출처·분석기간을 한 묶음으로 내보낼 수 있습니다.
          </p>
        </div>
      </div>
      <div className="uw-report-grid">
        {[
          [
            "후보지역 평가 결과",
            "현재 가중치의 M/S/V·순위와 자료 출처를 CSV로 저장합니다.",
            "후보지역 CSV 저장",
            onCsv,
          ],
          [
            "전체 데이터",
            "후보지·공간 레이어·GPS·출처가 포함된 재연결용 JSON입니다.",
            "전체 데이터 JSON 저장",
            onJson,
          ],
          [
            "현재 분석 세션",
            "선택 조건·가중치·현재 결과와 데이터 버전을 보존합니다.",
            "현재 분석 세션 저장",
            onSession,
          ],
        ].map(([name, desc, label, fn]) => (
          <article className="surface uw-report-card" key={name}>
            <FileChartColumn size={25} />
            <h3>{name}</h3>
            <p>{desc}</p>
            <button onClick={fn}>
              {label}
              <ArrowDownToLine size={14} />
            </button>
          </article>
        ))}
      </div>
      <section className="surface uw-report-summary">
        <div>
          <span>분석 입력</span>
          <b>{dataset.meta.name}</b>
        </div>
        <div>
          <span>현재 가중치</span>
          <b>
            M {mobility}% · S {100 - mobility}%
          </b>
        </div>
        <div>
          <span>최고 점수</span>
          <b>{format(analysis.highest)}</b>
        </div>
        <div>
          <span>조회 GPS</span>
          <b>{analysis.filteredPositions.length}개</b>
        </div>
        <button onClick={() => window.print()}>화면 인쇄 / PDF 저장</button>
      </section>
    </section>
  );
}
function readSaved() {
  try {
    const value = JSON.parse(
      localStorage.getItem("transit-atlas-scenarios-v2") || "[]",
    );
    return Array.isArray(value)
      ? value
          .filter(
            (s) =>
              s &&
              typeof s.id === "string" &&
              Number.isFinite(s.mobility) &&
              s.mobility >= 0 &&
              s.mobility <= 100 &&
              typeof s.datasetId === "string" &&
              typeof s.datasetVersion === "string" &&
              typeof s.datasetName === "string" &&
              typeof s.name === "string" &&
              s.filters &&
              ["vehicle", "day", "time"].every(key => typeof s.filters[key] === "string"),
          )
          .slice(0, 20)
      : [];
  } catch {
    return [];
  }
}

export default function UnifiedWorkspace() {
  const [dataset, setDataset] = useState(DEFAULT_WORKSPACE),
    [active, setActive] = useState("dashboard"),
    [mobility, setMobility] = useState(60),
    [filters, setFilters] = useState({ ...DEFAULT_FILTERS }),
    [selectedId, setSelectedId] = useState(DEFAULT_WORKSPACE.candidates[0]?.id),
    [selectedUnit, setSelectedUnit] = useState(null),
    [mode, setMode] = useState("integrated"),
    [mobileOpen, setMobileOpen] = useState(false),
    [modal, setModal] = useState(null),
    [apiUrl, setApiUrl] = useState(""),
    [connecting, setConnecting] = useState(false),
    [connection, setConnection] = useState("내장 자료"),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [exportOpen, setExportOpen] = useState(false),
    [saved, setSaved] = useState(readSaved);
  const analysis = useMemo(
    () => deriveWorkspace(dataset, { mobility, ...filters, selectedId }),
    [dataset, mobility, filters, selectedId],
  );
  const candidate =
    analysis.candidates.find((c) => c.id === selectedId) ||
    analysis.candidates[0] ||
    null;
  const controller = useRef(null),
    requestId = useRef(0),
    modalRef = useRef(null),
    mapRef = useRef(null),
    lowerRef = useRef(null);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 3200);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    try {
      localStorage.setItem("transit-atlas-scenarios-v2", JSON.stringify(saved));
    } catch {}
  }, [saved]);
  useEffect(() => {
    if (!modal) return;
    const before = document.activeElement;
    const el = modalRef.current;
    el?.querySelector("button")?.focus();
    const key = (e) => {
      if (e.key === "Escape") setModal(null);
      if (e.key === "Tab") {
        const nodes = el?.querySelectorAll("button,a,input,select");
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
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      before?.focus();
    };
  }, [modal]);
  useEffect(() => {
    if (!exportOpen) return;
    const close = (e) => {
      if (
        (e.type === "keydown" && e.key === "Escape") ||
        (e.type === "click" && !e.target.closest(".uw-export-wrapper"))
      )
        setExportOpen(false);
    };
    document.addEventListener("click", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", close);
    };
  }, [exportOpen]);
  function navigate(id) {
    setActive(id);
    setMobileOpen(false);
    setExportOpen(false);
    if (id === "spatial")
      requestAnimationFrame(() =>
        mapRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }),
      );
    else if (id === "sensitivity")
      requestAnimationFrame(() =>
        lowerRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        }),
      );
    else window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function applyData(next, type) {
    validateWorkspace(next);
    setDataset(next);
    setSelectedId(next.candidates[0]?.id || null);
    setSelectedUnit(null);
    setFilters({ ...DEFAULT_FILTERS });
    setConnection(type);
    setError("");
    setToast("자료를 검증하고 전체 분석 화면에 반영했습니다.");
  }
  async function importFile(file, type) {
    const current = ++requestId.current;
    controller.current?.abort();
    setConnecting(false);
    try {
      if (file.size > MAX_BYTES)
        throw Error("10MB 이하의 파일을 연결할 수 있습니다.");
      const text = await file.text();
      const next =
        type === "json"
          ? parseWorkspaceJson(text)
          : importCandidatesCsv(text, dataset);
      if (current !== requestId.current) return;
      applyData(next, type === "json" ? "JSON 파일" : "CSV 파일");
    } catch (e) {
      if (current === requestId.current)
        setError(e.message || "파일을 읽지 못했습니다.");
    }
  }
  async function connectApi() {
    controller.current?.abort();
    const current = ++requestId.current;
    const abort = new AbortController();
    controller.current = abort;
    setConnecting(true);
    setError("");
    try {
      const next = await fetchWorkspace(apiUrl, { signal: abort.signal });
      if (current !== requestId.current) return;
      applyData(next, "API");
    } catch (e) {
      if (current === requestId.current)
        setError(
          e.name === "AbortError"
            ? "연결이 취소되었거나 응답 시간이 초과되었습니다."
            : e.message || "API 연결에 실패했습니다.",
        );
    } finally {
      if (current === requestId.current) setConnecting(false);
    }
  }
  function resetData() {
    requestId.current++;
    controller.current?.abort();
    setConnecting(false);
    applyData(DEFAULT_WORKSPACE, "내장 자료");
    setMobility(60);
    setMode("integrated");
  }
  function csv() {
    save(
      "TRANSIT_ATLAS_CANDIDATE_RESULTS.csv",
      exportWorkspaceCsv(dataset, { mobility, ...filters }),
      "text/csv;charset=utf-8",
    );
    setExportOpen(false);
    setToast("현재 후보지역 평가 결과를 저장했습니다.");
  }
  function json() {
    save("TRANSIT_ATLAS_WORKSPACE.json", exportWorkspaceJson(dataset));
    setExportOpen(false);
  }
  function session() {
    save(
      "TRANSIT_ATLAS_ANALYSIS_SESSION.json",
      JSON.stringify(
        {
          schemaVersion: "2.0",
          dataset: {
            id: dataset.meta.id,
            version: dataset.meta.version,
            sources: dataset.meta.sources,
            period: dataset.meta.period,
          },
          parameters: {
            mobility,
            spatial: 100 - mobility,
            ...filters,
            selectedId,
            mode,
          },
          candidates: analysis.candidates,
          bootstrap: analysis.bootstrap || null,
        },
        null,
        2,
      ),
    );
    setExportOpen(false);
  }
  function saveScenario() {
    const now = new Date();
    const s = {
      id: crypto.randomUUID?.() || String(Date.now()),
      name: `분석 조건 ${saved.length + 1}`,
      datasetId: dataset.meta.id,
      datasetVersion: dataset.meta.version,
      datasetName: dataset.meta.name,
      mobility,
      filters: { ...filters },
      selectedId,
      createdAt: now.toISOString(),
    };
    setSaved((old) => [s, ...old].slice(0, 20));
    setToast("현재 가중치와 조회 조건을 저장했습니다.");
  }
  function restoreScenario(s) {
    if (
      s.datasetId !== dataset.meta.id ||
      s.datasetVersion !== dataset.meta.version
    ) {
      setError(
        "현재 연결 자료와 다른 버전의 분석 조건입니다. 해당 데이터 파일을 먼저 연결하세요.",
      );
      navigate("data");
      return;
    }
    if ((s.filters.vehicle !== "all" && !analysis.availableVehicles.includes(s.filters.vehicle)) ||
        (s.filters.day !== "all" && !analysis.availableDays.includes(s.filters.day)) ||
        !["all", "morning", "afternoon"].includes(s.filters.time)) {
      setError("저장된 조회 조건이 현재 연결 자료에 없습니다. 현재 자료에서 조건을 다시 지정하세요.");
      navigate("data");
      return;
    }
    setMobility(s.mobility);
    setFilters({ ...DEFAULT_FILTERS, ...s.filters });
    setSelectedId(
      dataset.candidates.some((c) => c.id === s.selectedId)
        ? s.selectedId
        : dataset.candidates[0]?.id,
    );
    navigate("dashboard");
    setToast("저장한 분석 조건을 복원했습니다.");
  }
  const dashboard = ["dashboard", "spatial", "sensitivity"].includes(active);
  return (
    <div className="atlas-app unified-app" data-testid="unified-workspace">
      <Sidebar
        active={active}
        onNavigate={navigate}
        dataset={dataset}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
        onGuide={() => setModal("guide")}
        connection={connection}
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
            <span className="uw-header-chip">
              <MapPin size={14} />
              {dataset.meta.region}
            </span>
            <span className="uw-header-chip">
              <CalendarDays size={14} />
              {localDate(dataset.meta.period).slice(0, 4)}년
            </span>
            <button
              className="source-button"
              aria-label="데이터 연결 관리"
              onClick={() => navigate("data")}
            >
              <Layers3 size={14} />
              <span>데이터 연결 · {dataset.meta.sources.length}종</span>
              <ChevronDown size={10} />
            </button>
            <button
              className="header-info"
              aria-label="분석 안내"
              onClick={() => setModal("guide")}
            >
              <Info size={18} />
            </button>
          </div>
        </header>
        <main>
          <div className="uw-workspace-strip">
            <div>
              <span className="uw-ready-dot" />
              <b>{NAV.find((n) => n[0] === active)?.[1]}</b>
              <i />
              <span>{dataset.meta.name}</span>
            </div>
            <div className="uw-export-wrapper">
              <button
                className="export-toggle"
                aria-expanded={exportOpen}
                onClick={() => setExportOpen(!exportOpen)}
              >
                <ArrowDownToLine size={12} />
                내보내기
                <ChevronDown size={9} />
              </button>
              {exportOpen && (
                <div className="export-menu">
                  <button onClick={csv}>후보지역 CSV 저장</button>
                  <button onClick={json}>전체 데이터 JSON 저장</button>
                  <button onClick={session}>현재 분석 세션 저장</button>
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
          {dashboard ? (
            <>
              <UnifiedKpis dataset={dataset} analysis={analysis} />
              <section
                className={
                  "main-analysis-grid uw-main-grid " +
                  (active === "spatial" ? "uw-spatial-view" : "")
                }
                ref={mapRef}
              >
                <Settings
                  dataset={dataset}
                  analysis={analysis}
                  mobility={mobility}
                  setMobility={setMobility}
                  filters={filters}
                  setFilters={setFilters}
                  onReset={() => {
                    setMobility(60);
                    setFilters({ ...DEFAULT_FILTERS });
                    setMode("integrated");
                  }}
                  onSave={saveScenario}
                />
                <section className="surface uw-map-panel">
                  <div className="uw-panel-heading">
                    <h2>
                      GIS 공간 분석 <span>|</span>
                      <small>이동·공간 특성 및 위치가치</small>
                    </h2>
                    <button
                      aria-label="공간 분석 안내"
                      onClick={() => setModal("map")}
                    >
                      <Info size={14} />
                    </button>
                  </div>
                  <UnifiedMap
                    dataset={dataset}
                    analysis={analysis}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                    selectedUnit={selectedUnit}
                    onUnitSelect={setSelectedUnit}
                    mode={mode}
                    onModeChange={setMode}
                  />
                </section>
                <UnifiedDetail
                  dataset={dataset}
                  analysis={analysis}
                  candidate={candidate}
                  onSelect={setSelectedId}
                />
              </section>
              <div ref={lowerRef}>
                <UnifiedAnalysisPanels
                  dataset={dataset}
                  analysis={analysis}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  mobility={mobility}
                  onWeightChange={setMobility}
                />
              </div>
            </>
          ) : active === "scenarios" ? (
            <ScenarioPage
              dataset={dataset}
              mobility={mobility}
              saved={saved}
              onApply={(w) => {
                setMobility(w);
                navigate("dashboard");
              }}
              onRestore={restoreScenario}
              onRemove={(id) => setSaved((s) => s.filter((x) => x.id !== id))}
            />
          ) : active === "data" ? (
            <DataPage
              dataset={dataset}
              connection={connection}
              apiUrl={apiUrl}
              setApiUrl={setApiUrl}
              connecting={connecting}
              error={error}
              onConnect={connectApi}
              onImportJson={(f) => importFile(f, "json")}
              onImportCsv={(f) => importFile(f, "csv")}
              onReset={resetData}
              onExport={json}
            />
          ) : (
            <ReportPage
              dataset={dataset}
              analysis={analysis}
              mobility={mobility}
              filters={filters}
              onCsv={csv}
              onJson={json}
              onSession={session}
            />
          )}
          <footer className="app-footer uw-footer">
            <span>
              TRANSIT ATLAS <i />
              From Movement to Meaning.
            </span>
            <div>
              <span>
                자료 버전 {dataset.meta.version} ·{" "}
                {dataset.meta.period.timezone}
              </span>
              <button onClick={() => navigate("data")}>
                자료 출처·연결 관리 <ArrowUpRight size={10} />
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
            className="modal uw-modal"
            role="dialog"
            aria-modal="true"
            aria-label={modal === "map" ? "공간 분석 안내" : "분석 안내"}
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
            <span className="modal-eyebrow">
              TRANSIT ATLAS · ANALYTICS WORKSPACE
            </span>
            <h2>
              {modal === "map"
                ? "지도에서 분석 근거를 확인합니다."
                : "하나의 입력, 일관된 분석 결과."}
            </h2>
            <div className="uw-guide-list">
              <article>
                <b>01</b>
                <div>
                  <h3>가중치와 후보지역</h3>
                  <p>
                    이동·공간 가중치를 조절하면 점수, 순위, 지도와 선택 상세가
                    같은 결과를 표시합니다. 값이 없는 지표는 임의로 채우지
                    않습니다.
                  </p>
                </div>
              </article>
              <article>
                <b>02</b>
                <div>
                  <h3>실제 공간과 운행기록</h3>
                  <p>
                    행정경계·후보 좌표·GPS는 지리 좌표로 표시됩니다. 위치가치
                    색상은 행정동에 속한 후보 점수의 평균이며 광고 노출 밀도가
                    아닙니다.
                  </p>
                </div>
              </article>
              <article>
                <b>03</b>
                <div>
                  <h3>파일과 API 연결</h3>
                  <p>
                    데이터 관리에서 JSON·CSV를 가져오거나 분석 API를 연결하세요.
                    출처 분류와 기간을 검사한 뒤 전체 화면에 적용합니다.
                  </p>
                </div>
              </article>
              <article>
                <b>04</b>
                <div>
                  <h3>출처와 재현성</h3>
                  <p>
                    현재 내장 후보지 평가와 차량기록은 시나리오 자료, 행정경계는
                    2013년 공개자료입니다. Bootstrap은 검증된 결과가 연결된
                    경우에만 표시합니다.
                  </p>
                </div>
              </article>
            </div>
            <button
              className="uw-primary uw-guide-button"
              onClick={() => {
                setModal(null);
                navigate("data");
              }}
            >
              데이터 연결 관리
              <ArrowRight size={14} />
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
