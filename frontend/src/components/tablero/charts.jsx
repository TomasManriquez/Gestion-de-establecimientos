import React from 'react';
import { fmt, dec, signPct, signInt, titleCase, GROUPS, treemapLayout } from '@/lib/enrollment';

const BLUE = '#0872b8';
const NAVY = '#0b4f8a';
const GREEN = '#4c9a2a';
const DOWN = '#c22e44';
const UP = '#2f7d14';
const DIM = '#c3d7e6';

const pctColor = (v) => (v < 0 ? DOWN : UP);

function nice(v) {
  const p = 10 ** Math.floor(Math.log10(v));
  const q = v / p;
  return (q <= 1 ? 1 : q <= 2 ? 2 : q <= 5 ? 5 : 10) * p;
}

/** Evolución de la matrícula: total o una línea por comuna. `markFrom` marca el año en que entran los jardines. */
export function EvolutionChart({ data, byComuna, markFrom, ariaLabel }) {
  const [hover, setHover] = React.useState(null);   // {key, i} del punto bajo el mouse o con el foco (vista por comuna)
  const { years, series } = data;
  if (!years.length) return <p className="py-10 text-center text-sm text-slep-muted">Sin datos para este filtro.</p>;
  const W = 700; const x0 = 96; const x1 = 590;
  const yb = byComuna ? 270 : 190;            // base del gráfico: la vista por comuna es más alta para separar las líneas
  const X = (i) => (years.length === 1 ? (x0 + x1) / 2 : x0 + (i * (x1 - x0)) / (years.length - 1));
  const vals = series.flatMap((s) => s.points.map((p) => p.value)).filter((v) => v > 0);
  let lo = Math.min(...vals); let hi = Math.max(...vals); let step;
  if (byComuna) { lo = 0; step = nice(Math.max(hi, 4) / 4); hi = Math.ceil(hi / step) * step; }
  else { step = nice(Math.max(hi - lo, hi * 0.08, 4) / 3); lo = Math.max(0, Math.floor(lo / step) * step - step); hi = Math.ceil(hi / step) * step; }
  if (hi <= lo) hi = lo + step;
  const Y = (v) => yb - ((v - lo) / (hi - lo)) * (yb - 24);
  const grid = []; for (let v = lo; v <= hi + 0.001 && grid.length < 7; v += step) grid.push(v);
  const path = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'} ${X(i).toFixed(1)} ${Y(p.value).toFixed(1)}`).join(' ');
  const total = !byComuna ? series[0].points : null;
  const markIdx = markFrom != null ? years.indexOf(markFrom) : -1;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${yb + 32}`} role="img" aria-label={ariaLabel} className="block overflow-visible">
      {grid.map((v) => (
        <g key={v}>
          <line x1={x0} x2={x1} y1={Y(v)} y2={Y(v)} stroke="#e3edf5" />
          <text x={x0 - 10} y={Y(v) + 4} textAnchor="end" fontSize="12" fill="#5b6f82">{fmt(v)}</text>
        </g>
      ))}
      {markIdx > 0 && (
        <g>
          <line x1={X(markIdx)} x2={X(markIdx)} y1={12} y2={yb} stroke="#94a9bb" strokeDasharray="3 4" />
          <text x={X(markIdx) + 6} y={yb - 6} fontSize="12" fill="#5b6f82">jardines desde {markFrom}</text>
        </g>
      )}
      {total && <path className="tb-line" d={`${path(total)} L ${X(total.length - 1)} ${yb} L ${X(0)} ${yb} Z`} fill="#168fd5" fillOpacity="0.1" />}
      {series.map((s) => (
        <path key={s.key} className="tb-line" d={path(s.points)} fill="none" strokeWidth={byComuna && s.selected && s.key !== 'total' ? 3 : 2.5}
          stroke={byComuna && !s.selected ? DIM : BLUE} strokeLinejoin="round" strokeLinecap="round" />
      ))}
      {total && total.map((p, i) => (
        <g key={p.year}>
          <circle className="tb-dot" cx={X(i)} cy={Y(p.value)} r="5" fill={BLUE} stroke="#fff" strokeWidth="2.5" />
          <text className="tb-dot" x={X(i)} y={Y(p.value) - 12} textAnchor="middle" fontSize="13.5" fontWeight="700" fill="#17324d">{fmt(p.value)}</text>
        </g>
      ))}
      {byComuna && series.map((s) => s.points.map((p, i) => {
        const on = hover && hover.key === s.key && hover.i === i;
        return (
          <g key={`${s.key}-${p.year}`}>
            <circle className="tb-dot" cx={X(i)} cy={Y(p.value)} r={on ? 6 : s.selected ? 4 : 3} fill={s.selected ? BLUE : DIM} stroke="#fff" strokeWidth="2" />
            {/* zona de captura más grande que el punto, también con teclado */}
            <circle data-point={`${s.key}|${p.year}`} cx={X(i)} cy={Y(p.value)} r="12" fill="transparent" tabIndex={0}
              onMouseEnter={() => setHover({ key: s.key, i })} onMouseLeave={() => setHover(null)}
              onFocus={() => setHover({ key: s.key, i })} onBlur={() => setHover(null)}>
              <title>{`${titleCase(s.label)} · ${p.year}: ${fmt(p.value)}`}</title>
            </circle>
          </g>
        );
      }))}
      {byComuna && hover && (() => {
        const s = series.find((z) => z.key === hover.key);
        const p = s?.points[hover.i];
        if (!p) return null;
        const w = 132; const h = 40;
        const cx = Math.min(Math.max(X(hover.i), x0 + w / 2), x1 + 60 - w / 2);
        const above = Y(p.value) - h - 12 > 4;
        const ty = above ? Y(p.value) - h - 12 : Y(p.value) + 14;
        return (
          <g pointerEvents="none" role="presentation">
            <rect x={cx - w / 2} y={ty} width={w} height={h} rx="8" fill="#17324d" fillOpacity="0.96" />
            <text x={cx} y={ty + 16} textAnchor="middle" fontSize="11.5" fill="#cfe3f3">{titleCase(s.label)} · {p.year}</text>
            <text x={cx} y={ty + 33} textAnchor="middle" fontSize="14" fontWeight="700" fill="#fff">{fmt(p.value)}</text>
          </g>
        );
      })()}
      {byComuna && series.map((s) => {
        const last = s.points[s.points.length - 1];
        return <text key={s.key} x={600} y={Y(last.value) + 4} fontSize="12" fontWeight="700" fill={s.selected ? '#17324d' : '#94a9bb'}>{titleCase(s.label)}</text>;
      })}
      {years.map((y, i) => <text key={y} x={X(i)} y={yb + 24} textAnchor="middle" fontSize="13" fill="#5b6f82">{y}</text>)}
    </svg>
  );
}

/** Barras horizontales por comuna: cada fila filtra la comuna. */
export function ComunaBars({ rows, selected, onSelect, showDelta }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="flex flex-1 flex-col justify-center gap-0.5">
      {rows.map((r) => (
        <button key={r.comuna} type="button" aria-pressed={selected === r.comuna} onClick={() => onSelect(selected === r.comuna ? null : r.comuna)}
          className={`tb-row tb-press flex min-h-12 flex-col gap-1.5 rounded-xl px-2.5 py-2 text-left ${selected === r.comuna ? 'bg-sky-50' : ''}`}>
          <span className="flex w-full items-baseline justify-between gap-2 text-[15px]">
            <span className="font-bold">{titleCase(r.comuna)}</span>
            <span>
              <b>{fmt(r.value)}</b>
              {showDelta && r.pct != null && <span className="ml-1.5 text-[13px] font-bold" style={{ color: pctColor(r.pct) }}>{signPct(r.pct)}</span>}
            </span>
          </span>
          <span className="block h-2 w-full overflow-hidden rounded bg-slate-200">
            <span className="tb-bar block h-full rounded" style={{ width: `${(r.value / max) * 100}%`, background: selected == null ? '#168fd5' : selected === r.comuna ? BLUE : DIM }} />
          </span>
        </button>
      ))}
    </div>
  );
}

const TW = 240; const TH = 100;   // el layout trabaja en un rectángulo de 240 × 100; aquí se pasa a porcentajes
const pctBox = (q) => ({ x: (q[0] / TW) * 100, y: (q[1] / TH) * 100, w: (q[2] / TW) * 100, h: (q[3] / TH) * 100 });
const labelled = (b) => b.w > 16 && b.h > 26;

const TREE_SHADES = ['#0b4f8a', '#0872b8', '#1f5f8f', '#2d7bb3', '#86c4e9', '#a9d6f0', '#c6e4f6', '#e3f1fa', '#ced9e3'];

/** Mapa de árbol por tipo de establecimiento: cada bloque filtra el tipo. */
export function GroupTreemap({ groups, selected, onSelect }) {
  const lay = treemapLayout(groups, TW, TH);
  const total = groups.reduce((a, g) => a + g.value, 0) || 1;
  return (
    <>
      <div className="relative h-64 w-full">
        {groups.map((g) => {
          if (!lay[g.index]) return null;
          const { x, y, w, h } = pctBox(lay[g.index]);
          const dark = g.index < 4;
          return (
            <button key={g.index} type="button" aria-pressed={selected === g.index} onClick={() => onSelect(selected === g.index ? null : g.index)}
              aria-label={`${g.name}: ${fmt(g.value)} alumnos`}
              className="tb-tile absolute box-border flex flex-col gap-px overflow-hidden rounded-lg border-2 border-white p-2 text-left"
              style={{ left: `${x}%`, top: `${y}%`, width: `${w}%`, height: `${h}%`, background: TREE_SHADES[g.index], color: dark ? '#fff' : '#17324d', opacity: selected == null || selected === g.index ? 1 : 0.35 }}>
              {labelled({ w, h }) && (<><span className="text-sm font-bold leading-tight">{g.name}</span><span className="text-sm">{fmt(g.value)} · {Math.round((g.value / total) * 100)} %</span></>)}
            </button>
          );
        })}
      </div>
      <TreemapFootnote groups={groups} lay={lay} />
    </>
  );
}

function TreemapFootnote({ groups, lay }) {
  const small = groups.filter((g) => lay[g.index] && !labelled(pctBox(lay[g.index])));
  return <p className="text-[13px] text-slep-muted">{small.length ? `Sin etiqueta: ${small.map((g) => `${g.name.toLowerCase()} ${fmt(g.value)}`).join(' · ')}` : 'Toca un bloque para filtrar por tipo.'}</p>;
}

/** Proporción 100 % urbano/rural por comuna: cada segmento filtra el área. */
export function UrbanRuralShare({ rows, area, comuna, onArea }) {
  return (
    <div className="flex flex-1 flex-col justify-center gap-2.5">
      <div className="flex gap-3.5 text-[13.5px] font-bold">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: NAVY }} />Urbano</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: GREEN }} />Rural</span>
      </div>
      {rows.map((r) => {
        const pu = r.total ? (r.urban / r.total) * 100 : 0;
        const pr = r.total ? 100 - pu : 0;
        return (
          <div key={r.comuna} className="grid grid-cols-[6.5rem_minmax(0,1fr)] items-center gap-3 transition-opacity duration-200" style={{ opacity: comuna == null || comuna === r.comuna ? 1 : 0.4 }}>
            <span className="text-[15px] font-bold">{titleCase(r.comuna)}</span>
            <div className="flex h-9 gap-[3px]">
              <button type="button" aria-label={`${r.comuna}, urbano: ${fmt(r.urban)} alumnos`} onClick={() => onArea(area === 'u' ? 'all' : 'u')}
                className="tb-bar tb-press min-w-0 overflow-hidden whitespace-nowrap rounded-l-lg rounded-r-[3px] px-2.5 text-left text-[13.5px] font-bold text-white"
                style={{ width: `${pu}%`, background: NAVY, opacity: area === 'r' ? 0.3 : 1 }}>{pu >= 14 ? `${Math.round(pu)} %` : ''}</button>
              <button type="button" aria-label={`${r.comuna}, rural: ${fmt(r.rural)} alumnos`} onClick={() => onArea(area === 'r' ? 'all' : 'r')}
                className="tb-bar tb-press min-w-0 overflow-hidden whitespace-nowrap rounded-l-[3px] rounded-r-lg px-2.5 text-right text-[13.5px] font-bold text-white"
                style={{ width: `${pr}%`, background: GREEN, opacity: area === 'u' ? 0.3 : 1 }}>{pr >= 14 ? `${Math.round(pr)} %` : ''}</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const HEAT = (t) => (t <= 0.15 ? '#e3f1fa' : t <= 0.3 ? '#bfe0f3' : t <= 0.55 ? '#86c4e9' : t <= 0.8 ? '#0872b8' : '#0b4f8a');

/** Mapa de calor comuna × tipo: cada celda selecciona esa combinación. */
export function HeatMap({ heat, measure, comuna, tipo, onPick }) {
  const cols = `7.5rem repeat(${heat.groups.length}, minmax(0, 1fr))`;
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-[38rem] flex-col gap-1">
        <div className="grid items-end gap-1" style={{ gridTemplateColumns: cols }}>
          <span />
          {heat.groups.map((g) => <span key={g} className="pb-1 text-center text-[12.5px] font-bold leading-tight text-slep-muted">{GROUPS[g].short}</span>)}
        </div>
        {heat.rows.map((r) => (
          <div key={r.comuna} className="grid gap-1" style={{ gridTemplateColumns: cols }}>
            <span className="flex items-center text-[14.5px] font-bold">{titleCase(r.comuna)}</span>
            {r.cells.map((c) => {
              const t = c.value / heat.max;
              const same = comuna === r.comuna && tipo === c.group;
              const on = (comuna == null || comuna === r.comuna) && (tipo == null || tipo === c.group);
              return (
                <button key={c.group} type="button" aria-label={`${r.comuna}, ${GROUPS[c.group].name}: ${c.value}`} onClick={() => onPick(same ? null : r.comuna, same ? null : c.group)}
                  className="tb-cell min-h-10 rounded-md text-sm font-bold"
                  style={{ background: c.value ? HEAT(t) : '#f3f7fa', color: !c.value ? '#94a9bb' : t > 0.55 ? '#fff' : '#17324d', opacity: on ? 1 : 0.3 }}>
                  {c.value ? (measure === 'ee' ? c.value : fmt(c.value)) : '–'}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Establecimientos por tamaño. */
export function SizeHistogram({ bins }) {
  const max = Math.max(1, ...bins.map((b) => b.count));
  return (
    <>
      <div className="flex h-44 items-end gap-2 border-b border-slate-300 pt-2">
        {bins.map((b) => (
          <div key={b.label} className="flex h-full flex-1 flex-col items-end justify-end gap-1" style={{ alignItems: 'center' }}>
            <span className="text-[13.5px] font-bold">{b.count}</span>
            <div className="tb-col w-full rounded-t-[5px] bg-slep-sky" style={{ height: `${Math.round((b.count / max) * 130)}px` }} />
          </div>
        ))}
      </div>
      <div className="flex gap-2">{bins.map((b) => <span key={b.label} className="flex-1 text-center text-xs text-slep-muted">{b.label}</span>)}</div>
      <span className="text-center text-[13px] text-slep-muted">alumnos por establecimiento</span>
    </>
  );
}

/** Tamaño (escala logarítmica) frente a asistencia. Los establecimientos fuera del filtro se atenúan. */
export function SizeAttendanceScatter({ points }) {
  const L0 = Math.log10(2); const L1 = Math.log10(1000);
  const X = (m) => 40 + ((Math.log10(m) - L0) / (L1 - L0)) * 520;
  const Y = (a) => 200 - ((Math.min(1, Math.max(0.7, a)) - 0.7) / 0.3) * 184;
  return (
    <>
      <svg width="100%" viewBox="0 0 580 238" role="img" aria-label="Matrícula en escala logarítmica contra asistencia. Los establecimientos fuera del filtro se atenúan." className="block">
        {[[16, '100 %'], [77.3, '90 %'], [138.7, '80 %'], [200, '70 %']].map(([y, t]) => (
          <g key={t}><line x1="40" x2="560" y1={y} y2={y} stroke={y === 200 ? '#c9dceb' : '#e3edf5'} /><text x="34" y={y + 4} textAnchor="end" fontSize="12.5" fill="#5b6f82">{t}</text></g>
        ))}
        {points.map((p) => (
          <circle key={p.rbd} className="tb-dot" cx={X(p.enrollment)} cy={Y(p.attendance)} r="5.5" fill={p.rural ? GREEN : NAVY} stroke="#fff" strokeWidth="1.2" style={{ opacity: p.on ? 0.85 : 0.08 }}>
            <title>{`${p.name}: ${fmt(p.enrollment)} alumnos, asistencia ${dec(p.attendance * 100)} %`}</title>
          </circle>
        ))}
        {[[2, 40], [10, 174], [50, 308], [200, 424], [800, 540]].map(([v, x]) => <text key={v} x={x} y="220" textAnchor="middle" fontSize="12.5" fill="#5b6f82">{v}</text>)}
        <text x="300" y="236" textAnchor="middle" fontSize="12.5" fill="#5b6f82">matrícula (escala logarítmica)</text>
      </svg>
      <div className="flex gap-4 text-[13.5px] font-bold">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: NAVY }} />Urbano</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: GREEN }} />Rural</span>
      </div>
    </>
  );
}

/** Tabla de cambios entre dos años; ordenada por el mayor descenso o el mayor aumento. */
export function ChangesTable({ rows, year, compare, sort }) {
  const sorted = [...rows].sort((a, b) => (sort === 'baja' ? a.delta - b.delta : b.delta - a.delta)).slice(0, 8);
  if (!sorted.length) return <p className="py-8 text-center text-sm text-slep-muted">Elige un año de comparación para ver los cambios.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] text-left text-[14.5px]">
        <thead>
          <tr className="border-b-2 border-slep-sky text-[13px] text-slep-muted">
            <th scope="col" className="px-2 py-2 font-bold">Establecimiento</th>
            <th scope="col" className="px-2 py-2 font-bold">Comuna</th>
            <th scope="col" className="px-2 py-2 text-right font-bold">{compare}</th>
            <th scope="col" className="px-2 py-2 text-right font-bold">{year}</th>
            <th scope="col" className="px-2 py-2 text-right font-bold">Δ</th>
            <th scope="col" className="px-2 py-2 text-right font-bold">Asistencia</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.rbd} className="tb-row border-b border-slate-200">
              <td className="max-w-[18rem] truncate px-2 py-2 font-bold" title={r.name}>{r.name}</td>
              <td className="px-2 py-2 text-slep-muted">{titleCase(r.comuna)}</td>
              <td className="px-2 py-2 text-right">{fmt(r.before)}</td>
              <td className="px-2 py-2 text-right">{fmt(r.now)}</td>
              <td className="px-2 py-2 text-right font-bold" style={{ color: r.delta === 0 ? '#5b6f82' : pctColor(r.delta) }}>{r.delta === 0 ? '0' : signInt(r.delta)}</td>
              <td className="px-2 py-2 text-right text-slep-muted">{r.attendance != null ? `${dec(r.attendance * 100)} %` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
