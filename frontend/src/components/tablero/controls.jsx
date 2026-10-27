import React, { useEffect } from 'react';
import { Info, X } from 'lucide-react';

/** Tarjeta de un gráfico: título, contenido y, abajo, el acceso al origen del dato. */
export function ChartCard({ title, action, children, source, className = '' }) {
  return (
    <section className={`tb-card flex min-w-0 flex-col gap-3 rounded-2xl border border-slep-line bg-white px-5 pb-3 pt-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-slep-ink">{title}</h2>
        {action}
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {source}
    </section>
  );
}

/** Botón discreto «Origen del dato» al pie de cada gráfico. */
export function SourceLink({ label, onClick }) {
  return (
    <button type="button" onClick={onClick} className="tb-press inline-flex min-h-8 items-center gap-1.5 self-start rounded-md text-xs text-slep-muted hover:text-slep-blue">
      <Info size={14} aria-hidden="true" />
      <span className="underline-offset-2 hover:underline">{label}</span>
    </button>
  );
}

/** Selector segmentado con una pastilla que se desliza bajo la opción activa. */
export function Segmented({ options, value, onChange, label, size = 'md' }) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  const h = size === 'sm' ? 'h-8 text-[13px]' : 'h-9 text-sm';
  return (
    <div role="group" aria-label={label} className="relative inline-grid rounded-xl bg-slate-200/70 p-[3px]"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      <span aria-hidden="true" className="tb-pill absolute bottom-[3px] left-[3px] top-[3px] rounded-lg bg-white shadow"
        style={{ width: `calc((100% - 6px) / ${options.length})`, transform: `translateX(${index * 100}%)` }} />
      {options.map((o) => (
        <button key={String(o.value)} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}
          className={`relative z-10 px-3.5 font-bold transition-colors duration-200 ${h} ${o.value === value ? 'text-slep-ink' : 'text-slep-muted hover:text-slep-ink'}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Lista desplegable nativa con el estilo del tablero. */
export function SelectField({ id, label, value, onChange, options, className = '' }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <label htmlFor={id} className="text-sm font-bold text-slep-ink">{label}</label>
      <select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value)}
        className="h-10 min-w-[8.5rem] rounded-xl border border-slate-300 bg-slate-50 px-3 text-[15px] text-slep-ink transition-colors hover:border-slep-sky focus:border-slep-sky focus:outline-none">
        {options.map((o) => <option key={String(o.value)} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

/** Interruptor accesible (role switch) con perilla animada. */
export function Switch({ checked, onChange, children }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      className="tb-press inline-flex min-h-10 items-center gap-2.5 text-sm font-bold text-slep-ink">
      <span className={`relative h-6 w-10 shrink-0 rounded-full transition-colors duration-200 ${checked ? 'bg-slep-blue' : 'bg-slate-300'}`}>
        <span className={`absolute left-[3px] top-[3px] size-[18px] rounded-full bg-white shadow transition-transform duration-200 ${checked ? 'translate-x-4' : ''}`} />
      </span>
      {children}
    </button>
  );
}

/** Panel lateral «Origen del dato»: se cierra con la X, con Escape o con el botón. */
export function SourcePanel({ info, onClose }) {
  useEffect(() => {
    if (!info) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [info, onClose]);
  if (!info) return null;
  return (
    <aside aria-label="Origen del dato" className="tb-sheet fixed right-6 top-28 z-40 flex max-h-[calc(100vh-8rem)] w-[24rem] max-w-[calc(100vw-3rem)] flex-col gap-3 overflow-y-auto rounded-2xl border border-slate-300 border-t-4 border-t-slep-sky bg-white p-5 shadow-2xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-slep-blue">Origen del dato</p>
          <p className="text-xl font-bold text-slep-ink">{info.title}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Cerrar origen del dato" className="tb-press grid size-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-slep-ink hover:bg-slate-200">
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <dl className="flex flex-col gap-2.5">
        {info.rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2.5 text-[14.5px] leading-snug">
            <dt className="text-slep-muted">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
