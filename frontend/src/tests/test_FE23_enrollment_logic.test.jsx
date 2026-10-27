/**
 * test_FE23_enrollment_logic.test.jsx
 * ───────────────────────────────────
 * Tarea: tablero de matrícula · selección de año y comparación (ADR-018)
 *
 * Verifica, con un conjunto pequeño donde los números se calculan a mano, que:
 *   - el año por defecto es el último con matrícula y la comparación el anterior
 *   - un establecimiento cerrado deja de contar desde el año siguiente al cierre y no distorsiona la variación
 *   - un jardín que entra no cuenta como crecimiento: la variación usa solo los presentes en ambos años
 *   - la asistencia se pondera por matrícula y un año sin dato lo dice (lastYear) en vez de mostrar otro
 *   - «sin dato» (null) no se suma como 0, pero una matrícula 0 sí es un valor
 *   - los filtros, el treemap y las comunas dependen de los datos, no de listas fijas
 */
import { describe, it, expect } from 'vitest';
import {
  buildModel, defaultYears, eesOf, totalsWithDelta, headline, evolution, jardinesFrom, byComunaBars, byGroup,
  urbanRural, heatmap, changes, scatter, groupOf, treemapLayout, sourceInfo, DEFAULT_FILTER, JARDIN,
} from '@/lib/enrollment';

// A y B: escuelas en 2025 y 2026. C: cerrada en 2025 (sin punto 2026). D: jardín que entra en 2025.
// E: escuela nueva en 2026. F: sin alumnos en 2026 (0 real).
const DATASET = {
  establishments: [
    { rbd: 'A', name: 'Escuela A', comuna: 'FRESIA', area_type: 'URBANO', category: '4. ESCUELA COMPLETA', status: 'active', closed_year: null },
    { rbd: 'B', name: 'Escuela B', comuna: 'FRESIA', area_type: 'RURAL', category: '6. RURAL MULTIGRADO', status: 'active', closed_year: null },
    { rbd: 'C', name: 'Escuela C', comuna: 'FRUTILLAR', area_type: 'URBANO', category: '4. ESCUELA COMPLETA', status: 'closed', closed_year: 2025 },
    { rbd: 'D', name: 'Jardín D', comuna: 'FRUTILLAR', area_type: 'URBANO', category: '2. J. INFANTIL - S. CUNA', status: 'active', closed_year: null },
    { rbd: 'E', name: 'Escuela E', comuna: 'FRUTILLAR', area_type: 'RURAL', category: '9. COLEGIO', status: 'active', closed_year: null },
    { rbd: 'F', name: 'Escuela F', comuna: 'FRESIA', area_type: 'RURAL', category: '6. RURAL MULTIGRADO', status: 'active', closed_year: null },
  ],
  points: [
    { rbd: 'A', year: 2024, enrollment: 90 },
    { rbd: 'A', year: 2025, enrollment: 100, attendance: 0.9, attendance_as_of: '', teachers: null },
    { rbd: 'A', year: 2026, enrollment: 110, enrollment_as_of: '2026-03', attendance: null, teachers: 8 },
    { rbd: 'B', year: 2025, enrollment: 20, attendance: 0.8 },
    { rbd: 'B', year: 2026, enrollment: 10, enrollment_as_of: '2026-03', teachers: 2 },
    { rbd: 'C', year: 2024, enrollment: 60 },
    { rbd: 'C', year: 2025, enrollment: 50, attendance: 0.7 },
    { rbd: 'D', year: 2025, enrollment: 30 },
    { rbd: 'D', year: 2026, enrollment: 40, enrollment_as_of: '2026-03' },
    { rbd: 'E', year: 2026, enrollment: 70, enrollment_as_of: '2026-03', teachers: 5 },
    { rbd: 'F', year: 2025, enrollment: 5 },
    { rbd: 'F', year: 2026, enrollment: 0, enrollment_as_of: '2026-03' },
  ],
  years: [2024, 2025, 2026],
  indicators: {
    enrollment: { label: 'Matrícula', years: [2024, 2025, 2026] },
    attendance: { label: 'Asistencia', years: [2025] },
    teachers: { label: 'Docentes', years: [2026] },
    assistants: { label: 'Asistentes', years: [] },
  },
};
const M = buildModel(DATASET);
const F = DEFAULT_FILTER;

