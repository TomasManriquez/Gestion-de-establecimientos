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
// Un color por tema, los de la marca (diseño V5-C). Solo ordena la vista: no significa nada.
const ACCENTS = ['#168fd5', '#76c93b', '#f8c928', '#f24f63', '#36bce7', '#ff7f96'];
const GRID = 'grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]';
const norm = (t) => (t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

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
            <DialogDescription>El tema ordena los proyectos; no da ni quita permisos. Los proyectos van en los subtemas: crea primero el tema y dentro de él sus subtemas.</DialogDescription>
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
 * Portal de proyectos del SLEP (ADR-021), versión C del diseño: árbol de temas y subtemas a la izquierda y los
 * proyectos del subtema elegido a la derecha. Los proyectos viven en los subtemas; el tema principal agrupa.
 * Ocultar lo restringido es del servidor: aquí solo se muestra lo que llega. Editar y borrar lo decide el
 * servidor (administrador o quien lo registró); los botones son comodidad.
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
  const [selected, setSelected] = useState('');
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

  const unitName = (id) => units.find((u) => u._id === id)?.name;
  const needle = norm(q.trim());

  // Árbol: cada tema con su color y sus subtemas; `own` = proyectos de ese nodo, `total` = con los de sus subtemas.
  const tree = useMemo(() => {
    const matches = (r) => !needle || norm(`${r.title} ${r.description} ${r.platform} ${unitName(r.unit_id)}`).includes(needle);
    const own = (id) => resources.filter((r) => r.topic_id === id && matches(r));
    return (topics ?? []).filter((t) => !t.parent_id).map((root, i) => {
      const children = (topics ?? []).filter((t) => t.parent_id === root._id)
        .map((c) => ({ ...c, label: `${root.name} › ${c.name}`, accent: ACCENTS[i % ACCENTS.length], items: own(c._id) }));
      const items = own(root._id);
      return { ...root, label: root.name, accent: ACCENTS[i % ACCENTS.length], items, children,
        total: items.length + children.reduce((n, c) => n + c.items.length, 0) };
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topics, resources, needle, units]);

  const nodes = useMemo(() => tree.flatMap((t) => [t, ...t.children]), [tree]);
  // Por defecto: el primer subtema con proyectos (el tema principal suele quedar vacío).
  const activeId = nodes.some((n) => n._id === selected) ? selected : (nodes.find((n) => n.parent_id && n.items.length)?._id ?? nodes[0]?._id ?? '');
  const active = nodes.find((n) => n._id === activeId);
  const parentOf = active?.parent_id ? tree.find((t) => t._id === active.parent_id) : null;
  // Con búsqueda se ven todas las coincidencias, agrupadas por su subtema; sin ella, solo el nodo elegido.
  const shown = needle
    ? nodes.filter((n) => n.items.length > 0)
    : (active ? (active.children?.length ? [active, ...active.children] : [active]) : []);
  const total = resources.length;
  const subtopicCount = (topics ?? []).filter((t) => t.parent_id).length;
  // Solo se registra en subtemas (o en un tema sin subtemas): el tema que agrupa queda vacío.
  const topicOptions = tree.flatMap((t) => (t.children.length ? t.children : [t]));
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
  const navItem = (on, extra = '') => `flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[15px] ${on ? 'bg-[#e6f1f9] font-bold text-[#0b3a66]' : 'text-[#17324d] hover:bg-[#f3f9fd]'} ${extra}`;

  return (
    <div className="flex max-w-[1240px] flex-col gap-5 font-sans text-[#17324d]">
      <div className="flex flex-wrap items-end justify-between gap-3.5">
        <div className="flex flex-col gap-1">
          <h1 className="text-[34px] font-bold leading-tight tracking-tight">Tableros y proyectos</h1>
          <span className="text-[15px] text-[#5b6f82]">{total} proyectos en {tree.length} temas y {subtopicCount} subtemas</span>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <label className="relative flex min-w-[220px] flex-1 items-center sm:flex-none">
            <Search size={17} aria-hidden="true" className="pointer-events-none absolute left-3.5 text-[#5b6f82]" />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar proyecto o unidad" aria-label="Buscar proyecto o unidad"
              className="h-11 w-full rounded-xl border border-[#c9dceb] bg-white pl-[42px] pr-3.5 text-base sm:w-72" />
          </label>
          {admin && <Button type="button" variant="outline" className="h-11 rounded-xl" onClick={() => setTopicForm(true)}><Plus data-icon="inline-start" />Nuevo tema</Button>}
          {canWrite && <Button type="button" className="h-11 rounded-xl bg-[#0872b8] hover:bg-[#0b4f8a]" onClick={() => openDrawer(null, active && !active.children?.length ? active._id : '')}><Plus data-icon="inline-start" />Registrar proyecto</Button>}
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      {topics && nodes.length > 0 && (
        <div className="flex flex-col gap-5 md:flex-row md:items-start">
          {/* Celular: el árbol pasa a un selector */}
          <select aria-label="Tema o subtema" value={activeId} onChange={(e) => { setSelected(e.target.value); setQ(''); }}
            className="h-11 rounded-xl border border-[#c9dceb] bg-white px-3 text-base md:hidden">
            {nodes.map((n) => <option key={n._id} value={n._id}>{n.parent_id ? `   ${n.name}` : n.name}</option>)}
          </select>
          <aside className="hidden w-[280px] shrink-0 rounded-[14px] border border-[#d7e8f1] bg-white p-2.5 md:block">
            <nav aria-label="Temas y subtemas">
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {tree.map((t) => (
                  <li key={t._id}>
                    <button type="button" aria-current={t._id === activeId && !needle ? 'page' : undefined} onClick={() => { setSelected(t._id); setQ(''); }}
                      className={navItem(t._id === activeId && !needle, 'font-bold')}>
                      <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: t.accent }} />
                      <span className="flex-1">{t.name}</span>
                      <span className="text-[13px] font-normal text-[#5b6f82]">{t.total}</span>
                    </button>
                    {t.children.length > 0 && (
                      <ul className="m-0 mb-1 flex list-none flex-col gap-0.5 p-0 pl-[22px]">
                        {t.children.map((c) => (
                          <li key={c._id}>
                            <button type="button" aria-current={c._id === activeId && !needle ? 'page' : undefined} onClick={() => { setSelected(c._id); setQ(''); }}
                              className={navItem(c._id === activeId && !needle)}>
                              <span className="flex-1">{c.name}</span>
                              <span className="text-[13px] font-normal text-[#5b6f82]">{c.items.length}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          </aside>

          <div className="flex min-w-0 flex-1 flex-col gap-6">
            {!needle && active && (
              <div className="flex flex-col gap-0.5">
                <span className="text-sm text-[#5b6f82]">{parentOf ? `${parentOf.name} › ${active.name}` : 'Tema'}</span>
                <h2 className="border-b-[3px] pb-2 text-[26px] font-bold" style={{ borderColor: active.accent }}>{active.name}</h2>
              </div>
            )}
            {shown.map((s) => {
              const isGroup = !needle && active?.children?.length && s._id === active._id;   // el tema que agrupa no pinta tarjetas propias
              if (isGroup && s.items.length === 0) return null;
              return (
                <section key={s._id} aria-label={s.label} className="flex flex-col gap-3">
                  {(needle || s._id !== active?._id) && (
                    <div className="flex items-baseline gap-2.5 border-b-2 pb-1.5" style={{ borderColor: s.accent }}>
                      <h3 className="text-xl font-bold">{needle ? s.label : s.name}</h3>
                      <span className="text-[13.5px] text-[#5b6f82]">{s.items.length} {s.items.length === 1 ? 'proyecto' : 'proyectos'}</span>
                    </div>
                  )}
                  <div className={GRID}>
                    {s.items.map((r) => (
                      <ResourceCard key={r._id} resource={r} unitName={unitName(r.unit_id)} manage={manageable(r)}
                        onEdit={() => openDrawer(r)} onDelete={() => setToDelete(r)} />
                    ))}
                    {canWrite && !needle && !isGroup && (
                      <button type="button" onClick={() => openDrawer(null, s._id)}
                        className="flex min-h-[120px] flex-col items-center justify-center gap-1.5 rounded-[14px] border-[1.5px] border-dashed border-[#b8d3e6] text-[15px] font-bold text-[#0872b8] active:scale-[0.97]">
                        <Plus size={22} aria-hidden="true" />Registrar en este subtema
                      </button>
                    )}
                  </div>
                </section>
              );
            })}
            {needle && shown.length === 0 && (
              <p className="rounded-[14px] border border-dashed border-[#c9dceb] bg-white p-7 text-center text-base text-[#5b6f82]">Ningún proyecto coincide con «{q.trim()}».</p>
            )}
          </div>
        </div>
      )}

      {topics && nodes.length === 0 && (
        <p className="rounded-[14px] border border-dashed border-[#c9dceb] bg-white p-7 text-center text-base text-[#5b6f82]">Aún no hay temas. Un administrador debe crearlos primero.</p>
      )}

      <TopicForm open={topicForm} onOpenChange={setTopicForm} topics={topics ?? []} onSaved={load} />
      <ResourceDrawer open={drawer.open} resource={drawer.resource} topicId={drawer.topicId} topics={topicOptions} units={units} admin={admin}
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
