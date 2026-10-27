/**
 * enrollment.js — lógica pura del tablero de matrícula (ADR-018).
 *
 * Recibe el contrato de `GET /api/analytics/enrollment` (un punto por establecimiento y año) y
 * calcula todo lo que el tablero muestra. Reglas que importan:
 *   - Un establecimiento «está en el año» si tiene un punto con matrícula (0 incluido) y, si cerró,
 *     el año no es posterior a `closed_year`.
 *   - Las variaciones entre años se calculan solo sobre los establecimientos que están en AMBOS años:
 *     una escuela que cierra o un jardín que entra no distorsionan la comparación.
 *   - `null` es «sin dato»; nunca se suma como 0. La asistencia se pondera por la matrícula del año.
 *   - Un indicador sin dato en el año elegido lo declara (`lastYear`) en vez de mostrar otro año en silencio.
 */

/** Tipos de establecimiento: se agrupan por el número que antecede a la categoría («7. LICEO …»). */
export const GROUPS = [
  { name: 'Escuela completa', short: 'Esc. completa', prefixes: [4] },
  { name: 'Colegio', short: 'Colegio', prefixes: [9] },
  { name: 'Liceo politécnico', short: 'Liceo polit.', prefixes: [7] },
  { name: 'Liceo técnico-profesional', short: 'Liceo TP', prefixes: [8] },
  { name: 'Jardín y sala cuna', short: 'Jardín', prefixes: [1, 2, 3] },
  { name: 'Rural multigrado', short: 'Rural mult.', prefixes: [6] },
  { name: 'Escuela con curso combinado', short: 'Curso comb.', prefixes: [5] },
  { name: 'Escuela diferencial', short: 'Diferencial', prefixes: [0] },
  { name: 'Sin categoría', short: 'Otros', prefixes: [] },
];
export const JARDIN = 4;
const OTHER = GROUPS.length - 1;

export function groupOf(category) {
  const m = /^\s*(\d+)\s*\./.exec(category ?? '');
  if (!m) return OTHER;
  const idx = GROUPS.findIndex((g) => g.prefixes.includes(Number(m[1])));
  return idx < 0 ? OTHER : idx;
}