describe('FE23: años', () => {
  it('FE23-A: el año por defecto es el último con matrícula y se compara con el anterior', () => {
    expect(defaultYears(M)).toEqual({ year: 2026, compare: 2025 });
    expect(defaultYears(buildModel({ ...DATASET, indicators: { enrollment: { years: [2025] } } }))).toEqual({ year: 2025, compare: null });
    expect(defaultYears(buildModel(null))).toEqual({ year: null, compare: null });
  });

  it('FE23-B: un cerrado cuenta hasta su año de cierre y deja de contar después', () => {
    expect(eesOf(M, F, 2025).map((e) => e.rbd)).toEqual(['A', 'B', 'C', 'D', 'F']);
    expect(eesOf(M, F, 2026).map((e) => e.rbd)).toEqual(['A', 'B', 'D', 'E', 'F']);                 // C ya no; E entra
    // aunque tuviera un punto 2026, un establecimiento cerrado en 2025 no cuenta en 2026
    const withStray = buildModel({ ...DATASET, points: [...DATASET.points, { rbd: 'C', year: 2026, enrollment: 9 }] });
    expect(eesOf(withStray, F, 2026).map((e) => e.rbd)).not.toContain('C');
  });
});

describe('FE23: comparación entre años', () => {
  it('FE23-C: la variación usa solo los presentes en ambos años', () => {
    const t = totalsWithDelta(M, F, 2026, 2025);
    expect(t.value).toBe(230);                                  // 110 + 10 + 40 + 70 + 0
    expect(t.matched).toBe(4);                                  // A, B, D, F
    expect(t.base).toBe(155);                                   // 100 + 20 + 30 + 5
    expect(t.delta).toBe(160 - 155);                            // A 110 + B 10 + D 40 + F 0 = 160 (E nueva no suma)
    expect(t.pct).toBeCloseTo((5 / 155) * 100);
    expect(t.entered).toBe(1);                                  // E
    expect(t.left).toBe(1);                                     // C
  });

  it('FE23-D: sin año de comparación no hay variación', () => {
    expect(totalsWithDelta(M, F, 2026, null)).toMatchObject({ delta: null, pct: null });
  });

  it('FE23-E: los jardines se pueden excluir y el salto de 2025 se marca', () => {
    const noJ = { ...F, jardines: false };
    expect(eesOf(M, noJ, 2026).map((e) => e.rbd)).toEqual(['A', 'B', 'E', 'F']);
    expect(totalsWithDelta(M, noJ, 2026, 2025).delta).toBe((110 + 10 + 0) - (100 + 20 + 5));
    expect(jardinesFrom(M, F)).toBe(2025);
    expect(jardinesFrom(M, noJ)).toBeNull();
  });
});

describe('FE23: indicadores de cabecera', () => {
  it('FE23-F: la asistencia se pondera por matrícula y declara su cobertura', () => {
    const h = headline(M, F, 2025, null);
    // A 0,9 × 100, B 0,8 × 20, C 0,7 × 50 → (90 + 16 + 35) / 170
    expect(h.attendance.value).toBeCloseTo(141 / 170);
    expect(h.attendance).toMatchObject({ n: 3, total: 5 });
  });

  it('FE23-G: un año sin asistencia lo dice y apunta al último año con dato', () => {
    const h = headline(M, F, 2026, 2025);
    expect(h.attendance.value).toBeNull();
    expect(h.attendance.lastYear).toBe(2025);
    expect(h.teachers).toMatchObject({ value: 15, n: 3, total: 5, lastYear: null });
    expect(headline(M, F, 2025, null).teachers.lastYear).toBe(2026);
  });

  it('FE23-H: «sin dato» no es 0, pero una matrícula 0 sí es un valor', () => {
    const h = headline(M, F, 2026, 2025);
    expect(h.establishments).toEqual({ value: 5, withEnrollment: 4 });                // F tiene 0 alumnos y cuenta como establecimiento
    expect(h.teachers.value).toBe(15);                                                 // A 8 + B 2 + E 5; D y F sin dato no suman 0
    expect(h.enrollment.asOf).toEqual(['2026-03']);
    expect(headline(M, F, 2025, null).enrollment.asOf).toEqual([]);                    // año completo
  });

  it('FE23-I: los filtros acotan los indicadores', () => {
    const h = headline(M, { ...F, comuna: 'FRESIA', area: 'r' }, 2026, 2025);
    expect(h.enrollment.value).toBe(10);                                               // B (F tiene 0)
    expect(h.establishments.value).toBe(2);
  });
});

