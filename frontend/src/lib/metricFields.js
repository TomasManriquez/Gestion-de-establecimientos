/**
 * metricFields.js — campos editables de `metrics` (un documento por establecimiento y año).
 *
 * Los rangos replican los de `MetricUpdate` en el backend para avisar antes de guardar; el
 * backend los vuelve a validar (422). Algunas proporciones se guardan 0–1 pero se editan en %.
 *
 * kind:
 *   int      entero 0–100.000
 *   float    decimal con `max`
 *   rate     porcentaje 0–100, se guarda tal cual
 *   fraction porcentaje en pantalla, se guarda como proporción 0–1 (IVE)
 *   fractionText igual que fraction, pero se guarda como texto (asistencia, por la planilla)
 *   score    puntaje 0–1.000
 *   category texto de una lista cerrada
 */
export const PERFORMANCE_CATEGORIES = ['ALTO', 'MEDIO', 'MEDIO-BAJO', 'INSUFICIENTE'];

export const METRIC_SECTIONS = [
  {
    title: 'Matrícula y personal',
    fields: [
      { key: 'enrollment', label: 'Matrícula', kind: 'int' },
      { key: 'num_teachers', label: 'Docentes', kind: 'int' },
      { key: 'num_assistants', label: 'Asistentes de la educación', kind: 'int' },
    ],
  },
  {
    title: 'Asistencia y vulnerabilidad',
    fields: [
      { key: 'attendance_avg', label: 'Asistencia promedio (%)', kind: 'fractionText' },
      { key: 'ive_basica', label: 'IVE básica (%)', kind: 'fraction' },
      { key: 'ive_media', label: 'IVE media (%)', kind: 'fraction' },
    ],
  },
  {
    title: 'Rendimiento',
    fields: [
      { key: 'grade_avg', label: 'Promedio de notas', kind: 'float', max: 7 },
      { key: 'promoted', label: 'Promovidos', kind: 'int' },
      { key: 'failed', label: 'Reprobados', kind: 'int' },
      { key: 'transferred', label: 'Trasladados', kind: 'int' },
      { key: 'dropouts', label: 'Desertores', kind: 'int' },
      { key: 'tasa_promocion', label: 'Tasa de promoción (%)', kind: 'rate' },
      { key: 'tasa_reprobacion', label: 'Tasa de reprobación (%)', kind: 'rate' },
      { key: 'tasa_desercion', label: 'Tasa de deserción (%)', kind: 'rate' },
      { key: 'tasa_retencion', label: 'Tasa de retención (%)', kind: 'rate' },
      { key: 'desempeno_basica', label: 'Categoría de desempeño básica', kind: 'category' },
      { key: 'desempeno_media', label: 'Categoría de desempeño media', kind: 'category' },
    ],
  },
  {
    title: 'Resultados de pruebas',
    fields: [
      { key: 'ptje_nem', label: 'Puntaje NEM', kind: 'score' },
      { key: 'ptje_ranking', label: 'Puntaje ranking', kind: 'score' },
      { key: 'score_lectura', label: 'Lectura', kind: 'score' },
      { key: 'score_matematica1', label: 'Matemática 1', kind: 'score' },
      { key: 'score_matematica2', label: 'Matemática 2', kind: 'score' },
      { key: 'score_historia', label: 'Historia y Cs. Sociales', kind: 'score' },
      { key: 'score_ciencia', label: 'Ciencias', kind: 'score' },
      { key: 'total_rendidores', label: 'Total de rendidores', kind: 'int' },
    ],
  },
];

export const METRIC_FIELDS = METRIC_SECTIONS.flatMap((s) => s.fields);

const LIMITS = { int: [0, 100000], rate: [0, 100], fraction: [0, 100], fractionText: [0, 100], score: [0, 1000] };

const round = (n, d) => Math.round(n * 10 ** d) / 10 ** d;
const parseNumber = (text) => Number(String(text).trim().replace(',', '.'));

/** Valor guardado → texto del input. En la carga original un 0 en tasas, IVE y puntajes es «sin dato». */
export function toInput(field, raw) {
  if (raw === null || raw === undefined || raw === '') return '';
  if (field.kind === 'category') return String(raw);
  const n = Number(raw);
  if (!Number.isFinite(n)) return '';
  if (field.kind === 'int') return String(n);
  if (n === 0) return '';
  if (field.kind === 'fraction' || field.kind === 'fractionText') return String(round(n * 100, 1));
  return String(round(n, 2));
}

/**
 * Texto del input → { value } listo para el PUT, { error } si no es válido, o {} si está vacío.
 */
export function fromInput(field, text) {
  const t = String(text ?? '').trim();
  if (t === '') return {};
  if (field.kind === 'category') {
    return PERFORMANCE_CATEGORIES.includes(t) ? { value: t } : { error: 'Elige una categoría de la lista' };
  }
  const n = parseNumber(t);
  if (!Number.isFinite(n)) return { error: 'Debe ser un número' };
  if (field.kind === 'int' && !Number.isInteger(n)) return { error: 'Debe ser un número entero' };
  const [min, max] = field.kind === 'float' ? [0, field.max] : LIMITS[field.kind];
  if (n < min || n > max) return { error: `Debe estar entre ${min} y ${max}` };
  if (field.kind === 'fraction') return { value: round(n / 100, 4) };
  if (field.kind === 'fractionText') return { value: String(round(n / 100, 4)) };
  return { value: n };
}

/** ¿El valor ya guardado está fuera de rango? (p. ej. una retención de 100,3 de la carga original) */
export function storedValueProblem(field, raw) {
  const text = toInput(field, raw);
  return text === '' ? null : fromInput(field, text).error ?? null;
}

/**
 * Arma un PUT por año con solo los campos que cambiaron.
 * `metrics`: documentos guardados; `edits`: { [year]: { [key]: texto } }.
 * Devuelve { payloads: [{ year, body }], errors: { [year]: { [key]: mensaje } } }.
 */
export function buildMetricPayloads(metrics, edits) {
  const byYear = Object.fromEntries((metrics ?? []).map((m) => [m.year, m]));
  const payloads = [];
  const errors = {};
  for (const [yearKey, fields] of Object.entries(edits ?? {})) {
    const year = Number(yearKey);
    const saved = byYear[year] ?? {};
    const body = {};
    for (const field of METRIC_FIELDS) {
      if (!(field.key in fields)) continue;
      const text = fields[field.key];
      if (String(text).trim() === toInput(field, saved[field.key])) continue;   // sin cambio
      const parsed = fromInput(field, text);
      if (parsed.error) (errors[year] ??= {})[field.key] = parsed.error;
      else if ('value' in parsed) body[field.key] = parsed.value;
    }
    if (Object.keys(body).length) payloads.push({ year, body });
  }
  return { payloads, errors };
}
