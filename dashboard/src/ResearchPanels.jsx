import React, { useState } from "react";
import { CalendarDays, Check, ChevronRight, CircleCheck, Database, Download, ExternalLink, FileCheck2, Fingerprint, Layers3, MapPin, Navigation, Route, Truck } from "lucide-react";
import "./ResearchPanels.css";
import { exportResearchCsv } from "./researchModel";

const number = (value, maximumFractionDigits = 0) => Number(value || 0).toLocaleString("ko-KR", { maximumFractionDigits });
const km2 = (area) => number(Number(area || 0) / 1e6, 3);
const shortHash = (value) => value ? `${value.slice(0, 12)}…${value.slice(-6)}` : "—";
const kindLabel = (kind) => kind === "SYNTHETIC" ? "합성 운행자료" : "공개 경계자료";

function Badge({ children, type = "public" }) {
  return <span className={`research-kind ${type}`}>{children}</span>;
}
function Title({ children, action }) {
  return <div className="research-panel-title"><h2>{children}</h2>{action}</div>;
}
function saveFile(filename, body, type) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function exportUnits(summary, data) {
  saveFile("TRANSIT_ATLAS_행정동_합성GPS집계.csv", exportResearchCsv(summary.filters, data), "text/csv;charset=utf-8");
}

export function ResearchKpis({ summary, data }) {
  const k = summary.kpis;
  const passed = Object.values(data.quality).filter((q) => q.status === "passed").length;
  const items = [
    { label: "공간 분석 단위", value: k.unitCount, unit: "개 동", note: "마포구 실제 행정경계 · 2013", icon: Layers3, tag: "공개 경계" },
    { label: "선택 조건 GPS 기록", value: k.positionCount, unit: "개", note: "좌표별 공간결합 · 합성 입력", icon: Navigation, tag: "SYNTHETIC", synthetic: true },
    { label: "합성 운행 차량", value: k.vehicleCount, unit: "대", note: "현재 차량·날짜·시간 조건", icon: Truck, tag: "SYNTHETIC", synthetic: true },
    { label: "합성 운행일", value: k.dayCount, unit: "일", note: "가상 날짜 · 실제 관측기간 아님", icon: CalendarDays, tag: "SYNTHETIC", synthetic: true },
    { label: "입력 자료 검증", value: `${passed} / 3`, unit: "", note: "스키마·좌표·무결성 확인", icon: FileCheck2, tag: "검증 통과", accent: true },
  ];
  return <section className="kpi-grid research-kpis" aria-label="연결된 자료 요약">{items.map((item) => <article className={`kpi-card ${item.accent ? "kpi-accent" : ""}`} key={item.label}>
    <div className="kpi-icon"><item.icon size={28} strokeWidth={1.5} /></div>
    <div className="kpi-copy"><h2>{item.label}</h2><div className="kpi-value" data-testid={item.label === "선택 조건 GPS 기록" ? "research-gps-count" : undefined}>{typeof item.value === "number" ? number(item.value) : item.value}<small>{item.unit}</small></div><p>{item.note}</p></div>
    <Badge type={item.synthetic ? "synthetic" : "public"}>{item.tag}</Badge>
  </article>)}</section>;
}

function Metric({ label, value, note }) {
  return <div className="research-metric"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>;
}