describe('FE23: gráficos', () => {
  it('FE23-J: la evolución solo incluye años con establecimientos y no mezcla los cerrados', () => {
    const e = evolution(M, F, false);
    expect(e.series[0].points).toEqual([{ year: 2024, value: 150 }, { year: 2025, value: 205 }, { year: 2026, value: 230 }]);
    const byC = evolution(M, F, true);
    expect(byC.series.map((s) => s.key)).toEqual(M.comunas);
    expect(byC.series.find((s) => s.key === 'FRESIA').points.map((p) => p.value)).toEqual([90, 125, 120]);
  });

  it('FE23-K: las comunas salen de los datos, ordenadas por matrícula', () => {
    expect(M.comunas).toEqual(['FRESIA', 'FRUTILLAR']);                                // 110+10+0 = 120 frente a 40+70 = 110
    const bars = byComunaBars(M, F, 2026, 2025);
    expect(bars.find((b) => b.comuna === 'FRUTILLAR')).toMatchObject({ value: 110, count: 2 });
  });

  it('FE23-L: tipos, urbano/rural y mapa de calor', () => {
    expect(byGroup(M, F, 2026).map((g) => [g.name, g.count, g.value])).toEqual([
      ['Escuela completa', 1, 110], ['Colegio', 1, 70], ['Jardín y sala cuna', 1, 40], ['Rural multigrado', 2, 10],
    ]);
    const ur = urbanRural(M, F, 2026).find((r) => r.comuna === 'FRUTILLAR');
    expect(ur).toMatchObject({ urban: 40, rural: 70, total: 110 });
    const heat = heatmap(M, F, 2026, 'ee');
    expect(heat.groups).toEqual([0, 1, 4, 5]);
    expect(heat.rows.find((r) => r.comuna === 'FRESIA').cells.map((c) => c.value)).toEqual([1, 0, 0, 2]);
    expect(heat.max).toBe(2);
  });

  it('FE23-M: la tabla de cambios y la dispersión', () => {
    expect(changes(M, F, 2026, 2025).map((c) => [c.rbd, c.delta]).sort()).toEqual([['A', 10], ['B', -10], ['D', 10], ['F', -5]]);
    expect(changes(M, F, 2026, null)).toEqual([]);
    const pts = scatter(M, { ...F, comuna: 'FRESIA' }, 2025);
    expect(pts.map((p) => [p.rbd, p.on])).toEqual([['A', true], ['B', true], ['C', false]]);     // C no es de FRESIA: se atenúa
  });
});

describe('FE23: apoyos', () => {
  it('FE23-N: los tipos se agrupan por el número de la categoría', () => {
    expect(groupOf('7. LICEO POLITÉCNICO')).toBe(2);
    expect(groupOf('2. J. INFANTIL - S. CUNA')).toBe(JARDIN);
    expect(groupOf('3. JARDIN INFANTIL')).toBe(JARDIN);
    expect(groupOf('')).toBe(8);
    expect(groupOf('99. NUEVA')).toBe(8);
  });

  it('FE23-O: el treemap reparte el área en proporción al valor y llena el rectángulo', () => {
    const items = [{ index: 0, value: 60 }, { index: 1, value: 30 }, { index: 2, value: 10 }, { index: 3, value: 0 }];
    const lay = treemapLayout(items, 100, 50);
    expect(Object.keys(lay).sort()).toEqual(['0', '1', '2']);                           // el 0 no ocupa espacio
    const areas = Object.fromEntries(Object.entries(lay).map(([k, [, , w, h]]) => [k, w * h]));
    expect(areas[0]).toBeCloseTo(0.6 * 5000); expect(areas[1]).toBeCloseTo(0.3 * 5000); expect(areas[2]).toBeCloseTo(0.1 * 5000);
  });

  it('FE23-P: el origen del dato declara cobertura, cortes y lo que aún no se registra', () => {
    const att = sourceInfo('attendance', M, F, 2026);
    expect(att.title).toBe('Asistencia 2026');
    expect(Object.fromEntries(att.rows)['Cálculo']).toMatch(/sin datos/i);
    const enr = Object.fromEntries(sourceInfo('enrollment', M, F, 2026).rows);
    expect(enr['Corte']).toBe('2026-03');
    expect(enr['Años con dato']).toBe('2024, 2025, 2026');
    expect(enr['Registro de cargas']).toMatch(/D36/);
  });
});