/** 'PUERTO VARAS' → 'Puerto Varas', 'LOS MUERMOS' → 'Los Muermos' */
export const titleCase = (t) => String(t ?? '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
export const sum = (arr, f = (x) => x) => arr.reduce((a, x) => a + f(x), 0);
export const fmt = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
export const dec = (n, d = 1) => n.toFixed(d).replace('.', ',');
export const signPct = (x) => `${x < 0 ? '−' : x > 0 ? '+' : ''}${dec(Math.abs(x))} %`;
export const signInt = (x) => `${x < 0 ? '−' : x > 0 ? '+' : ''}${fmt(Math.abs(x))}`;

export const DEFAULT_FILTER = { comuna: null, tipo: null, area: 'all', jardines: true };
export const isFiltered = (f) => f.comuna != null || f.tipo != null || f.area !== 'all' || !f.jardines;

export function buildModel(dataset) {
  const ests = (dataset?.establishments ?? []).map((e) => ({
    ...e, group: groupOf(e.category), rural: e.area_type === 'RURAL', status: e.status || 'active',
  }));
  const byKey = new Map((dataset?.points ?? []).map((p) => [`${p.rbd}|${p.year}`, p]));
  const enrollmentYears = dataset?.indicators?.enrollment?.years ?? [];
  const model = {
    ests,
    years: dataset?.years ?? [],
    enrollmentYears,
    indicators: dataset?.indicators ?? {},
    comunas: [],
    point: (rbd, year) => byKey.get(`${rbd}|${year}`) ?? null,
  };
  // Comunas desde los datos, de mayor a menor matrícula del último año (solo los establecimientos de ese año).
  const last = enrollmentYears[enrollmentYears.length - 1];
  const size = {};
  ests.forEach((e) => { size[e.comuna] = (size[e.comuna] ?? 0) + (inYear(model, e, last) ? model.point(e.rbd, last).enrollment : 0); });
  model.comunas = Object.keys(size).sort((a, b) => size[b] - size[a] || a.localeCompare(b, 'es'));
  return model;
}

/** Año por defecto (el último con matrícula) y año de comparación (el anterior con matrícula). */
export function defaultYears(model) {
  const ys = model.enrollmentYears;
  const year = ys.length ? ys[ys.length - 1] : null;
  return { year, compare: ys.length > 1 ? ys[ys.length - 2] : null };
}

export const inYear = (model, est, year) => {
  const p = model.point(est.rbd, year);
  if (!p || p.enrollment == null) return false;
  return !(est.status === 'closed' && est.closed_year != null && year > est.closed_year);
};

/** `skip`: nombres de filtros que no se aplican ('comuna' | 'tipo' | 'area'), para gráficos que los usan como selección. */
export const passes = (est, f, skip = []) =>
  (skip.includes('comuna') || f.comuna == null || est.comuna === f.comuna)
  && (skip.includes('tipo') || f.tipo == null || est.group === f.tipo)
  && (skip.includes('area') || f.area === 'all' || (f.area === 'r') === est.rural)
  && (f.jardines || est.group !== JARDIN);

export const eesOf = (model, f, year, skip = []) =>
  year == null ? [] : model.ests.filter((e) => passes(e, f, skip) && inYear(model, e, year));

const enrollmentOf = (model, e, year) => model.point(e.rbd, year)?.enrollment ?? 0;

/** Matrícula de `year` y su variación contra `compare` sobre los establecimientos presentes en ambos. */
export function totalsWithDelta(model, f, year, compare, skip = []) {
  const ees = eesOf(model, f, year, skip);
  const value = sum(ees, (e) => enrollmentOf(model, e, year));
  if (compare == null) return { ees, value, delta: null, pct: null, entered: 0, left: 0, matched: 0 };
  const matched = ees.filter((e) => inYear(model, e, compare));
  const now = sum(matched, (e) => enrollmentOf(model, e, year));
  const before = sum(matched, (e) => enrollmentOf(model, e, compare));
  const prev = eesOf(model, f, compare, skip);
  return {
    ees, value, matched: matched.length, base: before,
    delta: now - before, pct: before ? ((now - before) / before) * 100 : null,
    entered: ees.length - matched.length,
    left: prev.filter((e) => !inYear(model, e, year)).length,
  };
}

/** Indicador de cabecera para un año: valor, cobertura y, si falta el dato, el último año que lo tiene. */
export function headline(model, f, year, compare) {
  const ees = eesOf(model, f, year);
  const t = totalsWithDelta(model, f, year, compare);

  const att = ees.map((e) => ({ e, p: model.point(e.rbd, year) })).filter(({ p }) => p?.attendance != null && p.enrollment > 0);
  const attW = sum(att, ({ p }) => p.enrollment);
  const attendance = {
    value: attW ? sum(att, ({ p }) => p.attendance * p.enrollment) / attW : null,
    n: att.length, total: ees.length,
    asOf: [...new Set(att.map(({ p }) => p.attendance_as_of).filter(Boolean))],
    lastYear: lastYearWith(model, 'attendance', year),
  };
  const teach = ees.map((e) => model.point(e.rbd, year)?.teachers).filter((v) => v != null);
  const teachers = { value: teach.length ? sum(teach) : null, n: teach.length, total: ees.length, lastYear: lastYearWith(model, 'teachers', year) };

  const asOf = [...new Set(ees.map((e) => model.point(e.rbd, year)?.enrollment_as_of).filter(Boolean))];
  return {
    establishments: { value: ees.length, withEnrollment: ees.filter((e) => enrollmentOf(model, e, year) > 0).length },
    enrollment: { value: t.value, delta: t.delta, pct: t.pct, asOf, entered: t.entered, left: t.left, matched: t.matched },
    attendance, teachers,
  };
}

/** Último año (distinto del elegido) con dato del indicador; null si no hay otro. */
export function lastYearWith(model, key, year) {
  const ys = (model.indicators[key]?.years ?? []).filter((y) => y !== year);
  return ys.length ? ys[ys.length - 1] : null;
}

/** Evolución de la matrícula. `byComuna`: una serie por comuna. Solo años con algún establecimiento. */
export function evolution(model, f, byComuna) {
  const years = model.years.filter((y) => eesOf(model, f, y).length > 0);
  const total = (flt) => years.map((y) => ({ year: y, value: sum(eesOf(model, flt, y), (e) => enrollmentOf(model, e, y)) }));
  if (!byComuna) return { years, series: [{ key: 'total', label: 'Total', points: total(f) }] };
  return {
    years,
    series: model.comunas.map((c) => ({ key: c, label: c, selected: f.comuna == null || f.comuna === c, points: total({ ...f, comuna: c }) })),
  };
}

/** Primer año con jardines dentro del filtro (para marcar el salto en la serie). */
export function jardinesFrom(model, f) {
  if (!f.jardines) return null;
  return model.years.find((y) => eesOf(model, { ...f, tipo: null }, y).some((e) => e.group === JARDIN)) ?? null;
}

export function byComunaBars(model, f, year, compare) {
  return model.comunas.map((c) => {
    const t = totalsWithDelta(model, { ...f, comuna: c }, year, compare);
    return { comuna: c, value: t.value, pct: t.pct, count: t.ees.length };
  });
}

export function byGroup(model, f, year) {
  const ees = eesOf(model, f, year, ['tipo']);
  return GROUPS.map((g, i) => {
    const rows = ees.filter((e) => e.group === i);
    return { index: i, name: g.name, count: rows.length, value: sum(rows, (e) => enrollmentOf(model, e, year)) };
  }).filter((g) => g.count > 0);
}

export function urbanRural(model, f, year) {
  const ees = eesOf(model, f, year, ['area']);
  return model.comunas.map((c) => {
    const rows = ees.filter((e) => e.comuna === c);
    const urban = sum(rows.filter((e) => !e.rural), (e) => enrollmentOf(model, e, year));
    const rural = sum(rows.filter((e) => e.rural), (e) => enrollmentOf(model, e, year));
    return { comuna: c, urban, rural, total: urban + rural };
  });
}

/** Mapa de calor comuna × tipo. `measure`: 'ee' (establecimientos) o 'mat' (matrícula). */
export function heatmap(model, f, year, measure) {
  const ees = eesOf(model, f, year, ['comuna', 'tipo']);
  const groups = [...new Set(ees.map((e) => e.group))].sort((a, b) => a - b);
  const rows = model.comunas.map((c) => ({
    comuna: c,
    cells: groups.map((g) => {
      const rr = ees.filter((e) => e.comuna === c && e.group === g);
      return { group: g, value: measure === 'ee' ? rr.length : sum(rr, (e) => enrollmentOf(model, e, year)) };
    }),
  }));
  return { groups, rows, max: Math.max(1, ...rows.flatMap((r) => r.cells.map((c) => c.value))) };
}

export const SIZE_BINS = [[0, 9, '0–9'], [10, 19, '10–19'], [20, 29, '20–29'], [30, 49, '30–49'], [50, 99, '50–99'], [100, 199, '100–199'], [200, 399, '200–399'], [400, Infinity, '400+']];

export function sizeHistogram(model, f, year) {
  const vals = eesOf(model, f, year).map((e) => enrollmentOf(model, e, year));
  return SIZE_BINS.map(([a, b, label]) => ({ label, count: vals.filter((v) => v >= a && v <= b).length }));
}

/** Puntos de «tamaño y asistencia»: todos los del año con dato; `on` indica si pasan el filtro. */
export function scatter(model, f, year) {
  return model.ests
    .filter((e) => inYear(model, e, year))
    .map((e) => ({ e, p: model.point(e.rbd, year) }))
    .filter(({ p }) => p.attendance != null && p.enrollment > 0)
    .map(({ e, p }) => ({ rbd: e.rbd, name: e.name, enrollment: p.enrollment, attendance: p.attendance, rural: e.rural, on: passes(e, f) }));
}

/** Establecimientos con cambio de matrícula entre dos años (solo los presentes en ambos). */
export function changes(model, f, year, compare) {
  if (compare == null) return [];
  return eesOf(model, f, year).filter((e) => inYear(model, e, compare)).map((e) => {
    const now = model.point(e.rbd, year);
    const before = model.point(e.rbd, compare);
    return { rbd: e.rbd, name: e.name, comuna: e.comuna, before: before.enrollment, now: now.enrollment, delta: now.enrollment - before.enrollment, attendance: now.attendance ?? before.attendance };
  });
}

/**
 * Texto del panel «Origen del dato». Lo que no está en el contrato (archivo, quién cargó) no se inventa:
 * la plataforma aún no registra cargas (D36), y el panel lo dice.
 */
export function sourceInfo(key, model, f, year) {
  const h = headline(model, f, year, null);
  const years = model.indicators[key === 'establishments' ? 'enrollment' : key]?.years ?? [];
  const cover = (n, total) => `${n} de ${total} establecimientos con dato`;
  const common = [['Años con dato', years.length ? years.join(', ') : 'ninguno'], ['Año mostrado', String(year)]];
  const note = ['Registro de cargas', 'Aún no se registra quién ni cuándo cargó cada dato (brecha D36). Se actualiza editando la ficha o con la carga de la planilla.'];
  if (key === 'attendance') {
    return {
      title: `Asistencia ${year}`,
      rows: [
        ['Definición', 'Promedio de asistencia del año por establecimiento.'],
        ['Cálculo', h.attendance.value == null ? 'Sin datos con este filtro.' : `Ponderada por la matrícula del año: ${dec(h.attendance.value * 100)} %.`],
        ['Cobertura', cover(h.attendance.n, h.attendance.total)],
        ['Corte', h.attendance.asOf.length ? h.attendance.asOf.join(', ') : 'Año completo'],
        ...common, note,
      ],
    };
  }
  if (key === 'teachers') {
    return {
      title: `Docentes ${year}`,
      rows: [
        ['Definición', 'Por confirmar: todas las funciones o solo docentes de aula.'],
        ['Cálculo', 'Suma de los establecimientos con dato.'],
        ['Cobertura', cover(h.teachers.n, h.teachers.total)],
        ...common, note,
      ],
    };
  }
  return {
    title: `Matrícula ${year}`,
    rows: [
      ['Definición', 'Alumnos matriculados en el establecimiento.'],
      ['Cálculo', 'Suma de los establecimientos del filtro que están en el año.'],
      ['Cobertura', cover(h.establishments.withEnrollment, h.establishments.value)],
      ['Corte', h.enrollment.asOf.length ? h.enrollment.asOf.join(', ') : 'Año completo'],
      ['Comparación', 'La variación usa solo los establecimientos presentes en ambos años.'],
      ...common, note,
    ],
  };
}

/** Plegado de squarified treemap sobre un rectángulo de TW×TH. Devuelve {index: [x, y, w, h]}. */
export function treemapLayout(items, TW = 240, TH = 100) {
  const total = sum(items, (i) => i.value) || 1;
  const nodes = items.filter((i) => i.value > 0).map((i) => ({ index: i.index, a: (i.value / total) * TW * TH })).sort((a, b) => b.a - a.a);
  const out = {};
  let [x, y, w, h] = [0, 0, TW, TH];
  let rest = nodes;
  while (rest.length) {
    const side = Math.min(w, h);
    const worst = (row) => {
      const s = sum(row, (z) => z.a);
      const mx = Math.max(...row.map((z) => z.a));
      const mn = Math.min(...row.map((z) => z.a));
      return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
    };
    const row = [rest[0]];
    let k = 1;
    while (k < rest.length && worst(row.concat([rest[k]])) <= worst(row)) { row.push(rest[k]); k += 1; }
    const s = sum(row, (z) => z.a);
    if (w >= h) {
      const cw = s / h; let cy = y;
      row.forEach((z) => { const zh = z.a / cw; out[z.index] = [x, cy, cw, zh]; cy += zh; });
      x += cw; w -= cw;
    } else {
      const ch = s / w; let cx = x;
      row.forEach((z) => { const zw = z.a / ch; out[z.index] = [cx, y, zw, ch]; cx += zw; });
      y += ch; h -= ch;
    }
    rest = rest.slice(k);
  }
  return out;
}
