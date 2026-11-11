import React, { useEffect, useRef, useState } from 'react';
import { ImagePlus, Lock, X } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { parseApiError, portalApi } from '@/lib/api';
import { shrinkImage } from '@/lib/image';
import { LEVELS } from './ResourceCard';

const SELECT = 'h-11 w-full rounded-lg border border-[#c9dceb] bg-white px-3 text-base';
const REQUIRES = [
  'Sin exigencias. Se recomienda usar la plantilla de TI.',
  'Se publica al registrar. Autoevaluación, datos ficticios mientras se construye, dueño y autor nombrados.',
  'Queda restringido: solo lo ven las personas autorizadas. Requiere autenticación institucional y un suplente.',
];

/** El aviso del nivel 2 (ADR-021 §5): quién lo ve, a quién pedir acceso y el límite del control. */
export function RestrictedNotice({ saved }) {
  return (
    <Alert>
      <Lock aria-hidden="true" />
      <AlertDescription>
        {saved ? 'Este recurso quedó restringido. ' : 'Un recurso de nivel 2 queda restringido. '}
        Solo las personas autorizadas pueden verlo: solicita a un administrador la autorización de quien deba verlo.
        Ojo: esto controla quién ve el <strong>enlace</strong>. Una planilla de Google o un informe de Power BI no quedan
        protegidos por el portal; quien tenga la URL entra según los permisos de esa plataforma.
      </AlertDescription>
    </Alert>
  );
}

const Section = ({ title, children }) => (
  <section className="flex flex-col gap-3">
    <h3 className="text-lg font-bold text-[#0b3a66]">{title}</h3>
    {children}
  </section>
);
const Label = ({ id, children }) => <label htmlFor={id} className="flex flex-col gap-1 text-[13.5px] text-[#5b6f82]">{children}</label>;

/**
 * Formulario de registro como panel lateral (diseño V4). La carátula es opcional: sirve cuando el enlace solo
 * muestra un login. Se reduce en el navegador antes de subirla y se sube después de guardar el recurso.
 */