export function ResearchDetail({ selected, summary, data }) {
  const [tab, setTab] = useState("overview");
  const unit = selected || summary.selectedUnit || summary.units[0];
  const points = summary.positions.filter((position) => position.dongCode === unit.code);
  const byDay = data.gps.days.map((day) => ({ day, count: points.filter((point) => point.day === day).length }));
  const maxDay = Math.max(1, ...byDay.map((day) => day.count));
  return <section className="surface research-detail" aria-label="선택 행정동 상세">
    <Title><MapPin size={16} /> 선택 행정동 상세</Title>
    <div className="research-detail-body">
      <div className="research-unit-heading"><span className="research-unit-pin"><MapPin size={18} /></span><div><h3 data-testid="research-selected-name">{unit.name}</h3><p>서울특별시 마포구</p></div><Badge>실제 경계</Badge></div>
      <div className="research-detail-tabs" role="tablist" aria-label="행정동 상세 탭">{[["overview", "공간정보"], ["activity", "합성 GPS"], ["source", "자료 출처"]].map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
      <div className="research-detail-content" role="tabpanel">
        {tab === "overview" && <>
          <div className="research-area-main"><span>행정동 형상 면적</span><strong>{km2(unit.areaM2)}<small>km²</small></strong><p>2013년 단순화 경계의 파생값</p></div>
          <dl className="research-detail-list"><div><dt>행정구역 코드</dt><dd>{unit.code}</dd></div><div><dt>경계 기준연도</dt><dd>2013년</dd></div><div><dt>형상 둘레</dt><dd>{number(unit.perimeterM / 1000, 2)} km</dd></div><div><dt>연산 좌표계</dt><dd>EPSG:5179</dd></div><div><dt>표시 좌표계</dt><dd>EPSG:4326</dd></div></dl>
          <h4 className="research-section-label">현재 조건의 합성 GPS</h4><div className="research-mini-metrics"><Metric label="GPS 기록" value={number(unit.sampleCount)} /><Metric label="차량" value={number(unit.vehicleCount)} /><Metric label="운행일" value={number(unit.dayCount)} /></div>
          <div className="research-scope-note"><CircleCheck size={15} /><p>실제 경계에 GPS 좌표를 공간결합했습니다. 기록 수는 합성 좌표 개수이며 방문 횟수나 광고 노출량을 뜻하지 않습니다.</p></div>
        </>}
        {tab === "activity" && <>
          <div className="research-activity-heading"><h4>일자별 GPS 기록</h4><Badge type="synthetic">SYNTHETIC</Badge></div>
          <div className="research-day-bars">{byDay.map((item) => <div key={item.day}><span>{item.day.slice(5).replace("-", ".")}</span><div><i style={{ width: `${item.count / maxDay * 100}%` }} /></div><b>{item.count}</b></div>)}</div>
          <div className="research-mini-metrics"><Metric label="기록 수" value={number(unit.sampleCount)} /><Metric label="구성 비율" value={`${number(unit.sampleShare * 100, 1)}%`} /><Metric label="차량 수" value={number(unit.vehicleCount)} /></div>
          <p className="research-detail-caption">날짜·차량·시간 필터가 지도와 이 집계에 동일하게 적용됩니다. 좌표가 없는 행정동은 0으로 표시합니다.</p>
          <div className="research-unavailable"><Route size={17} /><div><b>운행행태 분석 연계 전</b><span>정차·방문 이벤트와 실제 도로 매칭은 수행하지 않았습니다.</span></div></div>
        </>}
        {tab === "source" && <>
          <div className="research-source-block"><Badge>PUBLIC_AGGREGATE</Badge><h4>KOSTAT 2013 행정경계</h4><p>공개 미러의 원문 해시를 확인한 실제 지리 형상입니다. 현행 법정 경계·공식 면적 통계와 구분합니다.</p><a href={data.source.url} target="_blank" rel="noreferrer">원문 자료 <ExternalLink size={12} /></a></div>
          <div className="research-source-block"><Badge type="synthetic">SYNTHETIC</Badge><h4>GPS 입력 검증 시나리오</h4><p>Seed 42 · 차량 2대 · 가상 3일. 실제 도로를 따라 생성하거나 실측한 배송차량 경로가 아닙니다.</p></div>
          <p className="research-detail-caption">CRS는 경위도 입력 계약으로 명시했습니다. 미러의 Apache-2.0 선언과 원기관 이용조건 확인 여부는 자료 관리에서 구분합니다.</p>
        </>}
      </div>
      <div className="research-model-state"><span>위치가치 M · S · V</span><b>원천 지표 연계 전</b></div>
    </div>
  </section>;
}

export function ResearchAnalysisPanels({ data, summary, onSelect, selectedCode }) {
  const units = summary.units;
  const quality = data.quality;
  const maxCount = Math.max(1, ...units.map((unit) => unit.sampleCount));
  const missing = Object.values(quality.gps.missing_required || {}).reduce((sum, value) => sum + value, 0);
  const checks = [
    ["자치구 형상 유효성", `${quality.district.topology_valid_count} / ${quality.district.feature_count}`],
    ["행정동 형상 유효성", `${quality.dongs.topology_valid_count} / ${quality.dongs.feature_count}`],
    ["필수 GPS 값 누락", `${number(missing)}건`],
    ["좌표 왕복오차", `${Number(quality.dongs.max_roundtrip_error_deg).toExponential(2)}°`],
    ["원본·결과 무결성", "SHA-256 확인"],
  ];
  return <section className="research-analysis-grid" aria-label="연결 자료 분석 결과">
    <section className="surface research-lower-panel"><Title action={<button className="research-icon-button" onClick={() => exportUnits(summary, data)} aria-label="행정동 합성 GPS 집계 CSV 저장"><Download size={14} /></button>}>행정동별 GPS 공간집계</Title>
      <div className="research-table-scroll"><table className="research-table"><thead><tr><th>행정동</th><th>면적(km²)</th><th>합성 기록</th><th>차량</th></tr></thead><tbody>{units.map((unit) => <tr key={unit.code} data-research-unit={unit.code} className={selectedCode === unit.code ? "selected" : ""} onClick={() => onSelect?.(unit.code)}><th><button onClick={(e) => { e.stopPropagation(); onSelect?.(unit.code); }} aria-pressed={selectedCode === unit.code}>{unit.name}</button></th><td>{km2(unit.areaM2)}</td><td><span className="research-count-cell"><i style={{ width: `${unit.sampleCount / maxCount * 100}%` }} /><b>{unit.sampleCount}</b></span></td><td>{unit.vehicleCount}</td></tr>)}</tbody></table></div>
      <p className="research-lower-caption">16개 실제 경계 · 선택 조건의 합성 GPS 포인트 수</p>
    </section>
    <section className="surface research-lower-panel"><Title action={<Badge>검증 통과</Badge>}>입력 자료 품질 점검</Title>
      <div className="research-checks">{checks.map(([label, value]) => <div key={label}><span><Check size={13} />{label}</span><b>{value}</b></div>)}</div><p className="research-lower-caption">자동 보정·임의 대체 없음 · 원천 경고는 자료 관리에 기록</p>
    </section>
    <section className="surface research-lower-panel"><Title action={<button className="research-icon-button" onClick={() => saveFile("TRANSIT_ATLAS_실행명세.json", JSON.stringify(data.manifests, null, 2), "application/json")} aria-label="처리 실행 명세 JSON 저장"><Download size={14} /></button>}>처리 이력과 재현성</Title>
      <div className="research-run-list">{[["district", "마포구 경계", "PUBLIC_AGGREGATE"], ["dongs", "마포 16개 행정동", "PUBLIC_AGGREGATE"], ["gps", "합성 GPS 입력", "SYNTHETIC"]].map(([key, label, kind]) => <div key={key}><div><Fingerprint size={14} /><b>{label}</b><Badge type={kind === "SYNTHETIC" ? "synthetic" : "public"}>{kind === "SYNTHETIC" ? "합성" : "공개"}</Badge></div><code title={data.manifests[key].run_id}>{data.manifests[key].run_id.slice(0, 24)}</code></div>)}</div>
      <p className="research-lower-caption">원본 해시 · 처리 조건 · 출력 해시 · 자료 분류 저장</p>
    </section>
  </section>;
}

export function ResearchDataPage({ data }) {
  const sources = [
    { key: "district", label: "서울 자치구 경계", scope: "25개 구 검증 → 마포구 1개", kind: "PUBLIC_AGGREGATE" },
    { key: "dongs", label: "서울 행정동 경계", scope: "423개 동 검증 → 마포구 16개", kind: "PUBLIC_AGGREGATE" },
    { key: "gps", label: "GPS 입력 검증자료", scope: "합성 차량 2대 · 가상 3일 · 72행", kind: "SYNTHETIC" },
  ];
  return <div className="research-data-page">
    <div className="research-page-intro"><div><span>DATA CATALOG</span><h2>연결된 자료와 처리 이력</h2><p>공개 공간 형상과 합성 운행자료의 출처·해상도·처리 조건을 각각 관리합니다.</p></div><button className="research-download-button" onClick={() => saveFile("TRANSIT_ATLAS_자료명세.json", JSON.stringify({ source: data.source, quality: data.quality, manifests: data.manifests }, null, 2), "application/json")}><Download size={15} /> 자료 명세 저장</button></div>
    <div className="research-catalog-grid">{sources.map((source) => {
      const manifest = data.manifests[source.key], quality = data.quality[source.key];
      return <article className="surface research-catalog-card" key={source.key}><div className="research-catalog-heading"><Database size={23} /><Badge type={source.kind === "SYNTHETIC" ? "synthetic" : "public"}>{source.kind}</Badge></div><h3>{source.label}</h3><p>{source.scope}</p><dl><div><dt>자료 성격</dt><dd>{kindLabel(source.kind)}</dd></div><div><dt>기준시점</dt><dd>{source.kind === "SYNTHETIC" ? "2024.05.01–03 · 가상 날짜" : "2013년 경계"}</dd></div><div><dt>좌표계</dt><dd>EPSG:4326 → EPSG:5179</dd></div><div><dt>검증 상태</dt><dd className="research-text-green"><CircleCheck size={13} /> {quality.status === "passed" ? "통과" : "확인 필요"}</dd></div><div><dt>원본 SHA-256</dt><dd><code title={manifest.source?.sha256 || manifest.input_sha256}>{shortHash(manifest.source?.sha256 || manifest.input_sha256)}</code></dd></div></dl></article>;
    })}</div>
    <section className="surface research-quality-page-panel"><Title>품질 검증과 자료 적용 범위</Title><div className="research-quality-page-grid"><div><h3>확인한 항목</h3>{["원본·메타데이터 해시와 파생 결과 연결", "필수속성·기준연도·중복 코드·형상 위상", "명시적 좌표계 계약·변환·왕복오차", "GPS 좌표·시간대·중복·충돌·이상 속도", "합성 행 표기와 원천 분류의 일치"].map((line) => <p key={line}><Check size={14} />{line}</p>)}</div><div><h3>해석에 필요한 메모</h3><p>공개 경계는 단순화된 2013년 형상입니다. 공식 면적 통계나 최신 법정 경계가 아닙니다.</p><p>원문에 CRS 선언이 없어 경위도 입력 계약을 명시했습니다. 미러 README의 Apache-2.0 선언과 원기관 약관 확인 여부는 별개입니다.</p><p>GPS는 입력 검증용 합성자료입니다. 배송차량 실측 GPS, View-T 교통량, 인구·POI와 M/S/V·Bootstrap 계산은 아직 연결되지 않았습니다.</p></div></div></section>
    <section className="surface research-source-reference"><div><Layers3 size={19} /><div><h3>KOSTAT 2013 · 공개 미러</h3><p>고정 버전 <code>{data.source.upstreamCommit}</code></p></div></div><a href={data.source.url} target="_blank" rel="noreferrer">원문 확인 <ExternalLink size={14} /></a></section>
  </div>;
}
