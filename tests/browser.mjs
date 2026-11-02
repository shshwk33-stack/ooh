import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const page = await browser.newPage({
  viewport: { width: 1512, height: 1150 },
  deviceScaleFactor: 1,
});
let errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
await page.locator(".research-pin").first().waitFor();
await page.waitForTimeout(800);
await page.screenshot({ path: "/tmp/research-desktop.png", fullPage: true });
assert.equal(await page.locator(".kpi.text-value").count(), 0);
assert.ok(
  (await page.locator(".kpi .text-value").textContent()).includes("홍대입구역"),
);
await page.getByRole("slider", { name: "이동 가중치" }).fill("0");
assert.ok(
  (await page.locator(".kpi .text-value").textContent()).includes("공덕역"),
);
assert.equal(
  await page.locator(".contribution-bar>i").first().getAttribute("style"),
  "width: 0%;",
);
await page.getByRole("button", { name: "현재 시나리오 저장" }).click();
await page
  .getByRole("button", { name: "저장된 시나리오", exact: true })
  .click();
assert.equal(await page.locator(".saved-row").count(), 1);
await page.reload();
await page
  .getByRole("button", { name: "저장된 시나리오", exact: true })
  .click();
assert.equal(await page.locator(".saved-row").count(), 1);
await page.getByRole("button", { name: "불러오기", exact: true }).click();
assert.equal(
  await page.getByRole("slider", { name: "이동 가중치" }).inputValue(),
  "0",
);
await page.getByRole("combobox", { name: "분석 지역" }).selectOption("망원동");
assert.equal(await page.locator(".model-table tbody tr").count(), 1);
assert.ok(
  (await page.locator(".stability-mini").textContent()).includes("21/21"),
);
await page.getByRole("button", { name: "조건 초기화" }).click();
await page.getByRole("switch", { name: "도로 교통활동" }).click();
assert.equal(
  await page
    .getByRole("switch", { name: "도로 교통활동" })
    .getAttribute("aria-checked"),
  "false",
);
await page.getByRole("switch", { name: "도로 교통활동" }).click();
await page.getByRole("button", { name: "지도 확대", exact: true }).click();
await page.getByRole("button", { name: "지도 중심 복원" }).click();
await page.getByRole("button", { name: "지도 전체화면" }).click();
assert.equal(await page.locator(".full-map").count(), 1);
await page.keyboard.press("Escape");
assert.equal(await page.locator(".full-map").count(), 0);
await page
  .getByRole("combobox", { name: "비교 후보지 선택" })
  .selectOption("MP-018");
assert.equal(
  await page.locator(".candidate-heading h3").textContent(),
  "공덕역",
);
await page.getByRole("button", { name: "선정 안정성", exact: true }).click();
assert.equal(await page.locator(".stability-dots>span").count(), 21);
await page.getByRole("button", { name: "기초 지표", exact: true }).click();
assert.ok(
  (await page.locator(".record-body").textContent()).includes("41,200"),
);
await page.getByRole("button", { name: "점수 구성", exact: true }).click();
const download = page.waitForEvent("download");
await page.getByRole("button", { name: "분석 결과 내보내기" }).click();
assert.ok((await download).suggestedFilename().endsWith(".csv"));
await page
  .getByRole("button", { name: "모델 비교·민감도", exact: true })
  .click();
assert.equal(await page.locator(".sensitivity-table tbody tr").count(), 8);
await page.getByRole("button", { name: "통합 공간 분석", exact: true }).click();
const valid = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "Uploaded road", traffic: 2000 },
      geometry: {
        type: "LineString",
        coordinates: [
          [126.92, 37.55],
          [126.93, 37.56],
        ],
      },
    },
  ],
};
await page
  .getByLabel("도로 GeoJSON 파일")
  .setInputFiles({
    name: "roads.geojson",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(valid)),
  });
await page.locator(".imported-file").waitFor();
assert.equal(await page.locator(".model-table tbody tr").count(), 8);
await page.getByRole("button", { name: "업로드 도로 제거" }).click();
await page.getByRole("button", { name: "데이터 출처", exact: true }).click();
assert.ok(
  (await page.getByRole("dialog").textContent()).includes("KOSTAT 2013"),
);
await page.keyboard.press("Escape");
assert.equal(await page.getByRole("dialog").count(), 0);
await page.getByRole("button", { name: "조건 초기화" }).click();
await page.waitForTimeout(3700);
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: "/tmp/research-mobile.png", fullPage: true });
assert.ok(
  await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  ),
);
assert.deepEqual(errors, []);
console.log(
  "Passed: score decomposition, baseline ranking, sensitivity, filters, persistence, GIS layers/zoom/fullscreen, GeoJSON import, CSV, sources dialog, mobile overflow; no runtime errors.",
);
await browser.close();