export default function ResourceDrawer({ open, onOpenChange, topics, units, resource, topicId, admin, onSaved }) {
  const editing = Boolean(resource);
  const blank = { title: '', url: '', description: '', topic_id: topicId ?? '', unit_id: '', catastro_level: 1, visibility: 'org' };
  const [form, setForm] = useState(blank);
  const [cover, setCover] = useState(null);            // { blob, url } elegida ahora; null = sin cambio
  const [dropCover, setDropCover] = useState(false);   // quitar la carátula que ya tiene
  const [pending, setPending] = useState(false);
  const [error, setError] = useState({ message: '', fields: {} });
  const [saved, setSaved] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setForm(resource ? { ...blank, ...resource, description: resource.description ?? '', unit_id: resource.unit_id ?? '' } : blank);
    setCover(null);
    setDropCover(false);
    setError({ message: '', fields: {} });
    setSaved(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, resource, topicId]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const level = Number(form.catastro_level);

  const pick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    try {
      const blob = await shrinkImage(file);
      setCover({ blob, url: URL.createObjectURL(blob) });
      setDropCover(false);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    const body = {
      title: form.title.trim(), url: form.url.trim(), description: form.description.trim() || null,
      topic_id: form.topic_id, unit_id: form.unit_id || null, catastro_level: level,
    };
    if (editing && admin) body.visibility = form.visibility;
    setPending(true);
    try {
      let result = editing ? await portalApi.updateResource(resource._id, body) : await portalApi.createResource(body);
      try {
        if (cover) result = await portalApi.setCover(result._id, cover.blob);
        else if (dropCover && resource?.has_cover) result = await portalApi.removeCover(result._id);
      } catch (err) {      // el recurso ya quedó guardado: solo la imagen falló
        toast.error(`El proyecto se guardó, pero la carátula no: ${parseApiError(err).message}`);
      }
      onSaved();
      if (!editing && result.visibility === 'restricted') setSaved(result);   // el aviso se lee antes de cerrar
      else { toast.success(editing ? 'Proyecto actualizado' : 'Proyecto registrado'); onOpenChange(false); }
    } catch (err) {
      const { message, fields } = parseApiError(err);
      setError({ message, fields });
    } finally {
      setPending(false);
    }
  };

  const shownCover = cover?.url ?? null;
  const hasOld = editing && resource.has_cover && !dropCover && !cover;
  const lv = LEVELS[level] ?? LEVELS[0];

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent
        className="!fixed !left-auto !right-0 !top-0 flex !h-dvh !max-h-dvh !w-full !max-w-[600px] !translate-x-0 !translate-y-0 flex-col !gap-0 !rounded-none !p-0 [&>button.absolute]:hidden"
        aria-describedby="drawer-desc">
        {saved ? (
          <div className="flex flex-1 flex-col gap-4 p-6">
            <DialogTitle>Proyecto registrado</DialogTitle>
            <DialogDescription id="drawer-desc" className="sr-only">Aviso sobre el recurso restringido</DialogDescription>
            <RestrictedNotice saved />
            <Button type="button" className="self-end" onClick={() => onOpenChange(false)}>Entendido</Button>
          </div>
        ) : (
          <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
            <div className="flex items-start gap-3 border-b border-[#e3edf4] px-6 pb-4 pt-5">
              <div className="flex flex-1 flex-col gap-1 text-left">
                <span className="text-[12.5px] font-bold uppercase tracking-[0.12em] text-[#5b6f82]">Formulario de registro de soluciones digitales</span>
                <DialogTitle className="text-2xl font-bold leading-tight">{editing ? 'Editar proyecto' : 'Registrar proyecto'}</DialogTitle>
                <DialogDescription id="drawer-desc" className="text-[14.5px] text-[#5b6f82]">Publica el enlace y deja el catastro hecho en el mismo paso.</DialogDescription>
              </div>
              <button type="button" aria-label="Cerrar" onClick={() => !pending && onOpenChange(false)}
                className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-[#f3f9fd]"><X size={16} aria-hidden="true" /></button>
            </div>

            <div className="flex flex-1 flex-col gap-7 overflow-y-auto px-6 pb-7 pt-5">
              {error.message && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}

              <Section title="Enlace">
                <Label id="res-url">Dirección (https://…)
                  <Input id="res-url" type="url" value={form.url} onChange={set('url')} required maxLength={500} placeholder="https://app.powerbi.com/…" className="h-11 text-base" aria-label="Enlace" />
                  {error.fields.url && <span className="text-sm text-[#b42335]">{error.fields.url}</span>}
                </Label>
                <Label id="res-title">Título
                  <Input id="res-title" value={form.title} onChange={set('title')} required maxLength={120} className="h-11 text-base" aria-label="Título" />
                  {error.fields.title && <span className="text-sm text-[#b42335]">{error.fields.title}</span>}
                </Label>
                <Label id="res-desc">Descripción breve (va en la tarjeta)
                  <Input id="res-desc" value={form.description} onChange={set('description')} maxLength={500} placeholder="Para qué sirve, en una línea" className="h-11 text-base" aria-label="Descripción" />
                </Label>
                <Label id="res-topic">Bloque del portal
                  <select id="res-topic" value={form.topic_id} onChange={set('topic_id')} required className={SELECT} aria-label="Tema">
                    <option value="" disabled>Elige un tema</option>
                    {topics.map((t) => <option key={t._id} value={t._id}>{t.label}</option>)}
                  </select>
                </Label>
              </Section>

              <Section title="Carátula (opcional)">
                <p className="text-[13.5px] text-[#5b6f82]">Útil cuando el enlace solo muestra un login: sube una captura del tablero. PNG, JPEG o WebP; se reduce sola.</p>
                <div className="flex flex-wrap items-center gap-4 rounded-xl border border-[#d7e8f1] bg-[#f8fbfd] p-3">
                  <div className="grid h-24 w-40 shrink-0 place-items-center overflow-hidden rounded-lg border border-[#d7e8f1] bg-white text-[#8fb3d6]">
                    {shownCover
                      ? <img src={shownCover} alt="Vista previa de la carátula" className="size-full object-cover" />
                      : <ImagePlus size={28} aria-hidden="true" />}
                  </div>
                  <div className="flex flex-col items-start gap-2">
                    <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={pick} className="sr-only" aria-label="Archivo de la carátula" />
                    <Button type="button" variant="outline" onClick={() => fileRef.current?.click()}>
                      {shownCover || hasOld ? 'Cambiar imagen' : 'Elegir imagen'}
                    </Button>
                    {(shownCover || hasOld) && (
                      <button type="button" className="text-sm font-bold text-[#b42335]" onClick={() => { setCover(null); setDropCover(true); }}>Quitar carátula</button>
                    )}
                    {hasOld && <span className="text-[13px] text-[#5b6f82]">Ya tiene una carátula guardada.</span>}
                  </div>
                </div>
              </Section>

              <Section title="Catastro">
                <Label id="res-level">Nivel de sensibilidad (catastro)
                  <select id="res-level" value={form.catastro_level} onChange={set('catastro_level')} className={SELECT} aria-label="Nivel de sensibilidad (catastro)">
                    {LEVELS.map((l, i) => <option key={l.label} value={i}>{l.label}</option>)}
                  </select>
                </Label>
                <Label id="res-unit">Unidad responsable (opcional)
                  <select id="res-unit" value={form.unit_id} onChange={set('unit_id')} className={SELECT} aria-label="Unidad responsable">
                    <option value="">Sin unidad</option>
                    {units.map((u) => <option key={u._id} value={u._id}>{u.name}</option>)}
                  </select>
                </Label>
                {editing && admin && (
                  <Label id="res-vis">Visibilidad
                    <select id="res-vis" value={form.visibility} onChange={set('visibility')} className={SELECT} aria-label="Visibilidad">
                      <option value="org">Toda la organización</option>
                      <option value="restricted">Restringido (solo con acceso concedido)</option>
                    </select>
                  </Label>
                )}
                {level === 2 && <RestrictedNotice />}
              </Section>
            </div>

            <div className="flex flex-col gap-3 border-t border-[#e3edf4] bg-[#fbfdfe] px-6 pb-5 pt-4">
              <div className="flex items-start gap-3">
                <span className="shrink-0 rounded-[10px] px-3 py-1.5 text-[15px] font-bold" style={{ background: lv.bg, color: lv.ink }}>{lv.label}</span>
                <span className="text-[14.5px]">{REQUIRES[level]}</span>
              </div>
              <div className="flex justify-end gap-2.5">
                <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>Cancelar</Button>
                <Button type="submit" disabled={pending}>{pending && <Spinner data-icon="inline-start" />}Guardar</Button>
              </div>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
