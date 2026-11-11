import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { can, isIamAdmin } from '@/lib/access';
import { parseApiError, portalApi, unitsApi } from '@/lib/api';
import ResourceCard from './ResourceCard';
import ResourceDrawer from './ResourceDrawer';

const SELECT = 'h-10 w-full rounded-md border border-input bg-background px-3 text-base';
// Un color por sección, los de la marca (diseño V4). Solo ordena la vista: no significa nada.
const ACCENTS = ['#168fd5', '#76c93b', '#f8c928', '#f24f63', '#36bce7', '#ff7f96'];
const norm = (t) => (t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Cada tema seguido de sus subtemas; el subtema se rotula «Tema › Subtema». */
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
            <DialogDescription>El tema ordena los proyectos; no da ni quita permisos. Hay dos niveles: tema y subtema.</DialogDescription>
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

/**
 * Portal de proyectos del SLEP (ADR-021), con el diseño de la iteración 4: una sección por tema, con su color,
 * y tarjetas con carátula. Ocultar lo restringido es del servidor: aquí solo se muestra lo que llega. Editar y
 * borrar lo decide el servidor (administrador o quien lo registró); los botones son comodidad.
 */
export default function PortalPage({ currentUser }) {
  const admin = isIamAdmin(currentUser);
  const canWrite = can(currentUser, 'datos', 'write');
  const me = currentUser?._id ?? currentUser?.id;

  const [topics, setTopics] = useState(null);
  const [resources, setResources] = useState([]);
  const [units, setUnits] = useState([]);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [drawer, setDrawer] = useState({ open: false, resource: null, topicId: '' });
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

  const flat = useMemo(() => flattenTopics(topics ?? []), [topics]);
  const unitName = (id) => units.find((u) => u._id === id)?.name;
  const needle = norm(q.trim());

  const sections = useMemo(() => flat.map((t, i) => ({
    ...t,
    accent: ACCENTS[i % ACCENTS.length],
    items: resources.filter((r) => r.topic_id === t._id
      && (!needle || norm(`${r.title} ${r.description} ${r.platform} ${unitName(r.unit_id)}`).includes(needle))),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  })), [flat, resources, needle, units]);

  // Con búsqueda solo salen las secciones que coinciden; sin ella, las vacías solo se muestran a quien puede registrar en ellas.
  const visible = sections.filter((s) => s.items.length > 0 || (!needle && canWrite));
  const manageable = (r) => admin || (canWrite && r.created_by === me);

  const remove = async () => {
    try {
      await portalApi.removeResource(toDelete._id);
      toast.success('Proyecto eliminado');
      setToDelete(null);
      await load();
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  const openDrawer = (resource = null, topicId = '') => setDrawer({ open: true, resource, topicId });

  return (
    <div className="flex max-w-[1240px] flex-col gap-5 font-sans text-[#17324d]">
      <div className="flex flex-wrap items-end justify-between gap-3.5">
        <div className="flex flex-col gap-1">
          <h1 className="text-[34px] font-bold leading-tight tracking-tight">Tableros y proyectos</h1>
          <span className="text-[15px] text-[#5b6f82]">{resources.length} proyectos en {flat.length} bloques</span>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <label className="relative flex min-w-[220px] flex-1 items-center sm:flex-none">
            <Search size={17} aria-hidden="true" className="pointer-events-none absolute left-3.5 text-[#5b6f82]" />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar proyecto o unidad" aria-label="Buscar proyecto o unidad"
              className="h-11 w-full rounded-xl border border-[#c9dceb] bg-white pl-[42px] pr-3.5 text-base sm:w-72" />
          </label>
          {admin && <Button type="button" variant="outline" className="h-11 rounded-xl" onClick={() => setTopicForm(true)}><Plus data-icon="inline-start" />Nuevo tema</Button>}
          {canWrite && <Button type="button" className="h-11 rounded-xl bg-[#0872b8] hover:bg-[#0b4f8a]" onClick={() => openDrawer()}><Plus data-icon="inline-start" />Registrar proyecto</Button>}
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      {topics && visible.map((s) => (
        <section key={s._id} aria-label={s.label} className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 border-b-[3px] pb-2" style={{ borderColor: s.accent }}>
            <h2 className="flex-1 text-[21px] font-bold">{s.label}</h2>
            <span className="text-sm text-[#5b6f82]">{s.items.length} {s.items.length === 1 ? 'proyecto' : 'proyectos'}</span>
          </div>
          <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
            {s.items.map((r) => (
              <ResourceCard key={r._id} resource={r} unitName={unitName(r.unit_id)} manage={manageable(r)}
                onEdit={() => openDrawer(r)} onDelete={() => setToDelete(r)} />
            ))}
            {canWrite && !needle && (
              <button type="button" onClick={() => openDrawer(null, s._id)}
                className="flex min-h-[120px] flex-col items-center justify-center gap-1.5 rounded-[14px] border-[1.5px] border-dashed border-[#b8d3e6] text-[15px] font-bold text-[#0872b8] active:scale-[0.97]">
                <Plus size={22} aria-hidden="true" />Registrar en este bloque
              </button>
            )}
          </div>
        </section>
      ))}

      {topics && visible.length === 0 && (
        <p className="rounded-[14px] border border-dashed border-[#c9dceb] bg-white p-7 text-center text-base text-[#5b6f82]">
          {needle ? `Ningún proyecto coincide con «${q.trim()}».` : (flat.length === 0 ? 'Aún no hay temas. Un administrador debe crearlos primero.' : 'Todavía no hay proyectos.')}
        </p>
      )}

      <TopicForm open={topicForm} onOpenChange={setTopicForm} topics={topics ?? []} onSaved={load} />
      <ResourceDrawer open={drawer.open} resource={drawer.resource} topicId={drawer.topicId} topics={flat} units={units} admin={admin}
        onOpenChange={(open) => setDrawer((d) => ({ ...d, open }))} onSaved={load} />

      <AlertDialog open={Boolean(toDelete)} onOpenChange={(open) => !open && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar este proyecto?</AlertDialogTitle>
            <AlertDialogDescription>
              {toDelete && `«${toDelete.title}» dejará de aparecer en el portal y se borrarán su carátula y los accesos concedidos sobre él. El enlace externo no se toca.`}
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
