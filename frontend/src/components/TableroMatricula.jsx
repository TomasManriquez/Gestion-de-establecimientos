import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, TriangleAlert } from 'lucide-react';
import { analyticsApi } from '@/lib/api';
import {
  buildModel, defaultYears, headline, evolution, jardinesFrom, byComunaBars, byGroup, urbanRural, heatmap,
  sizeHistogram, scatter, changes, sourceInfo, fmt, dec, signPct, signInt, titleCase, DEFAULT_FILTER, isFiltered, GROUPS,
} from '@/lib/enrollment';
import { ChartCard, Segmented, SelectField, SourceLink, SourcePanel, Switch } from './tablero/controls';
import {
  EvolutionChart, ComunaBars, GroupTreemap, UrbanRuralShare, HeatMap, SizeHistogram, SizeAttendanceScatter, ChangesTable,
} from './tablero/charts';

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
/** '2026-03' → 'mar 2026' */
const monthLabel = (ym) => { const m = /^(\d{4})-(\d{2})$/.exec(ym ?? ''); return m ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : ym; };
const cutoff = (list) => (list.length ? `corte ${list.map(monthLabel).join(', ')}` : 'año completo');

function Kpi({ label, value, sub, subColor, accent, onSource, extra }) {
  return (
    <div className="tb-card flex min-w-0 flex-1 basis-52 flex-col gap-1 rounded-2xl border border-slep-line bg-white px-[18px] pb-4 pt-3.5" style={{ borderTop: `4px solid ${accent}` }}>
      <button type="button" onClick={onSource} aria-label={`${label}: ver origen del dato`} className="tb-press -mx-1 flex items-center justify-between rounded-md px-1 text-left text-sm font-bold text-slep-muted hover:text-slep-blue">
        {label}
        <span aria-hidden="true" className="text-xs">ⓘ</span>
      </button>
      <span className="text-4xl font-bold leading-none tracking-tight text-slep-ink">{value}</span>
      <span className="text-[13.5px] font-bold" style={{ color: subColor ?? '#5b6f82' }}>{sub}</span>
      {extra}
    </div>
  );
}

/**
 * Tablero de matrícula (ADR-018). Todos los gráficos salen de GET /api/analytics/enrollment y se calculan
 * aquí con `lib/enrollment.js`. El año y la comparación se eligen arriba; los gráficos son además filtros.
 */
