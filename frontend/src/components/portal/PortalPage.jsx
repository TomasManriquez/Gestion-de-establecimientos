import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ExternalLink, Library, Lock, Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { can, isIamAdmin } from '@/lib/access';
import { parseApiError, portalApi, unitsApi } from '@/lib/api';

const SELECT = 'h-10 w-full rounded-md border border-input bg-background px-3 text-base';
const LEVELS = [
  [0, 'Nivel 0 · Público: lo ve toda la organización'],
  [1, 'Nivel 1 · Interno: lo ve toda la organización'],
  [2, 'Nivel 2 · Sensible: queda restringido'],
];

/** El aviso del nivel 2 (ADR-021 §5): quién lo ve, a quién pedir acceso y el límite del control. */
function RestrictedNotice({ saved }) {
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

/** Temas en orden de lectura: cada tema seguido de sus subtemas, con la etiqueta «Tema › Subtema». */
function flattenTopics(topics) {
  const roots = topics.filter((t) => !t.parent_id);
  return roots.flatMap((r) => [
    { ...r, label: r.name },
    ...topics.filter((t) => t.parent_id === r._id).map((s) => ({ ...s, label: `${r.name} › ${s.name}` })),
  ]);
}

function TopicForm({ open, onOpenChange, topics, onSaved }) {
  const [name, setName] = useState('');
  const [parent, setParent] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { if (open) { setName(''); setParent(''); setError(''); } }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setPending(true);
    try {
      await portalApi.createTopic({ name: name.trim(), parent_id: parent || null });
      toast.success('Tema creado');
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(parseApiError(err).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className="max-w-md">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Nuevo tema</DialogTitle>
            <DialogDescription>El tema ordena los recursos; no da ni quita permisos. Hay dos niveles: tema y subtema.</DialogDescription>
          </DialogHeader>
          {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="topic-name">Nombre</FieldLabel>
              <Input id="topic-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} className="text-base" />
            </Field>
            <Field>
              <FieldLabel htmlFor="topic-parent">Dentro de</FieldLabel>
              <select id="topic-parent" value={parent} onChange={(e) => setParent(e.target.value)} className={SELECT}>
                <option value="">Ninguno (tema principal)</option>
                {topics.filter((t) => !t.parent_id).map((t) => <option key={t._id} value={t._id}>{t.name}</option>)}
              </select>
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={pending}>{pending && <Spinner data-icon="inline-start" />}Crear</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResourceForm({ open, onOpenChange, topics, units, resource, admin, onSaved }) {
  const editing = Boolean(resource);
  const blank = { title: '', url: '', description: '', topic_id: '', unit_id: '', catastro_level: 1, visibility: 'org' };
  const [form, setForm] = useState(blank);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState({ message: '', fields: {} });
  const [saved, setSaved] = useState(null);       // recurso recién guardado: si es restringido, se muestra el aviso

  useEffect(() => {
    if (open) {
      setForm(resource ? { ...blank, ...resource, description: resource.description ?? '', unit_id: resource.unit_id ?? '' } : blank);
      setError({ message: '', fields: {} });
      setSaved(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, resource]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    const body = {
      title: form.title.trim(), url: form.url.trim(), description: form.description.trim() || null,
      topic_id: form.topic_id, unit_id: form.unit_id || null, catastro_level: Number(form.catastro_level),
    };
    if (editing && admin) body.visibility = form.visibility;
    setPending(true);
    try {
      const result = editing ? await portalApi.updateResource(resource._id, body) : await portalApi.createResource(body);
      onSaved();
      if (!editing && result.visibility === 'restricted') setSaved(result);   // el aviso se lee antes de cerrar
      else { toast.success(editing ? 'Recurso actualizado' : 'Recurso registrado'); onOpenChange(false); }
    } catch (err) {
      const { message, fields } = parseApiError(err);
      setError({ message, fields });
    } finally {
      setPending(false);
    }
  };

  if (saved) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Recurso registrado</DialogTitle></DialogHeader>
          <RestrictedNotice saved />
          <DialogFooter><Button type="button" onClick={() => onOpenChange(false)}>Entendido</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className="max-h-[90dvh] max-w-lg overflow-y-auto">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{editing ? 'Editar recurso' : 'Registrar recurso'}</DialogTitle>
            <DialogDescription>Un enlace a un tablero, planilla o aplicación del SLEP.</DialogDescription>
          </DialogHeader>
          {error.message && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
          <FieldGroup>
            <Field data-invalid={Boolean(error.fields.title) || undefined}>
              <FieldLabel htmlFor="res-title">Título</FieldLabel>
              <Input id="res-title" value={form.title} onChange={set('title')} required maxLength={120} className="text-base" />
              <FieldError>{error.fields.title}</FieldError>
            </Field>
            <Field data-invalid={Boolean(error.fields.url) || undefined}>
              <FieldLabel htmlFor="res-url">Enlace</FieldLabel>
              <Input id="res-url" type="url" value={form.url} onChange={set('url')} required maxLength={500} placeholder="https://…" className="text-base" />
              <FieldError>{error.fields.url}</FieldError>
            </Field>
            <Field>
              <FieldLabel htmlFor="res-desc">Descripción (opcional)</FieldLabel>
              <Input id="res-desc" value={form.description} onChange={set('description')} maxLength={500} className="text-base" />
            </Field>
            <Field>
              <FieldLabel htmlFor="res-topic">Tema</FieldLabel>
              <select id="res-topic" value={form.topic_id} onChange={set('topic_id')} required className={SELECT}>
                <option value="" disabled>Elige un tema</option>
                {flattenTopics(topics).map((t) => <option key={t._id} value={t._id}>{t.label}</option>)}
              </select>
            </Field>
            <Field>
              <FieldLabel htmlFor="res-unit">Unidad responsable (opcional)</FieldLabel>
              <select id="res-unit" value={form.unit_id} onChange={set('unit_id')} className={SELECT}>
                <option value="">Sin unidad</option>
                {units.map((u) => <option key={u._id} value={u._id}>{u.name}</option>)}
              </select>
            </Field>
            <Field>
              <FieldLabel htmlFor="res-level">Nivel de sensibilidad (catastro)</FieldLabel>
              <select id="res-level" value={form.catastro_level} onChange={set('catastro_level')} className={SELECT}>
                {LEVELS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
              </select>
            </Field>
            {Number(form.catastro_level) === 2 && <RestrictedNotice />}
            {editing && admin && (
              <Field>
                <FieldLabel htmlFor="res-vis">Visibilidad</FieldLabel>
                <select id="res-vis" value={form.visibility} onChange={set('visibility')} className={SELECT}>
                  <option value="org">Toda la organización</option>
                  <option value="restricted">Restringido (solo con acceso concedido)</option>
                </select>
              </Field>
            )}
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={pending}>{pending && <Spinner data-icon="inline-start" />}Guardar</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Portal de recursos del SLEP (ADR-021). Lista lo que la persona puede ver, ordenado por tema. Ocultar lo
 * restringido es del servidor: aquí solo se muestra lo que llega. Editar/borrar lo decide el servidor
 * (administrador o quien lo registró); los botones son comodidad.
 */
export default function PortalPage({ currentUser }) {
  const admin = isIamAdmin(currentUser);
  const canWrite = can(currentUser, 'datos', 'write');
  const me = currentUser?._id ?? currentUser?.id;

  const [topics, setTopics] = useState(null);
  const [resources, setResources] = useState([]);
  const [units, setUnits] = useState([]);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');          // '' = todos
  const [resourceForm, setResourceForm] = useState({ open: false, resource: null });
  const [topicForm, setTopicForm] = useState(false);
  const [toDelete, setToDelete] = useState(null);

  const load = useCallback(async () => {
    try {
      const [t, r] = await Promise.all([portalApi.topics(), portalApi.resources()]);
      setTopics(t);
      setResources(r);
      setError('');
    } catch (err) {
      setError(parseApiError(err).message);
    }
  }, []);

  useEffect(() => {
    load();
    unitsApi.list().then((u) => setUnits(Array.isArray(u) ? u : (u?.items ?? []))).catch(() => {});
  }, [load]);

  const byId = useMemo(() => Object.fromEntries(flattenTopics(topics ?? []).map((t) => [t._id, t])), [topics]);
  const roots = (topics ?? []).filter((t) => !t.parent_id);
  const rootOfSelected = byId[selected]?.parent_id ?? selected;

  // Elegir un tema muestra también los recursos de sus subtemas.
  const shown = resources.filter((r) => {
    if (!selected) return true;
    const t = byId[r.topic_id];
    return r.topic_id === selected || t?.parent_id === selected;
  });

  const remove = async () => {
    try {
      await portalApi.removeResource(toDelete._id);
      toast.success('Recurso eliminado');
      setToDelete(null);
      await load();
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  const chip = (active) => `rounded-full border px-3 py-1.5 text-sm font-semibold transition-colors ${
    active ? 'border-slep-navy bg-slep-navy text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`;

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold font-outfit text-slate-800"><Library aria-hidden="true" />Portal de recursos</h1>
          <p className="mt-1 text-sm text-slate-500">Tableros, planillas y aplicaciones del SLEP, ordenados por tema.</p>
        </div>
        <div className="flex gap-2">
          {admin && <Button type="button" variant="outline" onClick={() => setTopicForm(true)}><Plus data-icon="inline-start" />Nuevo tema</Button>}
          {canWrite && <Button type="button" onClick={() => setResourceForm({ open: true, resource: null })}><Plus data-icon="inline-start" />Registrar recurso</Button>}
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      {topics && (
        <nav aria-label="Temas" className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <button type="button" className={chip(!selected)} aria-pressed={!selected} onClick={() => setSelected('')}>Todos</button>
            {roots.map((t) => (
              <button key={t._id} type="button" className={chip(rootOfSelected === t._id)} aria-pressed={rootOfSelected === t._id}
                onClick={() => setSelected(t._id)}>{t.name}</button>
            ))}
          </div>
          {byId[rootOfSelected] && (topics.some((t) => t.parent_id === rootOfSelected)) && (
            <div className="flex flex-wrap gap-2 pl-3">
              {topics.filter((t) => t.parent_id === rootOfSelected).map((s) => (
                <button key={s._id} type="button" className={chip(selected === s._id)} aria-pressed={selected === s._id}
                  onClick={() => setSelected(s._id)}>{s.name}</button>
              ))}
            </div>
          )}
        </nav>
      )}

      {topics && (shown.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">
          {topics.length === 0 ? 'Aún no hay temas. Un administrador debe crearlos primero.' : 'No hay recursos en este tema.'}
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((r) => (
            <li key={r._id} className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-2">
                <a href={r.url} target="_blank" rel="noopener noreferrer"
                  className="flex min-w-0 items-center gap-1.5 font-bold text-slate-800 hover:underline">
                  <span className="truncate">{r.title}</span><ExternalLink size={14} aria-hidden="true" className="shrink-0" />
                </a>
                {r.visibility === 'restricted' && <Badge variant="secondary" className="shrink-0"><Lock data-icon="inline-start" />Restringido</Badge>}
              </div>
              {r.description && <p className="text-sm text-slate-600">{r.description}</p>}
              <p className="text-xs text-slate-500">{r.platform} · {byId[r.topic_id]?.label ?? 'Sin tema'}</p>
              {(admin || (canWrite && r.created_by === me)) && (
                <div className="mt-auto flex justify-end gap-1">
                  <Button type="button" variant="ghost" size="icon" aria-label={`Editar ${r.title}`}
                    onClick={() => setResourceForm({ open: true, resource: r })}><Pencil size={16} /></Button>
                  <Button type="button" variant="ghost" size="icon" aria-label={`Eliminar ${r.title}`}
                    onClick={() => setToDelete(r)}><Trash2 size={16} /></Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      ))}

      <TopicForm open={topicForm} onOpenChange={setTopicForm} topics={topics ?? []} onSaved={load} />
      <ResourceForm open={resourceForm.open} resource={resourceForm.resource} topics={topics ?? []} units={units} admin={admin}
        onOpenChange={(open) => setResourceForm((s) => ({ ...s, open }))} onSaved={load} />

      <AlertDialog open={Boolean(toDelete)} onOpenChange={(open) => !open && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar este recurso?</AlertDialogTitle>
            <AlertDialogDescription>
              {toDelete && `«${toDelete.title}» dejará de aparecer en el portal y se borrarán los accesos concedidos sobre él. El enlace externo no se toca.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={remove}>Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
