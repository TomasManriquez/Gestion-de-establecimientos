import React, { useEffect, useState } from 'react';
import { ExternalLink, Lock, Pencil, Trash2 } from 'lucide-react';
import { portalApi } from '@/lib/api';

// Colores por plataforma (los del diseño V4); `soft` tiñe las barras de la miniatura.
const PLATFORM = {
  'Power BI': { color: '#f2c811', ink: '#17324d', soft: '#fbeeb0' },
  'Google Sheets': { color: '#188038', ink: '#fff', soft: '#cde9d6' },
  'Google Docs': { color: '#1a73e8', ink: '#fff', soft: '#d2e3fc' },
  'Google Drive': { color: '#1a73e8', ink: '#fff', soft: '#d2e3fc' },
  'Looker Studio': { color: '#4285f4', ink: '#fff', soft: '#d6e4fd' },
  SharePoint: { color: '#036c70', ink: '#fff', soft: '#c6e4e5' },
};
const OTHER = { color: '#5b6f82', ink: '#fff', soft: '#dfe6ec' };

export const LEVELS = [
  { label: 'Nivel 0 · Personal', bg: '#eef2f5', ink: '#3d5366' },
  { label: 'Nivel 1 · De unidad', bg: '#e6f1f9', ink: '#0b4f8a' },
  { label: 'Nivel 2 · Alto', bg: '#fde8eb', ink: '#9b1c2e' },
];

const covers = new Map();      // `${id}:${updated_at}` → URL del blob; una sola descarga por versión

/** Carátula subida por quien registró el recurso. Si falla la descarga se queda la miniatura de la plataforma. */
function Cover({ resource, fallback }) {
  const key = `${resource._id}:${resource.updated_at}`;
  const [src, setSrc] = useState(covers.get(key) ?? null);
  useEffect(() => {
    if (!resource.has_cover || covers.has(key)) { setSrc(covers.get(key) ?? null); return undefined; }
    let alive = true;
    portalApi.cover(resource._id).then((blob) => {
      const url = URL.createObjectURL(blob);
      covers.set(key, url);
      if (alive) setSrc(url);
    }).catch(() => {});
    return () => { alive = false; };
  }, [key, resource.has_cover, resource._id]);
  return src
    ? <img src={src} alt="" className="block aspect-video w-full rounded-t-lg border border-b-0 border-[#d7e8f1] bg-white object-cover" />
    : fallback;
}

/** Miniatura genérica: ventana de navegador con barras del color de la plataforma (diseño V4). */
function Thumb({ platform, host }) {
  const p = PLATFORM[platform] ?? OTHER;
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-t-lg border border-b-0 border-[#d7e8f1] bg-white transition-transform duration-200 group-hover:-translate-y-0.5">
      <div className="flex items-center gap-1.5 border-b border-[#e3edf4] bg-[#f6f9fb] px-2 py-1.5">
        {[0, 1, 2].map((i) => <span key={i} className="size-1.5 rounded-full bg-[#c9d6e1]" />)}
        <span className="ml-1.5 min-w-0 flex-1 truncate rounded-md bg-white px-2 py-0.5 text-[11.5px] text-[#5b6f82]">{host}</span>
      </div>
      <div className="flex h-[22px] items-center px-2.5 text-[11.5px] font-bold" style={{ background: p.color, color: p.ink }}>{platform}</div>
      <div className="flex h-16 items-end gap-1.5 px-3 pt-2.5">
        {[40, 75, 55, 90].map((h, i) => (
          <span key={h} className="flex-1 rounded-t-[3px]" style={{ height: `${h}%`, background: i % 2 ? p.color : p.soft, opacity: i % 2 ? 0.85 : 1 }} />
        ))}
        <span className="flex flex-[2] flex-col gap-1.5 self-start pl-1.5">
          {[100, 70, 85].map((w) => <span key={w} className="h-[7px] rounded bg-[#e3edf4]" style={{ width: `${w}%` }} />)}
        </span>
      </div>
    </div>
  );
}

const hostOf = (url) => { try { return new URL(url).hostname; } catch { return url; } };

export default function ResourceCard({ resource: r, unitName, manage, onEdit, onDelete }) {
  const level = LEVELS[r.catastro_level] ?? LEVELS[0];
  return (
    <article className="group flex flex-col overflow-hidden rounded-[14px] border border-[#d7e8f1] bg-white transition-shadow duration-200 hover:shadow-[0_10px_26px_rgba(23,50,77,0.09)]">
      <a href={r.url} target="_blank" rel="noopener noreferrer" className="flex flex-1 flex-col text-[#17324d] no-underline">
        <div className="overflow-hidden bg-[#eef4f9] px-3 pt-3">
          <Cover resource={r} fallback={<Thumb platform={r.platform} host={hostOf(r.url)} />} />
        </div>
        <div className="flex flex-col gap-1 px-3.5 pb-2.5 pt-3">
          <span className="flex items-start gap-2">
            <span className="flex-1 text-[17px] font-bold text-[#0b4f8a]">{r.title}</span>
            <ExternalLink size={15} role="img" aria-label="Se abre fuera de la plataforma" className="mt-[3px] shrink-0 text-[#5b6f82]" />
          </span>
          <span className="text-sm text-[#5b6f82]">{[r.platform, unitName].filter(Boolean).join(' · ')}</span>
          {r.description && <span className="text-[13.5px] text-[#5b6f82]">{r.description}</span>}
        </div>
      </a>
      <div className="flex flex-wrap items-center gap-1.5 px-3.5 pb-3">
        <span className="rounded-[10px] px-2 py-0.5 text-[12.5px] font-bold" style={{ background: level.bg, color: level.ink }}>{level.label}</span>
        {r.visibility === 'restricted' && (
          <span className="inline-flex items-center gap-1 rounded-[10px] bg-[#fff3d6] px-2 py-0.5 text-[12.5px] font-bold text-[#7a5200]"><Lock size={12} aria-hidden="true" />Restringido</span>
        )}
        {manage && (
          <span className="ml-auto flex gap-1.5">
            <button type="button" onClick={onEdit} aria-label={`Editar ${r.title}`}
              className="inline-flex min-h-8 items-center gap-1 rounded-lg border border-[#c9dceb] bg-white px-2.5 text-[13.5px] font-bold text-[#0872b8] active:scale-[0.97]"><Pencil size={14} aria-hidden="true" />Editar</button>
            <button type="button" onClick={onDelete} aria-label={`Eliminar ${r.title}`}
              className="inline-flex min-h-8 items-center gap-1 rounded-lg border border-[#f0c2c8] bg-white px-2.5 text-[13.5px] font-bold text-[#b42335] active:scale-[0.97]"><Trash2 size={14} aria-hidden="true" />Quitar</button>
          </span>
        )}
      </div>
    </article>
  );
}
