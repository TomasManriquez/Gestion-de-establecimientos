import React from 'react';
import { Plus, AlertTriangle } from 'lucide-react';
import { METRIC_SECTIONS, PERFORMANCE_CATEGORIES, toInput, storedValueProblem } from '@/lib/metricFields';

/**
 * Pestaña «Estadísticas» del editor de ficha. Edita un año a la vez; EditFicha guarda el estado
 * (`edits`) y al guardar envía un PUT por año con solo los campos cambiados (buildMetricPayloads).
 */
export default function EditFichaEstadisticas({ metrics, years, selectedYear, onSelectYear, onAddYear, edits, errors, onEdit }) {
  const saved = metrics.find((m) => m.year === selectedYear) ?? {};
  const yearEdits = edits[selectedYear] ?? {};
  const yearErrors = errors[selectedYear] ?? {};
  const nextYear = years.length ? Math.max(...years) + 1 : new Date().getFullYear();

  const valueOf = (field) => (field.key in yearEdits ? yearEdits[field.key] : toInput(field, saved[field.key]));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold text-slate-400 uppercase mr-1">Año</span>
        {years.map((y) => (
          <button
            key={y}
            type="button"
            onClick={() => onSelectYear(y)}
            aria-pressed={y === selectedYear}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              y === selectedYear ? 'bg-sky-600 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {y}
            {edits[y] && Object.keys(edits[y]).length > 0 && <span className="ml-1" aria-label="con cambios sin guardar">•</span>}
          </button>
        ))}
        <button
          type="button"
          onClick={() => onAddYear(nextYear)}
          className="flex items-center gap-1 px-3 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 font-bold rounded-lg text-xs transition-all"
        >
          <Plus size={14} />
          Agregar {nextYear}
        </button>
      </div>

      <p className="text-xs text-slate-500">
        Los porcentajes se escriben de 0 a 100. Solo se guardan los campos que cambies; dejar un campo vacío no borra el dato.
      </p>

      {selectedYear == null && (
        <p className="text-sm text-slate-500">Este establecimiento no tiene estadísticas registradas. Agrega un año para empezar.</p>
      )}

      {selectedYear != null && METRIC_SECTIONS.map((section) => (
        <fieldset key={section.title} className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-3">
          <legend className="text-xs font-bold text-slate-600 uppercase tracking-wider px-1">{section.title}</legend>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {section.fields.map((field) => {
              const id = `metric-${selectedYear}-${field.key}`;
              const error = yearErrors[field.key];
              const stored = field.key in yearEdits ? null : storedValueProblem(field, saved[field.key]);
              const inputClass = `w-full px-3 py-2 bg-white border rounded-lg text-sm focus:outline-none font-sans ${
                error ? 'border-rose-400 focus:border-rose-500' : 'border-slate-200 focus:border-sky-500'
              }`;
              return (
                <div key={field.key} className="space-y-1">
                  <label htmlFor={id} className="text-xs font-semibold text-slate-500">{field.label}</label>
                  {field.kind === 'category' ? (
                    <select id={id} value={valueOf(field)} onChange={(e) => onEdit(selectedYear, field.key, e.target.value)} className={inputClass}>
                      <option value="">Sin dato</option>
                      {PERFORMANCE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  ) : (
                    <input
                      id={id}
                      type="text"
                      inputMode={field.kind === 'int' ? 'numeric' : 'decimal'}
                      value={valueOf(field)}
                      onChange={(e) => onEdit(selectedYear, field.key, e.target.value)}
                      aria-invalid={Boolean(error)}
                      aria-describedby={error || stored ? `${id}-msg` : undefined}
                      className={inputClass}
                    />
                  )}
                  {error && <p id={`${id}-msg`} className="text-xs font-semibold text-rose-600">{error}</p>}
                  {!error && stored && (
                    <p id={`${id}-msg`} className="flex items-center gap-1 text-xs font-semibold text-amber-700">
                      <AlertTriangle size={12} /> Valor cargado fuera de rango: {stored.toLowerCase()}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
