import React from 'react';
import { Plus, Trash2, WifiOff } from 'lucide-react';
import { STATUS_2030, OTHER_TYPES, EMPTY_BAM, withoutInternet } from '@/lib/connectivity';

const input = 'w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-sky-500 font-sans';

function Text({ id, label, value, onChange, type = 'text', placeholder, inputMode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-semibold text-slate-500">{label}</label>
      <input id={id} type={type} value={value ?? ''} placeholder={placeholder} inputMode={inputMode}
        onChange={(e) => onChange(e.target.value)} className={input} />
    </div>
  );
}

function Choice({ id, label, value, options, onChange }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-semibold text-slate-500">{label}</label>
      <select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)} className={input}>
        <option value="">Sin dato</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

/**
 * Pestaña «Conectividad» del editor: los tres bloques con todos sus campos. La ficha solo muestra
 * los que tengan datos, así que dejar un bloque vacío equivale a «no tiene».
 */
export default function EditConectividad({ conn, onChange }) {
  const set2030 = (key, value) => onChange({ ...conn, program_2030: { ...conn.program_2030, [key]: value } });
  const setOther = (key, value) => onChange({ ...conn, other: { ...conn.other, [key]: value } });
  const setBam = (idx, key, value) => onChange({ ...conn, bam: conn.bam.map((b, i) => (i === idx ? { ...b, [key]: value } : b)) });
  const noInternet = withoutInternet(conn);
  const p = conn.program_2030;

  return (
    <div className="space-y-6">
      {noInternet && (
        <p role="status" className="flex items-center gap-2 p-3 rounded-xl bg-rose-50 border border-rose-200 text-sm font-semibold text-rose-700">
          <WifiOff size={16} /> Con estos datos la ficha mostrará «Sin internet»: {noInternet.toLowerCase()}
        </p>
      )}

      <fieldset className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-4">
        <legend className="text-xs font-bold text-slate-600 uppercase tracking-wider px-1">Conectividad 2030 (Telsur)</legend>
        <label className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700 cursor-pointer">
          <input type="checkbox" checked={p.enabled} onChange={(e) => set2030('enabled', e.target.checked)} className="size-4" />
          El establecimiento está en el programa 2030
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Choice id="c2030-status" label="Estado" value={p.status} options={STATUS_2030} onChange={(v) => set2030('status', v)} />
          <Text id="c2030-speed" label="Velocidad (Mbps)" value={p.download_speed} inputMode="decimal" onChange={(v) => set2030('download_speed', v)} />
          <Text id="c2030-test" label="Fecha de testeo" type="date" value={(p.test_date || '').slice(0, 10)} onChange={(v) => set2030('test_date', v)} />
          <Text id="c2030-ssid" label="Red wifi (SSID)" value={conn.ssid} onChange={(v) => onChange({ ...conn, ssid: v })} />
          <Text id="c2030-pass" label="Clave wifi" value={conn.ssid_password} onChange={(v) => onChange({ ...conn, ssid_password: v })} />
        </div>
        <p className="text-xs text-slate-500">Si el Starlink lo financia el 2030, va aquí como estado. Si es independiente, va en «Otro tipo de conexión».</p>
      </fieldset>

      <fieldset className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-4">
        <legend className="text-xs font-bold text-slate-600 uppercase tracking-wider px-1">Banda ancha móvil (BAM)</legend>
        {conn.bam.length === 0 && <p className="text-sm text-slate-500">Sin BAM. La ficha no mostrará este bloque.</p>}
        {conn.bam.map((b, idx) => (
          <div key={idx} className="p-3 bg-white rounded-lg border border-slate-200 flex flex-col md:flex-row gap-3 md:items-end">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 flex-1">
              <Text id={`bam-${idx}-carrier`} label="Operador" value={b.carrier} onChange={(v) => setBam(idx, 'carrier', v)} />
              <Text id={`bam-${idx}-number`} label="N° BAM" value={b.number} onChange={(v) => setBam(idx, 'number', v)} />
              <Text id={`bam-${idx}-qty`} label="Cantidad" value={b.qty ?? ''} inputMode="numeric"
                onChange={(v) => setBam(idx, 'qty', v === '' || !/^\d+$/.test(v) ? null : Number(v))} />
              <Text id={`bam-${idx}-imei`} label="IMEI" value={b.imei} onChange={(v) => setBam(idx, 'imei', v)} />
              <Text id={`bam-${idx}-device`} label="Equipo" value={b.device} onChange={(v) => setBam(idx, 'device', v)} />
              <Text id={`bam-${idx}-holder`} label="Asignado a" value={b.holder} onChange={(v) => setBam(idx, 'holder', v)} />
              <Text id={`bam-${idx}-oc`} label="OC" value={b.oc} onChange={(v) => setBam(idx, 'oc', v)} />
              <Text id={`bam-${idx}-end`} label="Término" type="date" value={(b.end || '').slice(0, 10)} onChange={(v) => setBam(idx, 'end', v)} />
            </div>
            <button type="button" aria-label={`Quitar BAM ${idx + 1}`} onClick={() => onChange({ ...conn, bam: conn.bam.filter((_, i) => i !== idx) })}
              className="p-2 text-rose-600 hover:bg-rose-50 rounded-lg transition-colors self-end">
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        <button type="button" onClick={() => onChange({ ...conn, bam: [...conn.bam, { ...EMPTY_BAM }] })}
          className="flex items-center gap-1 px-3 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 font-bold rounded-lg text-xs transition-all">
          <Plus size={14} /> Agregar BAM
        </button>
      </fieldset>

      <fieldset className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-4">
        <legend className="text-xs font-bold text-slate-600 uppercase tracking-wider px-1">Otro tipo de conexión</legend>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Text id="other-provider" label="Proveedor" value={conn.other.provider} onChange={(v) => setOther('provider', v)} />
          <Choice id="other-type" label="Tipo de conexión" value={conn.other.type} options={OTHER_TYPES} onChange={(v) => setOther('type', v)} />
          <Text id="other-speed" label="Velocidad (Mbps)" value={conn.other.download_speed} inputMode="decimal" onChange={(v) => setOther('download_speed', v)} />
          <Text id="other-oc" label="OC" value={conn.other.oc} onChange={(v) => setOther('oc', v)} />
          <Text id="other-expiry" label="Vencimiento" type="date" value={conn.other.expiry_date} onChange={(v) => setOther('expiry_date', v)} />
          <Text id="other-whatsapp" label="Soporte por WhatsApp" value={conn.other.support_whatsapp} placeholder="+569…" inputMode="tel"
            onChange={(v) => setOther('support_whatsapp', v)} />
        </div>
        <p className="text-xs text-slate-500">Déjalo vacío si no tiene. La ficha solo muestra este bloque con datos.</p>
      </fieldset>
    </div>
  );
}
