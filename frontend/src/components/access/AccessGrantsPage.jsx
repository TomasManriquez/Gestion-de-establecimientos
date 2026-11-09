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
import { establishmentsApi, grantsApi, parseApiError, usersApi } from '@/lib/api';
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
  const [error, setError] = useState('');

  const [person, setPerson] = useState(null);
  const [allVaults, setAllVaults] = useState(false);
  const [rbd, setRbd] = useState('');
  const [saving, setSaving] = useState(false);
  const [toRevoke, setToRevoke] = useState(null);

  const load = useCallback(async () => {
    try {
      const list = await grantsApi.list({ resource_type: 'vault' });
      const ids = [...new Set(list.map((g) => g.subject_id))];
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
  }, [load]);

  const resourceLabel = (id) => (id === ALL ? 'Todas las bóvedas' : (() => {
    const e = establishments.find((x) => x.rbd === id);
    return e ? `${e.name} · RBD ${e.rbd}` : `RBD ${id}`;
  })());

  const canSave = person && (allVaults || rbd);

  const grant = async () => {
    setSaving(true);
    try {
      await grantsApi.create({ resource_type: 'vault', resource_id: allVaults ? ALL : rbd, user_id: person._id });
      toast.success(`${fullNameOf(person)} ahora tiene acceso`);
      setPerson(null);
      setRbd('');
      await load();
    } catch (err) {
      const e = parseApiError(err);
      toast.error(e.status === 409 ? 'Esa persona ya tiene ese acceso.' : e.message);
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
        <h1 className="flex items-center gap-2 text-2xl font-extrabold font-outfit text-slate-800"><ShieldCheck aria-hidden="true" />Accesos a la bóveda</h1>
        <p className="mt-1 text-sm text-slate-500">
          Solo las personas de esta lista ven las claves de un establecimiento. Ni el rol en Datos ni el correo del dominio dan acceso. Cada alta y baja queda registrada.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="grant-person">Persona</FieldLabel>
            <PersonPicker value={person} onChange={setPerson} />
          </Field>
          <Field orientation="horizontal" className="items-center justify-between rounded-xl border p-3">
            <FieldLabel htmlFor="grant-all">Todas las bóvedas (los 78 establecimientos)</FieldLabel>
            <Switch id="grant-all" checked={allVaults} onCheckedChange={setAllVaults} />
          </Field>
          {!allVaults && (
            <Field>
              <FieldLabel htmlFor="grant-rbd">Establecimiento</FieldLabel>
              <EstablishmentCombobox id="grant-rbd" establishments={establishments} value={rbd} onChange={setRbd} />
            </Field>
          )}
          <Button type="button" disabled={!canSave || saving} onClick={grant} className="self-start">
            {saving && <Spinner data-icon="inline-start" />}Conceder acceso
          </Button>
        </FieldGroup>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      {grants && (grants.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">Nadie tiene acceso a ninguna bóveda todavía (salvo los admin globales).</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {grants.map((g) => (
            <li key={g._id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-800">{people[g.subject_id] ? fullNameOf(people[g.subject_id]) : `Cuenta ${g.subject_id}`}</p>
                <p className="truncate text-sm text-slate-500">{resourceLabel(g.resource_id)}</p>
              </div>
              <Button type="button" variant="ghost" size="icon" onClick={() => setToRevoke(g)}
                aria-label={`Revocar acceso de ${people[g.subject_id] ? fullNameOf(people[g.subject_id]) : g.subject_id} a ${resourceLabel(g.resource_id)}`}>
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
              {toRevoke && `${people[toRevoke.subject_id] ? fullNameOf(people[toRevoke.subject_id]) : 'La persona'} dejará de ver ${resourceLabel(toRevoke.resource_id)} en su próxima petición.`}
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
