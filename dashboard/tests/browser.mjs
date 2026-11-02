import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { deriveDemo, rankAtWeight } from "../src/demoModel.js";
const origin = process.env.DASHBOARD_URL || "http://127.0.0.1:5180";
const artifacts = fileURLToPath(new URL("../docs/", import.meta.url));
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const page = await browser.newPage({
  viewport: { width: 1536, height: 1024 },
  deviceScaleFactor: 1,
});
page.setDefaultTimeout(10000);
let count = 0;
const errors = [],
  external = [],
  failed = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("request", (r) => {
  if (
    /^https?:/.test(r.url()) &&
    new URL(r.url()).origin !== new URL(origin).origin
  )
    external.push(r.url());
});
page.on("response", (r) => {
  if (r.status() >= 400) failed.push(r.url());
});
const pass = (n) => {
  count++;
  console.log("PASS " + n);
};
const screenshot = async (name) => {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: artifacts + name,
    fullPage: true,
    animations: "disabled",
  });
};
async function consistent(weight) {
  const d = deriveDemo(weight);
  const vals = await page.locator(".kpi-value").allTextContents();
  assert.ok(vals[2].includes(d.highest));
  assert.ok(vals[3].includes(d.average));
  assert.ok(vals[4].includes(d.stability));
  const rows = await page.locator(".comparison-table tbody tr").all();
  assert.ok(rows.length >= 5 && rows.length <= 6);
  for (let i = 0; i < rows.length; i++) {
    assert.equal(
      await rows[i].getAttribute("data-candidate-id"),
      d.candidates[i].id,
    );
    assert.equal(
      await rows[i].locator("td").last().innerText(),
      d.candidates[i].value,
    );
  }
  return d;
}
try {
  await page.goto(origin, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  assert.equal(await page.locator(".kpi-card").count(), 5);
  assert.equal(await page.locator(".kpi-card>.demo-badge").count(), 5);
  assert.equal(await page.getByRole("checkbox").count(), 6);
  await consistent(60);
  assert.ok(
    await page
      .locator(".settings-actions")
      .evaluate(
        (el) =>
          el.getBoundingClientRect().bottom <=
          el.closest(".settings-panel").getBoundingClientRect().bottom,
      ),
  );
  assert.ok(
    await page
      .locator(".candidate-tab-panel")
      .evaluate((el) => el.scrollHeight <= el.clientHeight + 1),
  );
  await screenshot("dashboard-1536.png");
  await page.setViewportSize({ width: 1440, height: 900 });
  await screenshot("dashboard-1440.png");
  await page.screenshot({
    path: artifacts + "dashboard-1440-viewport.png",
    fullPage: false,
    animations: "disabled",
  });
  pass("1440×900 dashboard, labelled DEMO, eight consistent candidates");
  await page
    .getByRole("slider", { name: "Mobility 가중치", exact: true })
    .fill("30");
  assert.equal(
    await page
      .getByRole("slider", { name: "Spatial 가중치", exact: true })
      .inputValue(),
    "70",
  );
  const d30 = await consistent(30);
  assert.equal(d30.candidates[0].id, "TA-002");
  await page
    .getByRole("slider", { name: "Spatial 가중치", exact: true })
    .fill("20");
  await consistent(80);
  assert.equal(
    await page
      .getByRole("slider", { name: "Mobility 가중치", exact: true })
      .inputValue(),
    "80",
  );
  await page
    .locator(".preset-grid button")
    .filter({ hasText: "기존 기준" })
    .click();
  await consistent(60);
  pass("sliders and presets reconcile V, sorting, aggregates, 100% sum");
  await page
    .getByRole("button", { name: "공덕역 후보지 선택", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  assert.equal(
    await page.locator(".candidate-name-row h3").innerText(),
    "공덕역 일대",
  );
  assert.equal(
    await page
      .locator(".comparison-table .selected-row")
      .getAttribute("data-candidate-id"),
    "TA-002",
  );
  assert.equal(
    await page.getByTestId("detail-integrated").innerText(),
    deriveDemo(60).candidates.find((c) => c.id === "TA-002").value,
  );
  await page
    .locator(".comparison-table")
    .getByRole("button", { name: "망원역", exact: true })
    .click();
  assert.equal(await page.locator("#candidate-select").inputValue(), "TA-003");
  pass("map, detail and comparison selection share state");
  for (const name of ["이동특성", "공간특성", "안정성", "개요"]) {
    await page.getByRole("tab", { name, exact: true }).click();
    assert.equal(
      await page
        .getByRole("tab", { name, exact: true })
        .getAttribute("aria-selected"),
      "true",
    );
    assert.equal(await page.getByRole("tabpanel").count(), 1);
  }
  await page.getByRole("tab", { name: "안정성", exact: true }).click();
  assert.equal(await page.locator(".weight-rank-grid>div").count(), 4);
  assert.ok(
    (await page.getByRole("tabpanel").innerText()).includes("재표본추출"),
  );
  await page.getByRole("tab", { name: "개요", exact: true }).click();
  pass("detail overview, movement, spatial and stability tabs");
  for (const [name, layer] of [
    ["차량 이동경로", "vehicle"],
    ["인구 통행구간", "population"],
    ["밀크런 경로", "milk"],
    ["POI/상권", "poi"],
  ]) {
    await page.getByRole("tab", { name, exact: true }).click();
    assert.ok((await page.locator(`[data-layer="${layer}"]`).count()) > 0);
  }
  await page
    .getByRole("checkbox", { name: "POI · 상권", exact: true })
    .uncheck();
  assert.equal(await page.locator('[data-layer="poi"]').count(), 0);
  await page.getByRole("tab", { name: "위치가치 히트맵", exact: true }).click();
  await page.getByRole("checkbox", { name: "후보지역", exact: true }).uncheck();
  assert.equal(
    await page.getByRole("button", { name: /후보지 선택$/ }).count(),
    0,
  );
  await page.getByRole("checkbox", { name: "후보지역", exact: true }).check();
  pass("five map modes activate real SVG layers; checkboxes hide them");
  const transform = await page
    .locator(".map-canvas>g")
    .getAttribute("transform");
  await page.getByRole("button", { name: "지도 확대", exact: true }).click();
  assert.notEqual(
    await page.locator(".map-canvas>g").getAttribute("transform"),
    transform,
  );
  await page
    .getByRole("button", { name: "지도 중심 복원", exact: true })
    .click();
  assert.equal(
    await page.locator(".map-canvas>g").getAttribute("transform"),
    transform,
  );
  await page
    .getByRole("button", { name: "지도 전체화면", exact: true })
    .click();
  assert.equal(await page.locator(".map-expanded").count(), 1);
  await page.keyboard.press("Escape");
  assert.equal(await page.locator(".map-expanded").count(), 0);
  pass("map zoom/reset/fullscreen/Escape");
  await page
    .getByRole("button", { name: "가중치 40%의 후보지 순위 보기", exact: true })
    .focus();
  const tip = page.getByRole("status", {
    name: "가중치별 순위 상세",
    exact: true,
  });
  assert.ok((await tip.innerText()).includes("40%"));
  const expected = rankAtWeight("TA-001", 40);
  assert.ok((await tip.innerText()).includes(expected + "위"));
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "홍대입구역 순위 강조", exact: true })
    .click();
  await page
    .getByRole("slider", { name: "Mobility 가중치", exact: true })
    .fill("50");
  const selectedPoints = await page
    .locator('.rank-chart polyline[stroke-width="2.6"]')
    .getAttribute("points");
  const currentX = Number(
    await page.locator(".current-weight-line").getAttribute("x1"),
  );
  const expectedY = await page
    .locator('.rank-chart text[x="19"]')
    .evaluateAll(
      (nodes, rank) =>
        Number(
          nodes
            .find((n) => n.textContent === String(rank))
            .previousElementSibling.getAttribute("y1"),
        ),
      rankAtWeight("TA-001", 50),
    );
  assert.ok(
    selectedPoints.split(" ").some((p) => {
      const [x, y] = p.split(",").map(Number);
      return Math.abs(x - currentX) < 0.01 && Math.abs(y - expectedY) < 0.01;
    }),
  );
  await page
    .getByRole("slider", { name: "Mobility 가중치", exact: true })
    .fill("60");
  assert.equal(await page.locator("#candidate-select").inputValue(), "TA-001");
  pass("rank graph keyboard tooltip and linked series selection");
  await page
    .getByRole("combobox", { name: "분석지역", exact: true })
    .selectOption("공덕 권역");
  await page
    .getByRole("combobox", { name: "기준연도", exact: true })
    .selectOption("2025년");
  await page
    .getByRole("combobox", { name: "분석기간", exact: true })
    .selectOption("주말");
  await page
    .getByRole("combobox", { name: "분석 시나리오", exact: true })
    .selectOption("도심 순환 시나리오");
  await page
    .getByRole("button", { name: "분석 미리보기", exact: true })
    .click();
  await page
    .getByRole("button", { name: "미리보기 적용됨", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "DEMO 설정 초기화", exact: true })
    .click();
  assert.equal(
    await page
      .getByRole("combobox", { name: "분석지역", exact: true })
      .inputValue(),
    "서울특별시 마포구",
  );
  await consistent(60);
  pass("conditions and complete DEMO reset");
  await page
    .getByRole("button", { name: "시나리오 비교", exact: true })
    .click();
  assert.equal(await page.locator(".scenario-card").count(), 3);
  await page
    .locator(".scenario-card")
    .filter({
      has: page.getByRole("heading", { name: "공간 중심", exact: true }),
    })
    .getByRole("button")
    .click();
  await consistent(30);
  await page.getByRole("button", { name: "데이터 관리", exact: true }).click();
  assert.equal(await page.locator(".data-table tbody tr").count(), 5);
  await page
    .getByRole("button", { name: "분석 결과 및 보고서", exact: true })
    .click();
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "DEMO CSV 저장", exact: true })
    .click();
  const file = await download;
  const csv = await readFile(await file.path(), "utf8");
  assert.ok(csv.includes(deriveDemo(30).highest));
  assert.ok(csv.includes("DEMO"));
  pass("secondary screens and current-weight CSV export");
  await page
    .getByRole("button", { name: "분석 대시보드", exact: true })
    .click();
  await page.getByRole("button", { name: "분석 가이드", exact: false }).click();
  assert.equal(await page.getByRole("dialog").count(), 1);
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "View-T + Spatial", exact: false })
    .click();
  assert.ok((await page.getByRole("dialog").innerText()).includes("Bootstrap"));
  await page.getByRole("button", { name: "닫기", exact: true }).click();
  pass("guide and data source dialogs");
  await page.reload({ waitUntil: "networkidle" });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await screenshot("dashboard-1920.png");
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  await screenshot("dashboard-mobile.png");
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  await page.getByRole("button", { name: "메뉴 열기", exact: true }).click();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "데이터 관리", exact: true })
    .click();
  assert.equal(await page.locator(".sidebar.mobile-open").count(), 0);
  pass("1920×1080/mobile layout and mobile navigation");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.reload({ waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.emulateMedia({ media: "print" });
  await page.pdf({
    path: artifacts + "dashboard-report-demo.pdf",
    preferCSSPageSize: true,
    printBackground: true,
  });
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  assert.deepEqual(failed, []);
  pass("PDF output; no runtime errors, external APIs or missing assets");
  console.log(`\n${count} browser verification groups passed.`);
} catch (e) {
  await page.screenshot({
    path: "/tmp/atlas-upgrade-failure.png",
    fullPage: true,
  });
  throw e;
} finally {
  await browser.close();
}
