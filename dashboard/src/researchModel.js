import researchData from './research-data.json' with { type: 'json' };

export const RESEARCH_DATA = researchData;

export function validateResearchData(data) {
  if (data?.schemaVersion !== '1.0' || data.source?.boundaryKind !== 'PUBLIC_AGGREGATE' ||
      data.source?.gpsKind !== 'SYNTHETIC' || data.gps?.kind !== 'SYNTHETIC') {
    throw new Error('Unsupported research data schema or provenance');
  }
  if (!Array.isArray(data.projected?.dongs) || !Array.isArray(data.gps.positions) ||
      !data.gps.positions.every(p => p.kind === 'SYNTHETIC' && Number.isFinite(p.x) && Number.isFinite(p.y))) {
    throw new Error('Invalid research geometry or positions');
  }
  return data;
}

export function filterPositions(filters = {}, data = RESEARCH_DATA) {
  validateResearchData(data);
  const { vehicle = 'all', day = 'all', time = 'all' } = filters;
  if (!['all', 'morning', 'afternoon'].includes(time)) throw new Error('Unsupported time filter');
  if (vehicle !== 'all' && !data.gps.vehicles.includes(vehicle)) throw new Error('Unknown vehicle filter');
  if (day !== 'all' && !data.gps.days.includes(day)) throw new Error('Unknown day filter');
  return data.gps.positions.filter(p =>
    (vehicle === 'all' || p.vehicleId === vehicle) &&
    (day === 'all' || p.day === day) &&
    (time === 'all' || (time === 'morning' ? p.hour < 12 : p.hour >= 12)));
}

export function deriveResearch(filters = {}, data = RESEARCH_DATA) {
  const positions = filterPositions(filters, data);
  const units = data.projected.dongs.map(unit => {
    // A boundary point with multiple matches is not silently counted twice.
    const samples = positions.filter(p => p.dongCode === unit.code);
    return { ...unit, boundaryKind: 'PUBLIC_AGGREGATE', positionKind: 'SYNTHETIC', sampleCount: samples.length,
      vehicleCount: new Set(samples.map(p => p.vehicleId)).size,
      dayCount: new Set(samples.map(p => p.day)).size,
      sampleShare: positions.length ? samples.length / positions.length : 0,
      firstTimestamp: samples.length ? samples.reduce((a,p) => a < p.timestamp ? a : p.timestamp, samples[0].timestamp) : null,
      lastTimestamp: samples.length ? samples.reduce((a,p) => a > p.timestamp ? a : p.timestamp, samples[0].timestamp) : null,
      sampleIds: samples.map(p => p.id),
      mobility: null, spatial: null, integrated: null, bootstrap: null };
  });
  const selectedUnit = units.find(unit => unit.code === filters.selectedCode) || units[0] || null;
  const kpis = { unitCount: units.length, positionCount: positions.length,
    vehicleCount: new Set(positions.map(p => p.vehicleId)).size,
    dayCount: new Set(positions.map(p => p.day)).size,
    activeUnitCount: units.filter(unit => unit.sampleCount > 0).length,
    ambiguousCount: positions.filter(p => p.dongCodes.length > 1).length,
    unmatchedCount: positions.filter(p => !p.dongCodes.length).length };
  return { positions, units, perDong: units, selectedUnit, kpis,
    gpsCount: kpis.positionCount, vehicleCount: kpis.vehicleCount, dayCount: kpis.dayCount,
    sortedUnits: [...units].sort((a,b) => b.sampleCount - a.sampleCount || a.code.localeCompare(b.code)),
    filters: { vehicle: filters.vehicle || 'all', day: filters.day || 'all', time: filters.time || 'all' },
    sourceKind: 'SYNTHETIC', boundaryKind: 'PUBLIC_AGGREGATE' };
}

const escapeCsv = value => `"${String(value ?? '').replaceAll('"', '""')}"`;

export function exportResearchCsv(filters = {}, data = RESEARCH_DATA) {
  const summary = deriveResearch(filters, data);
  const columns = ['dong_code','dong_name','boundary_year','boundary_kind','position_kind','sample_count',
    'vehicle_count','day_count','area_m2','vehicle_filter','day_filter','time_filter','boundary_run_id','gps_run_id'];
  const rows = summary.units.map(unit => [unit.code,unit.name,data.source.boundaryYear,'PUBLIC_AGGREGATE',
    'SYNTHETIC',unit.sampleCount,unit.vehicleCount,unit.dayCount,unit.areaM2,
    summary.filters.vehicle,summary.filters.day,summary.filters.time,
    data.manifests.dongs.run_id,data.manifests.gps.run_id]);
  return '\uFEFF' + [columns,...rows].map(row => row.map(escapeCsv).join(',')).join('\r\n');
}

validateResearchData(RESEARCH_DATA);
