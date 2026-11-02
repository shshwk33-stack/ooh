export const candidates = [
  {
    id: "MP-024",
    name: "홍대입구역",
    area: "서교동 · 양화로",
    x: 565,
    y: 320,
    mobility: 0.94,
    spatial: 0.78,
    visits: 142,
    dwell: 36,
    population: 32400,
  },
  {
    id: "MP-018",
    name: "공덕역",
    area: "공덕동 · 마포대로",
    x: 1030,
    y: 580,
    mobility: 0.78,
    spatial: 0.96,
    visits: 118,
    dwell: 28,
    population: 41200,
  },
  {
    id: "MP-041",
    name: "합정역",
    area: "합정동 · 양화로",
    x: 385,
    y: 465,
    mobility: 0.87,
    spatial: 0.72,
    visits: 126,
    dwell: 32,
    population: 28100,
  },
  {
    id: "MP-032",
    name: "상수역",
    area: "상수동 · 독막로",
    x: 570,
    y: 520,
    mobility: 0.73,
    spatial: 0.81,
    visits: 97,
    dwell: 24,
    population: 26500,
  },
  {
    id: "MP-009",
    name: "망원시장",
    area: "망원동 · 망원로",
    x: 295,
    y: 295,
    mobility: 0.82,
    spatial: 0.59,
    visits: 109,
    dwell: 41,
    population: 18700,
  },
  {
    id: "MP-056",
    name: "대흥역",
    area: "대흥동 · 대흥로",
    x: 865,
    y: 470,
    mobility: 0.62,
    spatial: 0.85,
    visits: 84,
    dwell: 22,
    population: 30900,
  },
  {
    id: "MP-063",
    name: "마포역",
    area: "도화동 · 마포대로",
    x: 975,
    y: 665,
    mobility: 0.66,
    spatial: 0.76,
    visits: 91,
    dwell: 26,
    population: 24300,
  },
  {
    id: "MP-015",
    name: "연남동 경의선숲길",
    area: "연남동 · 동교로",
    x: 625,
    y: 220,
    mobility: 0.58,
    spatial: 0.88,
    visits: 73,
    dwell: 38,
    population: 29600,
  },
];
export function rankCandidates(alpha = 60, time = "all", area = "all") {
  const factor = time === "morning" ? 0.91 : time === "evening" ? 1.06 : 1;
  return candidates
    .filter((c) => area === "all" || c.area.includes(area))
    .map((c) => ({
      ...c,
      score: Math.min(
        0.99,
        ((c.mobility * alpha) / 100 + c.spatial * (1 - alpha / 100)) * factor,
      ),
      visits: Math.round(c.visits * factor),
    }))
    .sort((a, b) => b.score - a.score);
}
export function toCSV(rows, alpha) {
  return (
    "\uFEFF후보지,지역,이동 점수,공간 점수,위치가치,이동 가중치\n" +
    rows
      .map((c) =>
        [
          c.name,
          c.area,
          c.mobility,
          c.spatial,
          c.score.toFixed(3),
          alpha + "%",
        ].join(","),
      )
      .join("\n")
  );
}
