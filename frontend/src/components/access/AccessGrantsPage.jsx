import React, { useCallback, useEffect, useState } from 'react';
import { ChevronsUpDown, ShieldCheck, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import EstablishmentCombobox from '@/components/users/EstablishmentCombobox';
import { establishmentsApi, grantsApi, parseApiError, portalApi, unitsApi, usersApi } from '@/lib/api';
import { fullNameOf } from '@/lib/format';

const ALL = '*';

/** Busca personas por nombre o correo en el servidor (hay cientos de cuentas: no se cargan todas). */
function PersonPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (!open) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      usersApi.list({ q: query || undefined, page: 1, page_size: 8, status: 'active' }, controller.signal)
        .then((d) => setResults(d.items ?? []))
        .catch(() => {});
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [open, query]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button id="grant-person" type="button" variant="outline" role="combobox" aria-expanded={open} className="w-full justify-between font-normal">
          <span className="truncate">{value ? `${fullNameOf(value)} · ${value.email}` : 'Buscar por nombre o correo'}</span>
          <ChevronsUpDown data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Nombre o correo" value={query} onValueChange={setQuery} />
          <CommandList>
            <CommandEmpty>No hay cuentas activas con ese criterio. La persona debe haber entrado al menos una vez con Google.</CommandEmpty>
            <CommandGroup>
              {results.map((u) => (
                <CommandItem key={u._id} value={u._id} onSelect={() => { onChange(u); setOpen(false); }}>
                  <span className="truncate">{fullNameOf(u)}</span>
                  <span className="ml-auto truncate text-xs text-muted-foreground">{u.email}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Concesiones de acceso a las bóvedas (ADR-021). Solo `iam/admin`. Una concesión = «esta persona puede ver y
 * gestionar la bóveda de este establecimiento (o todas)». Revocar surte efecto en la siguiente petición.
 */
export default function AccessGrantsPage() {
  const [grants, setGrants] = useState(null);
  const [people, setPeople] = useState({});
  const [establishments, setEstablishments] = useState([]);
  const [portalResources, setPortalResources] = useState([]);
  const [units, setUnits] = useState([]);
  const [error, setError] = useState('');

  const [kind, setKind] = useState('vault');            // 'vault' | 'portal_resource'
  const [resourceId, setResourceId] = useState('');
  const [subject, setSubject] = useState('person');   // 'person' | 'unit'
  const [unitId, setUnitId] = useState('');
  const [includeSubunits, setIncludeSubunits] = useState(true);
  const [person, setPerson] = useState(null);
  const [allVaults, setAllVaults] = useState(false);
  const [rbd, setRbd] = useState('');
  const [saving, setSaving] = useState(false);
  const [toRevoke, setToRevoke] = useState(null);

  const load = useCallback(async () => {
    try {
      const list = await grantsApi.list();
      const ids = [...new Set(list.filter((g) => g.subject_type !== 'unit').map((g) => g.subject_id))];
      const found = await Promise.all(ids.map((id) => usersApi.get(id).catch(() => null)));
      setPeople(Object.fromEntries(found.filter(Boolean).map((u) => [u._id, u])));
      setGrants(list);
      setError('');
    } catch (err) {
      setError(parseApiError(err).message);
    }
  }, []);

  useEffect(() => {
    load();
    establishmentsApi.all().then(setEstablishments).catch(() => {});
    unitsApi.list({ status: 'active' }).then((u) => setUnits(Array.isArray(u) ? u : (u?.items ?? []))).catch(() => {});
    portalApi.resources().then((r) => setPortalResources(r.filter((x) => x.visibility === 'restricted'))).catch(() => {});
  }, [load]);

  const subjectName = (g) => {
    if (g.subject_type === 'unit') {
      const u = units.find((x) => x._id === g.subject_id);
      return `Unidad ${u?.name ?? g.subject_id}${g.include_subunits ? ' y sus subunidades' : ''}`;
    }
    return people[g.subject_id] ? fullNameOf(people[g.subject_id]) : `Cuenta ${g.subject_id}`;
  };

  const resourceLabel = (g) => {
    if (g.resource_type === 'portal_resource') {
      if (g.resource_id === ALL) return 'Portal · todos los recursos restringidos';
      return `Portal · ${portalResources.find((x) => x._id === g.resource_id)?.title ?? 'recurso eliminado'}`;
    }
    if (g.resource_id === ALL) return 'Todas las bóvedas';
    const e = establishments.find((x) => x.rbd === g.resource_id);
    return e ? `Bóveda · ${e.name} · RBD ${e.rbd}` : `Bóveda · RBD ${g.resource_id}`;
  };

  const target = kind === 'vault' ? rbd : resourceId;
  const canSave = (subject === 'person' ? person : unitId) && (allVaults || target);

  const grant = async () => {
    setSaving(true);
    try {
      const who = subject === 'person' ? { user_id: person._id } : { unit_id: unitId, include_subunits: includeSubunits };
      await grantsApi.create({ resource_type: kind, resource_id: allVaults ? ALL : target, ...who });
      toast.success(subject === 'person' ? `${fullNameOf(person)} ahora tiene acceso` : 'La unidad ahora tiene acceso');
      setPerson(null);
      setUnitId('');
      setRbd('');
      setResourceId('');
      await load();
    } catch (err) {
      const e = parseApiError(err);
      toast.error(e.status === 409 ? 'Ese acceso ya existe.' : e.message);
    } finally {
      setSaving(false);
    }
  };

  const revoke = async () => {
    try {
      await grantsApi.revoke(toRevoke._id);
      toast.success('Acceso revocado');
      setToRevoke(null);
      await load();
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-extrabold font-outfit text-slate-800"><ShieldCheck aria-hidden="true" />Accesos a recursos restringidos</h1>
        <p className="mt-1 text-sm text-slate-500">
          Solo las personas y unidades de esta lista ven las claves de un establecimiento o un recurso restringido del portal. Ni el rol en Datos ni el correo del dominio dan acceso. Cada alta y baja queda registrada.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="grant-subject">A quién</FieldLabel>
            <select id="grant-subject" value={subject} onChange={(e) => setSubject(e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-base">
              <option value="person">Una persona</option>
              <option value="unit">Una unidad</option>
            </select>
          </Field>
          {subject === 'person' ? (
            <Field>
              <FieldLabel htmlFor="grant-person">Persona</FieldLabel>
              <PersonPicker value={person} onChange={setPerson} />
            </Field>
          ) : (
            <>
              <Field>
                <FieldLabel htmlFor="grant-unit">Unidad</FieldLabel>
                <select id="grant-unit" value={unitId} onChange={(e) => setUnitId(e.target.value)}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-base">
                  <option value="" disabled>Elige una unidad</option>
                  {units.map((u) => <option key={u._id} value={u._id}>{u.name}</option>)}
                </select>
              </Field>
              <Field orientation="horizontal" className="items-center justify-between rounded-xl border p-3">
                <FieldLabel htmlFor="grant-sub">Incluir sus subunidades</FieldLabel>
                <Switch id="grant-sub" checked={includeSubunits} onCheckedChange={setIncludeSubunits} />
              </Field>
              <p className="text-sm text-slate-500">Cubre a quienes tengan esa unidad asignada en su cuenta. Las cuentas sin unidad no quedan cubiertas.</p>
            </>
          )}
          <Field>
            <FieldLabel htmlFor="grant-kind">Qué se concede</FieldLabel>
            <select id="grant-kind" value={kind} onChange={(e) => { setKind(e.target.value); setAllVaults(false); }}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-base">
              <option value="vault">Bóveda de claves de un establecimiento</option>
              <option value="portal_resource">Recurso restringido del portal</option>
            </select>
          </Field>
          <Field orientation="horizontal" className="items-center justify-between rounded-xl border p-3">
            <FieldLabel htmlFor="grant-all">{kind === 'vault' ? 'Todas las bóvedas (los 78 establecimientos)' : 'Todos los recursos restringidos del portal'}</FieldLabel>
            <Switch id="grant-all" checked={allVaults} onCheckedChange={setAllVaults} />
          </Field>
          {!allVaults && kind === 'vault' && (
            <Field>
              <FieldLabel htmlFor="grant-rbd">Establecimiento</FieldLabel>
              <EstablishmentCombobox id="grant-rbd" establishments={establishments} value={rbd} onChange={setRbd} />
            </Field>
          )}
          {!allVaults && kind === 'portal_resource' && (
            <Field>
              <FieldLabel htmlFor="grant-resource">Recurso restringido</FieldLabel>
              <select id="grant-resource" value={resourceId} onChange={(e) => setResourceId(e.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-base">
                <option value="" disabled>Elige un recurso</option>
                {portalResources.map((r) => <option key={r._id} value={r._id}>{r.title}</option>)}
              </select>
            </Field>
          )}
          <Button type="button" disabled={!canSave || saving} onClick={grant} className="self-start">
            {saving && <Spinner data-icon="inline-start" />}Conceder acceso
          </Button>
        </FieldGroup>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      {grants && (grants.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">Nadie tiene acceso concedido todavía (salvo los admin globales).</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {grants.map((g) => (
            <li key={g._id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-800">{subjectName(g)}</p>
                <p className="truncate text-sm text-slate-500">{resourceLabel(g)}</p>
              </div>
              <Button type="button" variant="ghost" size="icon" onClick={() => setToRevoke(g)}
                aria-label={`Revocar acceso de ${subjectName(g)} a ${resourceLabel(g)}`}>
                <Trash2 size={16} />
              </Button>
            </li>
          ))}
        </ul>
      ))}

      <AlertDialog open={Boolean(toRevoke)} onOpenChange={(open) => !open && setToRevoke(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Revocar este acceso?</AlertDialogTitle>
            <AlertDialogDescription>
              {toRevoke && `${subjectName(toRevoke)} dejará de ver ${resourceLabel(toRevoke)} en su próxima petición.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={revoke}>Revocar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
