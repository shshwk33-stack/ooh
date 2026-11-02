import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { RESEARCH_DATA, deriveResearch, filterPositions, exportResearchCsv,
  validateResearchData } from '../src/researchModel.js';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const python = join(root, '.venv-analysis/bin/python');
const sha = raw => createHash('sha256').update(raw).digest('hex');

test('packaged real boundary and synthetic GPS retain verified run/artifact hashes', () => {
  assert.equal(RESEARCH_DATA.schemaVersion, '1.0');
  assert.equal(RESEARCH_DATA.source.boundaryYear, 2013);
  assert.equal(RESEARCH_DATA.source.boundaryKind, 'PUBLIC_AGGREGATE');
  assert.equal(RESEARCH_DATA.source.gpsKind, 'SYNTHETIC');
  assert.equal(RESEARCH_DATA.provenance.originalFilesAndArtifactHashesVerified, true);
  for (const [name, folder] of Object.entries({ district:'mapo-district',dongs:'mapo-dongs',gps:'synthetic-gps-validation' })) {
    const manifest = RESEARCH_DATA.manifests[name];
    for (const [filename,expected] of Object.entries(manifest.outputs)) {
      assert.equal(sha(readFileSync(join(root,'docs/research/results',folder,filename))), expected);
    }
  }
});

test('actual exported geometry and scenario samples have finite metric coordinates', () => {
  assert.equal(RESEARCH_DATA.district.features.length, 1);
  assert.equal(RESEARCH_DATA.dongs.features.length, 16);
  assert.equal(RESEARCH_DATA.gps.positions.length, 72);
  for (const unit of RESEARCH_DATA.projected.dongs) {
    assert.equal(typeof unit.code, 'string');
    assert.ok(unit.areaM2 > 0 && unit.perimeterM > 0);
    assert.ok(unit.label.every(Number.isFinite));
    for (const polygon of unit.polygons) for (const ring of polygon) {
      assert.deepEqual(ring[0], ring.at(-1));
      assert.ok(ring.every(point => point.length===2 && point.every(Number.isFinite)));
    }
  }
  for (const p of RESEARCH_DATA.gps.positions) {
    assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y));
    assert.equal(p.kind, 'SYNTHETIC');
  }
});

test('Shapely boundary-inclusive joins yield three occupied dongs without invented visits', () => {
  const summary = deriveResearch();
  assert.deepEqual(summary.kpis,{unitCount:16,positionCount:72,vehicleCount:2,dayCount:3,
    activeUnitCount:3,ambiguousCount:0,unmatchedCount:0});
  assert.deepEqual(summary.units.filter(u=>u.sampleCount).map(u=>[u.code,u.name,u.sampleCount]),[
    ['1114061','염리동',12],['1114066','서교동',36],['1114078','아현동',24]
  ]);
  assert.equal(summary.units.reduce((n,u)=>n+u.sampleCount,0),72);
  assert.ok(summary.units.every(u=>u.mobility===null && u.spatial===null && u.integrated===null && u.bootstrap===null));
});

test('vehicle and artificial day filters update the same underlying observations and unit aggregates', () => {
  const all = deriveResearch();
  const day = deriveResearch({day:'2024-05-02'});
  const vehicle = deriveResearch({vehicle:'SYNTH-VEH-02'});
  const combined = deriveResearch({day:'2024-05-02',vehicle:'SYNTH-VEH-02',selectedCode:'1114061'});
  assert.equal(day.kpis.positionCount,24);
  assert.equal(day.kpis.dayCount,1);
  assert.equal(vehicle.kpis.positionCount,36);
  assert.equal(vehicle.kpis.vehicleCount,1);
  assert.equal(combined.kpis.positionCount,12);
  assert.equal(combined.selectedUnit.name,'염리동');
  assert.equal(combined.selectedUnit.sampleCount,4);
  assert.ok(combined.positions.every(p=>all.positions.some(a=>a.id===p.id)));
  assert.ok(combined.positions.every(p=>p.day==='2024-05-02' && p.vehicleId==='SYNTH-VEH-02'));
});

test('UTC samples are interpreted using Asia/Seoul dates and unsupported afternoon stays empty', () => {
  const first = RESEARCH_DATA.gps.positions[0];
  assert.equal(first.timestamp,'2024-05-01T01:00:00Z');
  assert.equal(first.localTimestamp,'2024-05-01T10:00:00+09:00');
  assert.equal(first.hour,10);
  assert.equal(filterPositions({time:'morning'}).length,72);
  const empty = deriveResearch({time:'afternoon'});
  assert.equal(empty.positions.length,0);
  assert.equal(empty.kpis.vehicleCount,0);
  assert.ok(empty.units.every(u=>u.sampleCount===0 && u.sampleShare===0));
});

