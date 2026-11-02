import React, { useState } from "react";
import {
  ArrowUpRight,
  Check,
  ChartNoAxesCombined,
  ChevronDown,
  CircleCheck,
  MapPin,
  MapPinned,
  Route,
  Truck,
  Users,
} from "lucide-react";
import { DemoBadge, PanelTitle } from "./AnalysisPanels";
import { rankAtWeight } from "./demoModel";

const hourly = {
  "TA-001": [8, 19, 24, 22, 18, 9],
  "TA-002": [11, 24, 18, 16, 22, 9],
  "TA-003": [6, 18, 22, 26, 19, 9],
  "TA-004": [7, 14, 20, 24, 24, 11],
  "TA-005": [10, 20, 23, 21, 18, 8],
  "TA-006": [9, 22, 24, 20, 17, 8],
  "TA-007": [12, 25, 19, 18, 18, 8],
  "TA-008": [6, 15, 23, 25, 21, 10],
};
const repeats = {
  "TA-001": 0.89,
  "TA-002": 0.84,
  "TA-003": 0.92,
  "TA-004": 0.78,
  "TA-005": 0.86,
  "TA-006": 0.73,
  "TA-007": 0.71,
  "TA-008": 0.69,
};
function Indicator({ icon: Icon, label, value, unit }) {
  return (
    <div>
      <dt>
        <Icon size={14} />
        {label}
      </dt>
      <dd>
        <b>{value}</b>
        <small>{unit}</small>
      </dd>
    </div>
  );
}
function ScoreBar({ label, value, color }) {
  return (
    <div className="score-row">
      <span>{label}</span>
      <div>
        <i
          style={{
            width: Math.min(100, Number(value) * 100) + "%",
            background: color,
          }}
        />
      </div>
      <b>{Number(value).toFixed(3)}</b>
    </div>
  );
}
export default function CandidateDetail({
  candidate: c,
  candidates,
  mobility,
  onSelect,
}) {
  const [tab, setTab] = useState("overview");
  const totalContribution = c.mobilityContribution + c.spatialContribution;
  const mobilityShare =
    totalContribution > 0
      ? (c.mobilityContribution / totalContribution) * 100
      : 0;
  const dominant =
    c.mobilityContribution >= c.spatialContribution
      ? { label: "이동 특성", value: c.mobilityContribution }
      : { label: "공간 특성", value: c.spatialContribution };
  const conciseReason = `M ${mobility} : S ${100 - mobility} 기준, ${dominant.label} 기여 ${dominant.value.toFixed(3)}가 우세합니다. 통합 점수 ${c.value}로 종합 ${c.rank}위입니다.`;
  return (
    <section className="surface candidate-panel">
      <PanelTitle>
        <MapPin size={14} /> 선택 후보지 상세 분석
      </PanelTitle>
      <div className="candidate-panel-body">
        <div className="candidate-name-row">
          <span className="candidate-rank">{c.rank}</span>
          <div>
            <h3>{c.name}</h3>
          </div>
          <span className="candidate-position">종합 {c.rank}위</span>
        </div>
        <div className="detail-tabs" role="tablist" aria-label="후보지 상세 탭">
          {[
            ["overview", "개요"],
            ["movement", "이동특성"],
            ["spatial", "공간특성"],
            ["stability", "안정성"],
          ].map(([id, label]) => (
            <button
              key={id}
              id={`detail-tab-${id}`}
              role="tab"
              aria-selected={tab === id}
              aria-controls={`detail-panel-${id}`}
              tabIndex={tab === id ? 0 : -1}
              onClick={() => setTab(id)}
              onKeyDown={(e) => {
                if (["ArrowRight", "ArrowLeft"].includes(e.key)) {
                  e.preventDefault();
                  const ids = ["overview", "movement", "spatial", "stability"];
                  const next =
                    ids[
                      (ids.indexOf(id) + (e.key === "ArrowRight" ? 1 : 3)) % 4
                    ];
                  setTab(next);
                  requestAnimationFrame(() =>
                    document.getElementById("detail-tab-" + next)?.focus(),
                  );
                }
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div
          className="candidate-tab-panel"
          id={`detail-panel-${tab}`}
          role="tabpanel"
          aria-labelledby={`detail-tab-${tab}`}
        >
          {tab === "overview" ? (
            <>
              <div
                className="reference-score-grid"
                aria-label="DEMO 후보지 점수"
              >
                <div className="integrated">
                  <span>
                    위치가치 점수 <small>(V)</small>
                  </span>
                  <strong data-testid="detail-integrated">{c.value}</strong>
                </div>
                <div className="mobility">
                  <span>
                    Mobility <small>(M)</small>
                  </span>
                  <strong>{c.mobility}</strong>
                </div>
                <div className="spatial">
                  <span>
                    Spatial <small>(S)</small>
                  </span>
                  <strong>{c.spatial}</strong>
                </div>
              </div>
              <div className="reference-stack-heading">
                <h4>점수 구성</h4>
                <small>
                  가중치 {mobility}:{100 - mobility}
                </small>
              </div>
              <div
                className="reference-stack"
                role="img"
                aria-label={`DEMO 점수 기여: 이동 ${c.mobilityContribution.toFixed(3)}, 공간 ${c.spatialContribution.toFixed(3)}`}
              >
                <i
                  className="mobility-segment"
                  style={{ width: `${mobilityShare}%` }}
                />
                <i
                  className="spatial-segment"
                  style={{
                    width: `${totalContribution > 0 ? 100 - mobilityShare : 0}%`,
                  }}
                />
              </div>
              <div className="reference-stack-labels">
                <span>
                  <i className="mobility-marker" />
                  이동특성 ({mobility}%) <b>{c.mobility}</b>
                </span>
                <span>
                  <i className="spatial-marker" />
                  공간특성 ({100 - mobility}%) <b>{c.spatial}</b>
                </span>
              </div>
              <h4 className="detail-section-title">
                주요 분석 지표 <DemoBadge />
              </h4>
              <dl className="detail-indicators">
                <Indicator
                  icon={Truck}
                  label="차량 통행량"
                  value={c.visits}
                  unit="대/일"
                />
                <Indicator
                  icon={Users}
                  label="인구 통행량"
                  value={c.population}
                  unit="명/일"
                />
                <Indicator
                  icon={MapPinned}
                  label="주변 POI 수"
                  value={c.poi}
                  unit="개"
                />
                <Indicator
                  icon={ChartNoAxesCombined}
                  label="상권 활동지수"
                  value={c.activity}
                  unit="정규화"
                />
              </dl>
              <div className="selection-reason">
                <h4>
                  <CircleCheck size={14} /> 선정 이유 <DemoBadge />
                </h4>
                <p>{conciseReason}</p>
              </div>
            </>
          ) : tab === "movement" ? (
            <>
              <div className="tab-heading">
                <span>MOBILITY PROFILE</span>
                <b>
                  {c.mobility}
                  <small> / 1.000</small>
                </b>
              </div>
              <dl className="detail-indicators">
                <Indicator
                  icon={Truck}
                  label="차량 통행량"
                  value={c.visits}
                  unit="대/일"
                />
                <Indicator
                  icon={Route}
                  label="경로 반복성"
                  value={repeats[c.id].toFixed(2)}
                  unit="지수"
                />
              </dl>
              <h4 className="detail-section-title">
                시간대별 이동량 <small>DEMO · 비중 %</small>
              </h4>
              <div
                className="hourly-chart"
                role="img"
                aria-label={`${c.short} 시간대별 이동량 비중 예시`}
              >
                {(hourly[c.id] || hourly["TA-001"]).map((v, i) => (
                  <div key={i}>
                    <span>{v}%</span>
                    <i style={{ height: v * 3 + "px" }} />
                    <small>{["06", "09", "12", "15", "18", "21"][i]}시</small>
                  </div>
                ))}
              </div>
              <div className="detail-note">
                방문·반복 이동의 UI 예시입니다. 실제 GPS 궤적을 분석한 결과가
                아닙니다.
              </div>
            </>
          ) : tab === "spatial" ? (
            <>
              <div className="tab-heading">
                <span>SPATIAL PROFILE</span>
                <b>
                  {c.spatial}
                  <small> / 1.000</small>
                </b>
              </div>
              <dl className="detail-indicators">
                <Indicator
                  icon={Users}
                  label="인구 통행량"
                  value={c.population}
                  unit="명/일"
                />
                <Indicator
                  icon={MapPinned}
                  label="POI 밀집도"
                  value={c.poi}
                  unit="개"
                />
                <Indicator
                  icon={MapPin}
                  label="상권 활동지수"
                  value={c.activity}
                  unit="지수"
                />
              </dl>
              <h4 className="detail-section-title">공간 점수 표현</h4>
              <ScoreBar label="Spatial" value={c.spatial} color="#c6a259" />
              <div className="detail-note">
                Static은 공간 점수 S만 사용하는 비교 기준입니다. 인구·시설
                지표는 별도 예시이며 S를 재산출하는 연구식은 연결하지
                않았습니다.
              </div>
            </>
          ) : (
            <>
              <h4 className="detail-section-title">
                가중치별 순위 <small>DEMO 가중합</small>
              </h4>
              <div className="weight-rank-grid">
                {[30, 50, 60, 80].map((w) => (
                  <div key={w}>
                    <span>
                      {w}:{100 - w}
                    </span>
                    <b>
                      {rankAtWeight(c.id, w)}
                      <small>위</small>
                    </b>
                  </div>
                ))}
              </div>
              <h4 className="detail-section-title">
                Bootstrap 결과 예시 <DemoBadge />
              </h4>
              <dl className="detail-indicators">
                <Indicator
                  icon={Route}
                  label="평균 순위"
                  value={c.mean}
                  unit="위"
                />
                <Indicator
                  icon={Check}
                  label="Top 5 선정확률"
                  value={(Number(c.top5) * 100).toFixed(1)}
                  unit="%"
                />
                <Indicator
                  icon={ArrowUpRight}
                  label="순위 변동성"
                  value={c.sigma}
                  unit="σ"
                />
              </dl>
              <div className="detail-note">
                별도로 정의된 DEMO 결과입니다. Bootstrap 재표본추출은 실행하지
                않습니다.
              </div>
            </>
          )}
        </div>
        <div className="candidate-select-row">
          <label htmlFor="candidate-select">후보지 탐색</label>
          <div>
            <select
              id="candidate-select"
              aria-label="선택 후보지"
              value={c.id}
              onChange={(e) => onSelect(e.target.value)}
            >
              {candidates.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.rank}. {d.short}
                </option>
              ))}
            </select>
            <ChevronDown size={11} />
          </div>
        </div>
      </div>
    </section>
  );
}