export default function TableroMatricula() {
  const [dataset, setDataset] = useState(null);
  const [error, setError] = useState(false);
  const [year, setYear] = useState(null);
  const [compare, setCompare] = useState(null);
  const [filter, setFilter] = useState(DEFAULT_FILTER);
  const [evoMode, setEvoMode] = useState('total');
  const [heatMeasure, setHeatMeasure] = useState('ee');
  const [sort, setSort] = useState('baja');
  const [sourceKey, setSourceKey] = useState(null);

  const load = useCallback((signal) => {
    setError(false);
    setDataset(null);
    analyticsApi.enrollment(signal)
      .then((d) => {
        const m = buildModel(d);
        const def = defaultYears(m);
        setDataset(d); setYear(def.year); setCompare(def.compare);
      })
      .catch((e) => { if (e?.code !== 'ERR_CANCELED') setError(true); });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  const model = useMemo(() => buildModel(dataset), [dataset]);
  const set = (patch) => setFilter((f) => ({ ...f, ...patch }));

  const pickYear = (y) => {
    const ys = model.enrollmentYears;
    const prev = [...ys].filter((v) => v < y).pop();
    setYear(y); setCompare(prev ?? null);
  };

  const data = useMemo(() => {
    if (!dataset || year == null) return null;
    return {
      head: headline(model, filter, year, compare),
      evo: evolution(model, filter, evoMode === 'comuna'),
      jardinesFrom: jardinesFrom(model, filter),
      bars: byComunaBars(model, filter, year, compare),
      groups: byGroup(model, filter, year),
      share: urbanRural(model, filter, year),
      heat: heatmap(model, { ...filter, comuna: null, tipo: null }, year, heatMeasure),
      bins: sizeHistogram(model, filter, year),
      points: scatter(model, filter, year),
      changes: changes(model, filter, year, compare),
    };
  }, [dataset, model, filter, year, compare, evoMode, heatMeasure]);

  const closeSource = useCallback(() => setSourceKey(null), []);

  if (error) {
    return (
      <div role="alert" className="mx-auto flex max-w-md flex-col items-center gap-3 py-20 text-center">
        <TriangleAlert className="text-rose-600" size={32} aria-hidden="true" />
        <p className="text-lg font-bold">No se pudieron cargar los datos</p>
        <p className="text-sm text-slep-muted">Revisa tu conexión e inténtalo de nuevo.</p>
        <button type="button" onClick={() => load()} className="tb-press inline-flex min-h-11 items-center gap-2 rounded-xl bg-slep-blue px-5 font-bold text-white">
          <RefreshCw size={16} aria-hidden="true" /> Reintentar
        </button>
      </div>
    );
  }
  if (!dataset) {
    return (
      <div role="status" className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <div className="size-11 animate-spin rounded-full border-4 border-slep-line border-t-slep-blue" />
        <p className="text-sm font-medium text-slep-muted">Cargando matrícula…</p>
      </div>
    );
  }
  if (!data) {
    return <p className="py-20 text-center text-slep-muted">Aún no hay datos de matrícula cargados.</p>;
  }

  const { head } = data;
  const e = head.enrollment;
  const yearOptions = [...model.enrollmentYears].reverse().map((y) => ({ value: y, label: String(y) }));
  const compareOptions = [{ value: '', label: 'Sin comparar' }, ...model.enrollmentYears.filter((y) => y !== year).reverse().map((y) => ({ value: y, label: String(y) }))];
  const comunaOptions = [{ value: '', label: 'Todas' }, ...model.comunas.map((c) => ({ value: c, label: titleCase(c) }))];
  const tipoOptions = [{ value: '', label: 'Todos' }, ...GROUPS.map((g, i) => ({ value: i, label: g.name })).filter((o) => model.ests.some((x) => x.group === o.value))];
  const open = (key) => () => setSourceKey(key);
  const source = (key, label) => <SourceLink label={label} onClick={open(key)} />;
  const sourceData = sourceKey ? sourceInfo(sourceKey, model, filter, year) : null;

  const missing = (ind, label) => (ind.value == null && ind.lastYear != null && model.enrollmentYears.includes(ind.lastYear)
    ? <button type="button" onClick={() => pickYear(ind.lastYear)} className="tb-press -mx-1 self-start rounded-md px-1 text-[13px] font-bold text-slep-blue hover:underline">Último dato: {ind.lastYear} · ver</button>
    : null);

  return (
    <div className="flex flex-col gap-4 text-slep-ink">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-bold text-slep-blue">Tableros</p>
          <h1 className="text-4xl font-bold tracking-tight">Matrícula</h1>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-2xl border border-slep-line bg-white px-4 py-2">
          <SelectField id="tb-year" label="Año" value={year} options={yearOptions} onChange={(v) => pickYear(Number(v))} />
          <SelectField id="tb-compare" label="Comparar con" value={compare ?? ''} options={compareOptions} onChange={(v) => setCompare(v === '' ? null : Number(v))} />
          <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-[13.5px] font-bold text-emerald-800">
            <span className="size-2 rounded-full bg-emerald-600" aria-hidden="true" />{cutoff(e.asOf)}
          </span>
        </div>
      </header>

      <div className="flex flex-wrap gap-3.5">
        <Kpi label="Establecimientos" value={fmt(head.establishments.value)} accent="#168fd5" onSource={open('establishments')}
          sub={`${head.establishments.withEnrollment} con matrícula`}
          extra={compare != null && (e.entered > 0 || e.left > 0) ? <span className="text-xs text-slep-muted">{e.entered > 0 && `${e.entered} entran`}{e.entered > 0 && e.left > 0 && ' · '}{e.left > 0 && `${e.left} salen`} vs {compare}</span> : null} />
        <Kpi label={`Matrícula ${year}`} value={fmt(e.value)} accent="#36bce7" onSource={open('enrollment')}
          sub={compare != null && e.pct != null ? `${signPct(e.pct)} vs ${compare}` : compare != null ? 'sin base de comparación' : 'sin comparar'}
          subColor={e.pct != null ? (e.pct < 0 ? '#c22e44' : '#2f7d14') : undefined}
          extra={compare != null && e.delta != null ? <span className="text-xs text-slep-muted">{signInt(e.delta)} alumnos en {e.matched} establecimientos presentes en ambos años</span> : null} />
        <Kpi label={`Asistencia ${year}`} value={head.attendance.value == null ? '—' : `${dec(head.attendance.value * 100)} %`} accent="#76c93b" onSource={open('attendance')}
          sub={head.attendance.value == null ? 'sin dato este año' : `ponderada · ${head.attendance.n} de ${head.attendance.total} con dato`}
          extra={missing(head.attendance)} />
        <Kpi label={`Docentes ${year}`} value={head.teachers.value == null ? '—' : fmt(head.teachers.value)} accent="#f8c928" onSource={open('teachers')}
          sub={head.teachers.value == null ? 'sin dato este año' : `${head.teachers.n} de ${head.teachers.total} con dato`}
          extra={missing(head.teachers)} />
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-2xl border border-slep-line bg-white px-4 py-2.5">
        <SelectField id="tb-comuna" label="Comuna" value={filter.comuna ?? ''} options={comunaOptions} onChange={(v) => set({ comuna: v === '' ? null : v })} />
        <SelectField id="tb-tipo" label="Tipo" value={filter.tipo ?? ''} options={tipoOptions} onChange={(v) => set({ tipo: v === '' ? null : Number(v) })} />
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-bold">Área</span>
          <Segmented label="Área" value={filter.area} onChange={(v) => set({ area: v })} options={[{ value: 'all', label: 'Todas' }, { value: 'u', label: 'Urbano' }, { value: 'r', label: 'Rural' }]} />
        </div>
        <Switch checked={filter.jardines} onChange={(v) => set({ jardines: v })}>Incluir jardines</Switch>
        {isFiltered(filter) && (
          <button type="button" onClick={() => setFilter(DEFAULT_FILTER)} className="tb-press ml-auto min-h-9 rounded-xl bg-sky-50 px-3.5 text-sm font-bold text-slep-blue hover:bg-sky-100">Limpiar filtros</button>
        )}
      </div>

      <div className="flex flex-wrap gap-4">
        <ChartCard title="Evolución de la matrícula" className="flex-[2_1_34rem]"
          action={<Segmented size="sm" label="Vista de la evolución" value={evoMode} onChange={setEvoMode} options={[{ value: 'total', label: 'Total' }, { value: 'comuna', label: 'Por comuna' }]} />}
          source={source('enrollment', `Matrícula · ${model.years.length ? `${model.years[0]}–${model.years[model.years.length - 1]}` : ''} · ver origen`)}>
          <EvolutionChart data={data.evo} byComuna={evoMode === 'comuna'} markFrom={data.jardinesFrom} ariaLabel={`Matrícula por año: ${data.evo.series[0]?.points.map((p) => `${p.year} ${fmt(p.value)}`).join(', ')}`} />
        </ChartCard>
        <ChartCard title="Por comuna" className="flex-[1_1_20rem]" source={source('enrollment', 'Matrícula por comuna · ver origen')}>
          <ComunaBars rows={data.bars} selected={filter.comuna} onSelect={(c) => set({ comuna: c })} showDelta={compare != null} />
        </ChartCard>
      </div>

      <div className="flex flex-wrap gap-4">
        <ChartCard title="Por tipo de establecimiento" className="flex-[1_1_27rem]" source={source('enrollment', 'Matrícula por tipo · ver origen')}>
          <GroupTreemap groups={data.groups} selected={filter.tipo} onSelect={(t) => set({ tipo: t })} />
        </ChartCard>
        <ChartCard title="Urbano y rural" className="flex-[1_1_27rem]" source={source('enrollment', 'Matrícula por área · ver origen')}>
          <UrbanRuralShare rows={data.share} area={filter.area} comuna={filter.comuna} onArea={(a) => set({ area: a })} />
        </ChartCard>
      </div>

      <div className="flex flex-wrap gap-4">
        <ChartCard title="Comuna × tipo" className="flex-[2_1_34rem]"
          action={<Segmented size="sm" label="Medida del mapa de calor" value={heatMeasure} onChange={setHeatMeasure} options={[{ value: 'ee', label: 'Establecimientos' }, { value: 'mat', label: 'Matrícula' }]} />}
          source={source('enrollment', 'Establecimientos y matrícula · ver origen')}>
          <HeatMap heat={data.heat} measure={heatMeasure} comuna={filter.comuna} tipo={filter.tipo} onPick={(c, t) => set({ comuna: c, tipo: t })} />
        </ChartCard>
        <ChartCard title="Por tamaño" className="flex-[1_1_20rem]" source={source('enrollment', 'Matrícula por establecimiento · ver origen')}>
          <SizeHistogram bins={data.bins} />
        </ChartCard>
      </div>

      <div className="flex flex-wrap gap-4">
        <ChartCard title="Tamaño y asistencia" className="flex-[1_1_24rem]" source={source('attendance', `Asistencia ${year} · ver origen`)}>
          {data.points.length
            ? <SizeAttendanceScatter points={data.points} />
            : <p className="py-10 text-center text-sm text-slep-muted">No hay asistencia registrada para {year}.{head.attendance.lastYear != null && model.enrollmentYears.includes(head.attendance.lastYear) && (
              <> <button type="button" className="font-bold text-slep-blue hover:underline" onClick={() => pickYear(head.attendance.lastYear)}>Ver {head.attendance.lastYear}</button></>)}</p>}
        </ChartCard>
        <ChartCard title={compare != null ? `Establecimientos, ${compare} → ${year}` : 'Establecimientos'} className="flex-[2_1_34rem]"
          action={<Segmented size="sm" label="Orden de la tabla" value={sort} onChange={setSort} options={[{ value: 'baja', label: 'Mayor baja' }, { value: 'alza', label: 'Mayor alza' }]} />}
          source={source('enrollment', 'Matrícula por establecimiento · ver origen')}>
          <ChangesTable rows={data.changes} year={year} compare={compare} sort={sort} />
        </ChartCard>
      </div>

      <SourcePanel info={sourceData} onClose={closeSource} />
    </div>
  );
}
