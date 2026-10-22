import React from 'react';
import { WifiOff, MessageCircle } from 'lucide-react';
import { STATUS_2030, OTHER_TYPES, labelOf, hasOther, withoutInternet, isExpired, whatsappLink, shortDate } from '@/lib/connectivity';

/** Par etiqueta / valor de una fila de datos. */
function Field({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="font-semibold text-slate-800 text-sm break-words">{children || '-'}</dd>
    </div>
  );
}

function Block({ title, badge, children }) {
  return (
    <section className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
      <h3 className="flex items-center gap-2 text-base font-bold text-slate-800 font-outfit">
        {title}
        {badge}
      </h3>
      {children}
    </section>
  );
}

/**
 * Conectividad en la ficha: muestra solo los bloques con datos (2030, BAM, otro tipo) y un aviso
 * cuando el establecimiento queda sin internet.
 */
export default function ConectividadFicha({ connectivity }) {
  const conn = connectivity ?? {};
  const p = conn.program_2030 ?? {};
  const bam = conn.bam ?? [];
  const other = conn.other ?? {};
  const noInternet = withoutInternet(conn);
  const expired = isExpired(other.expiry_date);
  const wa = whatsappLink(other.support_whatsapp);

  return (
    <div className="space-y-5">
      {noInternet && (
        <div role="status" className="flex items-center gap-3 p-4 rounded-2xl border border-rose-200 bg-rose-50 text-rose-800">
          <WifiOff size={20} className="shrink-0" />
          <div>
            <p className="font-bold">Sin internet</p>
            <p className="text-sm">{noInternet}</p>
          </div>
        </div>
      )}

      {p.enabled && (
        <Block
          title="Conectividad 2030 (Telsur)"
          badge={p.status && (
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${p.status === 'sin_internet' ? 'bg-rose-100 text-rose-800'
              : p.status === 'pendiente_instalacion' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}`}>
              {labelOf(STATUS_2030, p.status)}
            </span>
          )}
        >
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Field label="Red wifi (SSID)">{conn.ssid}</Field>
            <Field label="Clave wifi">{conn.ssid_password}</Field>
            <Field label="Velocidad de bajada">{p.download_speed && `${p.download_speed} Mbps`}</Field>
            <Field label="Fecha de testeo">{shortDate(p.test_date)}</Field>
          </dl>
        </Block>
      )}

      {bam.length > 0 && (
        <Block title="Banda ancha móvil (BAM)" badge={<span className="text-xs font-semibold text-slate-400">{bam.length}</span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs text-slate-400 border-b border-slate-100">
                  <th className="py-2 pr-4 font-semibold">Operador</th>
                  <th className="py-2 pr-4 font-semibold">N° / cantidad</th>
                  <th className="py-2 pr-4 font-semibold">IMEI</th>
                  <th className="py-2 pr-4 font-semibold">Asignado a</th>
                  <th className="py-2 pr-4 font-semibold">OC</th>
                  <th className="py-2 font-semibold">Término</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {bam.map((b, idx) => {
                  const end = shortDate(b.end);
                  return (
                    <tr key={idx}>
                      <td className="py-2 pr-4 font-semibold text-slate-800">{b.carrier || '-'}</td>
                      <td className="py-2 pr-4">{b.number || (b.qty ? `${b.qty} equipos` : '-')}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{b.imei || '-'}</td>
                      <td className="py-2 pr-4">{b.holder || '-'}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{b.oc || '-'}</td>
                      <td className="py-2">
                        {end || '-'}
                        {isExpired(end) && <span className="ml-2 text-xs font-bold text-rose-700">vencido</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Block>
      )}

      {hasOther(other) && (
        <Block
          title="Otro tipo de conexión"
          badge={other.type && <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-sky-100 text-sky-800">{labelOf(OTHER_TYPES, other.type)}</span>}
        >
          <dl className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Field label="Proveedor">{other.provider}</Field>
            <Field label="Velocidad">{other.download_speed && `${other.download_speed} Mbps`}</Field>
            <Field label="OC">{other.oc}</Field>
            <Field label="Vencimiento">
              {other.expiry_date && (
                <>
                  {other.expiry_date}
                  {expired && <span className="ml-2 text-xs font-bold text-rose-700">vencido</span>}
                </>
              )}
            </Field>
            <Field label="Soporte">
              {wa && (
                <a href={wa} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sky-700 hover:underline">
                  <MessageCircle size={14} /> {other.support_whatsapp}
                </a>
              )}
            </Field>
          </dl>
        </Block>
      )}
    </div>
  );
}
