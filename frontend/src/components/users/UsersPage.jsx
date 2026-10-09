import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, Upload, Users } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { establishmentsApi, parseApiError, platformsApi, unitsApi, usersApi } from '@/lib/api';
import { fullNameOf } from '@/lib/format';
import { orderUnits } from '@/lib/units';
import AccessDialog from './AccessDialog';
import BulkBar from './BulkBar';
import UserForm from './UserForm';
import UsersFilters from './UsersFilters';
import UsersTable from './UsersTable';

const PAGE_SIZE = 25;
const FILTER_KEYS = ['unit', 'kind', 'platform', 'role', 'status'];

/**
 * Vista /configuracion/usuarios (propuesta A). Los filtros y la página viven en la URL
 * (mismo patrón que el Directorio) y la paginación la hace el servidor.
 */
export default function UsersPage({ currentUser }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = {
    q: searchParams.get('q') ?? '',
    unit: searchParams.get('unit') ?? '',
    sub: searchParams.get('sub') !== '0',
    kind: searchParams.get('kind') ?? '',
    platform: searchParams.get('platform') ?? '',
    role: searchParams.get('role') ?? '',
    status: searchParams.get('status') ?? '',
    page: Math.max(1, parseInt(searchParams.get('page') ?? '1', 10) || 1),
  };
  const queryKey = searchParams.toString();

  // Datos de referencia (nombres de unidades y establecimientos, plataformas)
  const [unitsFlat, setUnitsFlat] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [establishments, setEstablishments] = useState([]);
  useEffect(() => {
    let alive = true;
    unitsApi.list().then((d) => alive && setUnitsFlat(d)).catch(() => {});
    platformsApi.list().then((d) => alive && setPlatforms(d)).catch(() => {});
    establishmentsApi.all().then((d) => alive && setEstablishments(d)).catch(() => {});
    return () => { alive = false; };
  }, []);
  const units = useMemo(() => orderUnits(unitsFlat), [unitsFlat]);
  const unitsById = useMemo(() => Object.fromEntries(unitsFlat.map((u) => [u._id, u])), [unitsFlat]);
  const establishmentsByRbd = useMemo(() => Object.fromEntries(establishments.map((e) => [e.rbd, e])), [establishments]);

  // Lista
  const [data, setData] = useState({ items: [], total: 0, total_pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const setParam = useCallback((key, value) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value === '' || value == null || (key === 'sub' && value === '1')) next.delete(key); else next.set(key, value);
      if (key !== 'page') next.delete('page');
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Búsqueda con debounce de 300 ms (como el Directorio)
  const [search, setSearch] = useState(params.q);
  useEffect(() => {
    if (search === params.q) return undefined;
    const timer = setTimeout(() => setParam('q', search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setSearch(params.q); }, [params.q]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const query = { page: params.page, page_size: PAGE_SIZE };
    if (params.q) query.q = params.q;
    if (params.unit) { query.unit_id = params.unit; query.include_descendants = params.sub; }
    for (const key of ['kind', 'platform', 'role', 'status']) if (params[key]) query[key] = params[key];
    usersApi.list(query, controller.signal)
      .then((d) => { setData(d); setError(null); setLoading(false); })
      .catch((err) => {
        if (controller.signal.aborted || err?.code === 'ERR_CANCELED') return;
        setError(parseApiError(err));
        setLoading(false);
      });
    return () => controller.abort();
  }, [queryKey, reloadKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Selección: se limpia al cambiar de página o de filtro (supuesto A6)
  const [selected, setSelected] = useState({});
  useEffect(() => { setSelected({}); }, [queryKey]);
  const selectedUsers = data.items.filter((u) => selected[u._id]);

  // Diálogos
  const [formState, setFormState] = useState({ open: false, user: null });
  const [accessUser, setAccessUser] = useState(null);
  const [confirmDisable, setConfirmDisable] = useState(null);
  const [disabling, setDisabling] = useState(false);

  const onSaved = (saved, isEdit) => {
    reload();
    if (isEdit) { toast.success(`Se guardaron los cambios de ${fullNameOf(saved)}.`); return; }
    const inv = saved.invitation;
    if (inv && !inv.sent) {
      toast.warning(`Se creó a ${fullNameOf(saved)}, pero la invitación por correo aún no se puede enviar.`);
    } else {
      toast.success(`Se creó a ${fullNameOf(saved)} y se envió la invitación.`);
    }
  };

  const doDisable = async () => {
    setDisabling(true);
    try {
      await usersApi.disable(confirmDisable._id);
      toast.success(`Se desactivó a ${fullNameOf(confirmDisable)}.`);
      setConfirmDisable(null);
      reload();
    } catch (err) {
      toast.error(parseApiError(err).message);
      setConfirmDisable(null);
    } finally {
      setDisabling(false);
    }
  };
  const doEnable = async (user) => {
    try {
      await usersApi.enable(user._id);
      toast.success(`Se reactivó a ${fullNameOf(user)}.`);
      reload();
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  const clearFilters = () => {
    setSearch('');
    setSearchParams({}, { replace: true });
  };

  const hasFilters = !!(params.q || FILTER_KEYS.some((k) => params[k]));
  const forbidden = error?.status === 403;

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-6 animate-fade-in">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs font-semibold text-muted-foreground">Configuración › Usuarios</p>
            <h1 className="text-3xl font-extrabold font-outfit tracking-tight">Usuarios</h1>
            <p className="text-sm text-muted-foreground">Administre quién accede a cada plataforma del SLEP, con qué rol y desde qué unidad.</p>
          </div>
          <div className="flex gap-3">
            <Tooltip>
              <TooltipTrigger asChild>
                <span tabIndex={0}>
                  <Button type="button" variant="outline" disabled aria-label="Importar CSV (próximamente)"><Upload />Importar CSV</Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>Próximamente: carga masiva desde un archivo CSV.</TooltipContent>
            </Tooltip>
            <Button type="button" onClick={() => setFormState({ open: true, user: null })}><Plus />Crear usuario</Button>
          </div>
        </header>

        {forbidden ? (
          <Alert variant="destructive" role="alert">
            <AlertTitle>Sin acceso</AlertTitle>
            <AlertDescription>Tu cuenta no tiene permiso para administrar usuarios.</AlertDescription>
          </Alert>
        ) : (
          <>
            <UsersFilters search={search} onSearch={setSearch} params={params} setParam={setParam} units={units} onClear={clearFilters} />

            {error && !forbidden && (
              <Alert variant="destructive" role="alert">
                <AlertTitle>No se pudo cargar la lista</AlertTitle>
                <AlertDescription>{error.message}</AlertDescription>
              </Alert>
            )}

            <Card className="overflow-hidden">
              <BulkBar selectedUsers={selectedUsers} units={units} platforms={platforms}
                onClear={() => setSelected({})}
                onDone={(results) => {
                  const ok = results.filter((r) => r.ok).length;
                  if (ok > 0) { toast.success(`${ok} de ${results.length} usuario(s) actualizados.`); reload(); }
                }} />

              {loading ? (
                <div className="flex flex-col gap-3 p-6" aria-busy="true" aria-label="Cargando usuarios">
                  {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-12 w-full" />)}
                </div>
              ) : data.items.length === 0 && !error ? (
                <Empty className="py-12">
                  <EmptyHeader>
                    <EmptyMedia variant="icon"><Users /></EmptyMedia>
                    <EmptyTitle>No hay usuarios con esos criterios</EmptyTitle>
                    <EmptyDescription>{hasFilters ? 'Prueba quitando algún filtro.' : 'Crea el primer usuario con el botón «Crear usuario».'}</EmptyDescription>
                  </EmptyHeader>
                  {hasFilters && <Button type="button" variant="outline" onClick={clearFilters}>Limpiar filtros</Button>}
                </Empty>
              ) : (
                <UsersTable items={data.items} selected={selected}
                  onToggle={(id) => setSelected((s) => ({ ...s, [id]: !s[id] }))}
                  onToggleAll={(on) => setSelected(on ? Object.fromEntries(data.items.map((u) => [u._id, true])) : {})}
                  unitsById={unitsById} establishmentsByRbd={establishmentsByRbd} currentUserId={currentUser?.id}
                  onEdit={(user) => setFormState({ open: true, user })} onAccess={setAccessUser}
                  onDisable={setConfirmDisable} onEnable={doEnable} />
              )}

              <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-muted/40 px-6 py-3 text-sm text-muted-foreground">
                <span>Mostrando <b>{data.items.length}</b> de <b>{data.total}</b> usuarios</span>
                {data.total_pages > 1 && (
                  <Pagination className="mx-0 w-auto justify-end">
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious href="#" aria-disabled={params.page <= 1}
                          onClick={(e) => { e.preventDefault(); if (params.page > 1) setParam('page', String(params.page - 1)); }} />
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationLink href="#" isActive onClick={(e) => e.preventDefault()}>{params.page} de {data.total_pages}</PaginationLink>
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationNext href="#" aria-disabled={params.page >= data.total_pages}
                          onClick={(e) => { e.preventDefault(); if (params.page < data.total_pages) setParam('page', String(params.page + 1)); }} />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                )}
              </div>
            </Card>
          </>
        )}

        <UserForm open={formState.open} user={formState.user} units={units} establishments={establishments}
          onOpenChange={(open) => setFormState((s) => ({ ...s, open }))} onSaved={onSaved} />

        <AccessDialog open={!!accessUser} user={accessUser} platforms={platforms}
          onOpenChange={(open) => !open && setAccessUser(null)}
          onSaved={() => { toast.success('Se actualizaron los accesos.'); reload(); }} />

        <AlertDialog open={!!confirmDisable} onOpenChange={(open) => !open && !disabling && setConfirmDisable(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Desactivar a {confirmDisable ? fullNameOf(confirmDisable) : ''}?</AlertDialogTitle>
              <AlertDialogDescription>
                Perderá el acceso en su siguiente petición. Podrás reactivar la cuenta cuando quieras.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={disabling}>Cancelar</AlertDialogCancel>
              <Button type="button" variant="destructive" disabled={disabling} onClick={doDisable}>
                {disabling && <Spinner data-icon="inline-start" />}Desactivar
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  );
}
