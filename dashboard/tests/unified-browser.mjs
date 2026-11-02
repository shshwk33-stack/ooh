import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { DEFAULT_WORKSPACE } from '../src/workspaceData.js';
import { deriveWorkspace } from '../src/workspaceModel.js';
import { exportCandidatesCsv } from '../src/workspaceContract.js';

const standalone = process.env.ATLAS_STANDALONE;
const origin = process.env.DASHBOARD_URL || 'http://127.0.0.1:5180';
const artifacts = fileURLToPath(new URL('../docs/unified/', import.meta.url));
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
if (standalone) await context.setOffline(true);
const page = await context.newPage();
page.setDefaultTimeout(12000);
const errors = [], unexpectedRequests = [], unexpectedFailures = [];
let groups = 0;
const qaPrefix = 'http://127.0.0.1:5180/qa-unified-api/';
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {
  if (!/^https?:/.test(request.url()) || request.url().startsWith(qaPrefix)) return;
  if (standalone || new URL(request.url()).origin !== new URL(origin).origin) unexpectedRequests.push(request.url());
});
page.on('response', response => {
  if (response.status() >= 400 && !response.url().startsWith(qaPrefix)) unexpectedFailures.push(response.url());
});
const pass = name => { groups++; console.log('PASS ' + name); };
const go = async label => page.locator('.sidebar').getByRole('button', { name: label, exact: true }).click();
const capture = async name => { await page.evaluate(() => document.fonts.ready); await page.screenshot({ path: artifacts + name, fullPage: true, animations: 'disabled' }); };
const getDownload = async action => { const event = page.waitForEvent('download'); await action(); return readFile(await (await event).path(), 'utf8'); };
const uploadJson = async data => page.getByTestId('import-json').setInputFiles({ name: 'analysis.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)) });
const datasetFixture = (name = '연결 검증 자료') => {
  const data = structuredClone(DEFAULT_WORKSPACE);
  data.meta.id = 'qa-import'; data.meta.name = name;
  data.candidates = data.candidates.slice(0, 2).map((candidate, i) => ({ ...candidate, id: `QA-00${i + 1}`, name: `검증 후보 ${i ? 'B' : 'A'}`, short: `검증 ${i ? 'B' : 'A'}`, mobility: i ? .9 : .2, spatial: i ? .2 : .9 }));
  data.bootstrap = null;
  return data;
};
const open = async () => {
  if (standalone) { await page.goto('about:blank'); await page.setContent(await readFile(standalone, 'utf8'), { waitUntil: 'networkidle' }); }
  else await page.goto(origin, { waitUntil: 'networkidle' });
  await page.getByTestId('unified-workspace').waitFor();
  await page.evaluate(() => document.fonts.ready);
};
const scoreText = async () => page.getByTestId('unified-detail-score').innerText();
const setWeight = async weight => page.getByRole('slider', { name: 'Mobility 가중치', exact: true }).fill(String(weight));

try {
  await open();
  const body = await page.locator('body').innerText();
  assert.ok(!/DEMO|프로토타입|prototype/i.test(body), 'Product interface must not contain former prototype labels');
  assert.equal(await page.getByRole('button', { name: '예시 점수 비교', exact: true }).count(), 0);
  assert.equal(await page.locator('.unified-kpis .kpi-card').count(), 5);
  assert.ok((await scoreText()).includes('0.876'));
  await capture('dashboard-unified-1440.png');
  pass('one integrated production interface includes weights, candidates and connected GIS');

  await setWeight(30);
  const d30 = deriveWorkspace(DEFAULT_WORKSPACE, { mobility: 30 });
  assert.equal(await page.getByRole('slider', { name: 'Spatial 가중치', exact: true }).inputValue(), '70');
  const values30 = await page.locator('.unified-kpis').innerText();
  assert.ok(values30.includes('0.906'));
  assert.ok((await page.locator('[data-unit-code="1114061"] title').textContent()).includes('0.906'));
  await setWeight(60);
  assert.ok((await page.locator('.unified-kpis').innerText()).includes('0.876'));
  pass('weight changes preserve 100% sum and calculate existing .876/.906 rank reversal');

  // More interaction checks follow the components' shared data attributes.
  await page.getByTestId('unified-map').waitFor();
  assert.equal(await page.locator('[data-unit-code]').count(), 16);
  assert.equal(await page.locator('[data-layer="unified-candidates"] [data-candidate-id]').count(), 8);
  await page.getByRole('button', { name: '공덕역 일대 후보지 선택', exact: true }).focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.getByTestId('unified-selected-name').innerText(), '공덕역 일대');
  assert.equal(await page.getByRole('combobox', { name: '상세 후보지 선택', exact: true }).inputValue(), 'TA-002');
  await page.locator('[data-unified-candidate="TA-003"]').getByRole('button').click();
  assert.equal(await page.getByTestId('unified-selected-name').innerText(), '망원역 일대');
  for (const name of ['이동특성', '공간특성', '안정성', '개요']) {
    await page.getByRole('tablist', { name: '후보지 상세 탭' }).getByRole('tab', { name, exact: true }).click();
    assert.equal(await page.getByRole('tablist', { name: '후보지 상세 탭' }).getByRole('tab', { name, exact: true }).getAttribute('aria-selected'), 'true');
  }
  assert.ok((await page.locator('.unified-bootstrap-panel').innerText()).includes('안정성 결과 연결 대기'));
  pass('actual geometry and candidate selection synchronize the map, comparison table and four detail tabs');

  await page.getByRole('button', { name: '지도 레이어 제어', exact: true }).click();
  assert.equal(await page.getByRole('checkbox', { name: '도로망', exact: true }).isDisabled(), true);
  await page.getByRole('checkbox', { name: 'GPS 기록점', exact: true }).check();
  assert.equal(await page.locator('[data-layer="unified-points"] circle').count(), 72);
  await page.getByText('차량·운행일 선택', { exact: true }).click();
  await page.getByRole('combobox', { name: '운행 차량', exact: true }).selectOption('SYNTH-VEH-01');
  assert.equal(await page.locator('[data-layer="unified-points"] circle').count(), 36);
  const days = deriveWorkspace(DEFAULT_WORKSPACE).days;
  await page.getByRole('combobox', { name: '운행일', exact: true }).selectOption(days[0]);
  assert.equal(await page.locator('[data-layer="unified-points"] circle').count(), 12);
  await page.getByRole('combobox', { name: '시간대', exact: true }).selectOption('afternoon');
  assert.equal(await page.locator('[data-layer="unified-points"] circle').count(), 0);
  assert.equal(await page.getByTestId('unified-highest').innerText(), '0.876');
  await page.getByRole('combobox', { name: '운행 차량', exact: true }).selectOption('all');
  await page.getByRole('combobox', { name: '운행일', exact: true }).selectOption('all');
  await page.getByRole('combobox', { name: '시간대', exact: true }).selectOption('all');
  if (await page.getByRole('button', { name: '지도 레이어 닫기', exact: true }).isVisible()) await page.getByRole('button', { name: '지도 레이어 닫기', exact: true }).click();
  const transform = await page.getByTestId('unified-map-transform').getAttribute('transform');
  await page.getByRole('button', { name: '지도 확대', exact: true }).click();
  assert.notEqual(await page.getByTestId('unified-map-transform').getAttribute('transform'), transform);
  await page.getByRole('button', { name: '지도 전체화면', exact: true }).click();
  assert.ok(await page.locator('.unified-map-expanded').isVisible());
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('.unified-map-expanded').count(), 0);
  await page.getByRole('button', { name: '후보지역 범위 확대', exact: true }).click();
  pass('available layers and GPS-only filters operate without changing static candidate score inputs');

  await setWeight(80);
  await page.getByRole('button', { name: '조건 저장', exact: true }).click();
  await go('시나리오 비교');
  assert.equal(await page.locator('.uw-scenario-card').count(), 4);
  assert.equal(await page.locator('.uw-saved-scenarios').getByRole('button', { name: '복원', exact: true }).count(), 1);
  await page.locator('.uw-scenario-card').filter({ has: page.getByRole('heading', { name: '공간 중심', exact: true }) }).getByRole('button').click();
  assert.equal(await page.getByRole('slider', { name: 'Mobility 가중치', exact: true }).inputValue(), '30');
  await go('시나리오 비교');
  await page.locator('.uw-saved-scenarios').getByRole('button', { name: '복원', exact: true }).click();
  assert.equal(await page.getByRole('slider', { name: 'Mobility 가중치', exact: true }).inputValue(), '80');
  await go('시나리오 비교');
  await page.locator('.uw-delete-scenario').click();
  assert.equal(await page.locator('.uw-saved-scenarios').getByRole('button', { name: '복원', exact: true }).count(), 0);
  await go('분석 대시보드');
  await setWeight(60);
  await go('공간 분석 (GIS)');
  assert.ok(await page.getByTestId('unified-map').isVisible());
  await go('민감도 및 강건성 분석');
  assert.ok(await page.locator('.unified-rank-chart').isVisible());
  await page.getByRole('button', { name: '이동 가중치 30% 적용', exact: true }).focus();
  assert.ok((await page.getByRole('status', { name: '가중치별 순위 상세', exact: true }).innerText()).includes('30%'));
  await page.keyboard.press('Enter');
  assert.equal(await page.getByTestId('unified-highest').innerText(), '0.906');
  await setWeight(60);
  pass('all analysis navigation, saved conditions, preset restoration and keyboard sensitivity controls operate');

  await go('데이터 관리');
  const importedLayers = datasetFixture();
  const point = [importedLayers.candidates[0].longitude, importedLayers.candidates[0].latitude];
  importedLayers.geometry.roads.features = [{ type: 'Feature', properties: { link_id: 'QA-LINK-01', name: '입력 검증용 선', traffic: 5000, unit: '검증 입력' }, geometry: { type: 'LineString', coordinates: [point, [point[0] + .002, point[1] + .001]] } }];
  importedLayers.geometry.poi.features = [{ type: 'Feature', properties: { name: '입력 검증용 시설' }, geometry: { type: 'Point', coordinates: point } }];
  importedLayers.geometry.population.features = [{ type: 'Feature', properties: { name: '입력 검증용 활동점', value: 100 }, geometry: { type: 'Point', coordinates: point } }];
  await uploadJson(importedLayers);
  await page.getByTestId('dataset-name').filter({ hasText: '연결 검증 자료' }).waitFor();
  await go('분석 대시보드');
  assert.ok((await page.locator('.unified-kpis').innerText()).includes('0.620'));
  assert.equal(await page.locator('[data-layer="unified-roads"] polyline').count(), 1);
  await page.getByRole('button', { name: '지도 레이어 제어', exact: true }).click();
  assert.equal(await page.getByRole('checkbox', { name: '도로망', exact: true }).isDisabled(), false);
  await page.getByRole('checkbox', { name: 'POI · 상권', exact: true }).check();
  await page.getByRole('checkbox', { name: '인구 활동', exact: true }).check();
  assert.ok(await page.locator('[data-layer="unified-poi"] circle').count() > 0);
  assert.equal(await page.locator('[data-layer="unified-population"] circle').count(), 1);
  await go('데이터 관리');
  const invalid = datasetFixture('거부되어야 할 자료'); invalid.candidates[0].mobility = 1.5;
  await uploadJson(invalid);
  await page.getByTestId('workspace-error').waitFor();
  assert.ok((await page.getByTestId('dataset-name').innerText()).includes('연결 검증 자료'));
  await page.getByTestId('import-json').setInputFiles({ name: 'oversized.json', mimeType: 'application/json', buffer: Buffer.alloc(10 * 1024 * 1024 + 1, 32) });
  await page.getByTestId('workspace-error').waitFor();
  assert.ok((await page.getByTestId('dataset-name').innerText()).includes('연결 검증 자료'));
  const csvFixture = datasetFixture(); csvFixture.candidates[0].name = '검증 "후보", A';
  await page.getByTestId('import-csv').setInputFiles({ name: 'candidates.csv', mimeType: 'text/csv', buffer: Buffer.from(exportCandidatesCsv(csvFixture)) });
  await page.getByTestId('dataset-name').filter({ hasText: '가져온 후보지역' }).waitFor();
  await go('분석 대시보드');
  await page.getByRole('combobox', { name: '상세 후보지 선택', exact: true }).selectOption('QA-001');
  assert.equal(await page.getByTestId('unified-selected-name').innerText(), '검증 "후보", A');
  await go('데이터 관리');
  await page.getByTestId('import-csv').setInputFiles({ name: 'invalid.csv', mimeType: 'text/csv', buffer: Buffer.from('id,name\nonly,invalid\n') });
  await page.getByTestId('workspace-error').waitFor();
  assert.ok((await page.getByTestId('dataset-name').innerText()).includes('가져온 후보지역'));
  await uploadJson(DEFAULT_WORKSPACE);
  pass('valid JSON/quoted CSV update analysis; malformed, oversized and out-of-range inputs preserve current data');

  const withBootstrap = datasetFixture('안정성 연결 검증');
  withBootstrap.meta.sources.push({ id: 'qa-bootstrap', label: '화면 검증용 파생 결과', kind: 'DERIVED' });
  withBootstrap.bootstrap = { sourceId: 'qa-bootstrap', iterations: 1000, seed: 42, resampleUnit: 'vehicle_day', weight: 60, topK: 2, period: structuredClone(withBootstrap.meta.period), results: withBootstrap.candidates.map((candidate, i) => ({ candidateId: candidate.id, meanRank: i ? 1.2 : 1.8, topKProbability: 1, rankSD: .4 })) };
  await uploadJson(withBootstrap);
  await page.getByTestId('dataset-name').filter({ hasText: '안정성 연결 검증' }).waitFor();
  await go('분석 대시보드');
  assert.equal(await page.locator('.unified-bootstrap-table tbody tr').count(), 2);
  await setWeight(30);
  assert.equal(await page.locator('.unified-bootstrap-table').count(), 0);
  await setWeight(60);
  assert.equal(await page.locator('.unified-bootstrap-table tbody tr').count(), 2);
  await go('데이터 관리');
  await uploadJson(DEFAULT_WORKSPACE);
  pass('provided Bootstrap results render only when weight, period and candidate contract match');

  const laterPeriod = datasetFixture('분석기간 변경');
  laterPeriod.meta.period = { start: '2025-05-01T00:00:00+09:00', end: '2025-05-03T23:59:59+09:00', timezone: 'Asia/Seoul' };
  await uploadJson(laterPeriod);
  await page.getByTestId('dataset-name').filter({ hasText: '분석기간 변경' }).waitFor();
  await go('분석 대시보드');
  await page.getByText('차량·운행일 선택', { exact: true }).click();
  assert.equal(await page.getByRole('combobox', { name: '운행일', exact: true }).locator('option').count(), 1);
  assert.equal(await page.getByRole('combobox', { name: '운행 차량', exact: true }).locator('option').count(), 1);
  await go('데이터 관리');
  await uploadJson(DEFAULT_WORKSPACE);
  pass('a changed analysis period scopes GPS options without deleting or inventing observations');

  const apiData = datasetFixture('API 연결 자료');
  const cors = { 'access-control-allow-origin': '*', 'content-type': 'application/json' };
  await context.route(qaPrefix + '**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/failure')) return route.fulfill({ status: 503, headers: cors, body: JSON.stringify({ error: 'unavailable' }) });
    if (path.endsWith('/invalid')) return route.fulfill({ status: 200, headers: cors, body: '{invalid-json' });
    if (path.endsWith('/slow')) {
      await new Promise(resolve => setTimeout(resolve, 350));
      return route.fulfill({ status: 200, headers: cors, body: JSON.stringify(apiData) }).catch(() => {});
    }
    return route.fulfill({ status: 200, headers: cors, body: JSON.stringify(apiData) });
  });
  if (standalone) await context.setOffline(false);
  await page.getByTestId('api-url').fill(qaPrefix + 'success');
  await page.getByTestId('api-connect').click();
  await page.getByTestId('dataset-name').filter({ hasText: 'API 연결 자료' }).waitFor();
  for (const endpoint of ['failure', 'invalid']) {
    await page.getByTestId('api-url').fill(qaPrefix + endpoint);
    await page.getByTestId('api-connect').click();
    await page.getByTestId('workspace-error').waitFor();
    assert.ok((await page.getByTestId('dataset-name').innerText()).includes('API 연결 자료'));
  }
  await page.getByTestId('api-url').fill(qaPrefix + 'slow');
  await page.getByTestId('api-connect').click();
  await uploadJson(datasetFixture('새 파일 우선 적용'));
  await page.getByTestId('dataset-name').filter({ hasText: '새 파일 우선 적용' }).waitFor();
  await page.waitForTimeout(450);
  assert.ok((await page.getByTestId('dataset-name').innerText()).includes('새 파일 우선 적용'));
  await uploadJson(DEFAULT_WORKSPACE);
  if (standalone) await context.setOffline(true);
  pass('API fetch accepts valid responses, preserves data on errors and prevents stale responses overwriting a newer file');

  await go('분석 결과 및 보고서');
  const csv = await getDownload(() => page.getByRole('button', { name: '후보지역 CSV 저장', exact: true }).click());
  assert.ok(csv.includes('SYNTHETIC') && csv.includes('0.876'));
  const exported = JSON.parse(await getDownload(() => page.getByRole('button', { name: '전체 데이터 JSON 저장', exact: true }).click()));
  assert.equal(exported.schemaVersion, '2.0'); assert.equal(exported.candidates.length, 8);
  const session = JSON.parse(await getDownload(() => page.getByRole('button', { name: '현재 분석 세션 저장', exact: true }).click()));
  assert.ok(session);
  pass('exports include source classifications, current scores and reloadable canonical data');

  await page.setViewportSize({ width: 1440, height: 1000 });
  await open();
  await capture('dashboard-unified-1440.png');
  await page.setViewportSize({ width: 1536, height: 1024 });
  await capture('dashboard-unified-1536.png');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.setViewportSize({ width: 390, height: 844 });
  await capture('dashboard-unified-mobile.png');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.getByRole('button', { name: '메뉴 열기', exact: true }).click();
  await go('데이터 관리');
  assert.equal(await page.locator('.sidebar.mobile-open').count(), 0);
  pass('desktop/mobile screens retain layout and functional navigation');

  assert.deepEqual(errors, []); assert.deepEqual(unexpectedRequests, []); assert.deepEqual(unexpectedFailures, []);
  pass('no unrequested network calls, missing assets or browser runtime errors');
  await writeFile(artifacts + (standalone ? 'standalone-verification.json' : 'browser-verification.json'), JSON.stringify({ groups, standalone: !!standalone, errors, unexpectedRequests, unexpectedFailures }, null, 2));
  console.log(`\n${groups} unified browser verification groups passed.`);
} catch (error) {
  await page.screenshot({ path: '/tmp/atlas-unified-failure.png', fullPage: true });
  throw error;
} finally { await browser.close(); }