test('unknown filter values and unrecognized source kinds fail explicitly', () => {
  assert.throws(()=>deriveResearch({vehicle:'UNKNOWN'}),/Unknown vehicle/);
  assert.throws(()=>deriveResearch({day:'2030-01-01'}),/Unknown day/);
  assert.throws(()=>deriveResearch({time:'evening'}),/Unsupported time/);
  const copied=structuredClone(RESEARCH_DATA);
  copied.source.gpsKind='OBSERVED_GPS';
  assert.throws(()=>validateResearchData(copied),/provenance/);
  copied.source.gpsKind='SYNTHETIC';
  copied.gps.positions[0].x=NaN;
  assert.throws(()=>validateResearchData(copied),/Invalid research/);
});

test('boundary ambiguity is retained and excluded from per-unit counting instead of double-counted', () => {
  const copied=structuredClone(RESEARCH_DATA);
  copied.gps.positions[0].dongCodes=['1114066','1114078'];
  copied.gps.positions[0].dongCode=null;
  const summary=deriveResearch({},copied);
  assert.equal(summary.kpis.ambiguousCount,1);
  assert.equal(summary.positions.length,72);
  assert.equal(summary.units.reduce((n,u)=>n+u.sampleCount,0),71);
});

test('selection, repeated derivation and sorted rows preserve the source bundle', () => {
  const before=JSON.stringify(RESEARCH_DATA);
  const first=deriveResearch({selectedCode:'1114066'});
  assert.equal(first.selectedUnit.code,'1114066');
  assert.equal(first.selectedUnit.sampleCount,36);
  assert.equal(first.sortedUnits[0].name,'서교동');
  assert.deepEqual(first,deriveResearch({selectedCode:'1114066'}));
  assert.equal(JSON.stringify(RESEARCH_DATA),before);
});

test('export preserves actual filter counts, year, source classifications and run lineage', () => {
  const csv=exportResearchCsv({day:'2024-05-02',vehicle:'SYNTH-VEH-02'});
  const lines=csv.slice(1).split('\r\n');
  assert.equal(lines.length,17);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"boundary_kind","position_kind"'));
  assert.ok(csv.includes('"2013","PUBLIC_AGGREGATE","SYNTHETIC"'));
  assert.ok(csv.includes(RESEARCH_DATA.manifests.dongs.run_id));
  assert.ok(csv.includes(RESEARCH_DATA.manifests.gps.run_id));
  assert.ok(csv.includes('"2024-05-02","all"'));
  assert.ok(csv.includes('"1114061","염리동","2013","PUBLIC_AGGREGATE","SYNTHETIC","4"'));
});

test('verified exporter regenerates the exact embedded payload', {skip:!existsSync(python)}, () => {
  const result=spawnSync(python,['scripts/export_dashboard_data.py','--check'],{cwd:root,encoding:'utf-8'});
  assert.equal(result.status,0,result.stderr);
  assert.match(result.stdout,/'units'|"units"/);
});

test('exporter rejects stale payload and tests covers semantics on shared boundaries', {skip:!existsSync(python)}, () => {
  const temporary=mkdtempSync(join(tmpdir(),'atlas-ui-export-'));
  try {
    const stale=join(temporary,'stale.json');
    writeFileSync(stale,'{}');
    const result=spawnSync(python,['scripts/export_dashboard_data.py','--check','--output',stale],{cwd:root,encoding:'utf-8'});
    assert.equal(result.status,2);
    assert.match(result.stderr,/stale/);
    const code=`from scripts.export_dashboard_data import spatial_match\nfrom shapely.geometry import Polygon,Point\na=Polygon([(0,0),(1,0),(1,1),(0,1)])\nb=Polygon([(1,0),(2,0),(2,1),(1,1)])\nf=[('a',a),('b',b)]\nassert spatial_match(Point(.5,.5),f)==['a']\nassert spatial_match(Point(1,.5),f)==['a','b']\nassert spatial_match(Point(3,.5),f)==[]\n`;
    const edge=spawnSync(python,['-c',code],{cwd:root,encoding:'utf-8'});
    assert.equal(edge.status,0,edge.stderr);
  } finally {rmSync(temporary,{recursive:true,force:true});}
});
