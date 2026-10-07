import React, { useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { parseApiError, usersApi } from '@/lib/api';
import { fullNameOf, ROLE_LABELS } from '@/lib/format';
import UnitSelect from './UnitSelect';

/** Ejecuta `fn` por cada usuario en orden y junta el resultado de cada uno (nunca se detiene en el primer error). */
async function runEach(users, fn) {
  const results = [];
  for (const user of users) {
    try {
      await fn(user);
      results.push({ id: user._id, name: fullNameOf(user), ok: true });
    } catch (err) {
      results.push({ id: user._id, name: fullNameOf(user), ok: false, message: parseApiError(err).message });
    }
  }
  return results;
}

function Results({ results }) {
  const failed = results.filter((r) => !r.ok);
  if (failed.length === 0) return null;
  return (
    <Alert variant="destructive" role="alert">
      <AlertTitle>{failed.length} de {results.length} no se pudieron procesar</AlertTitle>
      <AlertDescription>
        <ul className="flex flex-col gap-1">
          {failed.map((r) => <li key={r.id}><b>{r.name}:</b> {r.message}</li>)}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

/**
 * Selección múltiple. Hasta que exista `POST /api/users/bulk` (F4), cada acción llama al
 * endpoint individual por usuario, en orden: las invariantes del servidor (último admin,
 * auto-desactivación) se evalúan en cada llamada y el resultado se informa por persona.
 */
export default function BulkBar({ selectedUsers, units, platforms, onClear, onDone }) {
  const [dialog, setDialog] = useState(null);      // 'grant' | 'revoke' | 'unit' | 'disable'
  const [platformId, setPlatformId] = useState('');
  const [role, setRole] = useState('');
  const [unitId, setUnitId] = useState('');
  const [pending, setPending] = useState(false);
  const [results, setResults] = useState([]);

  const count = selectedUsers.length;
  if (count === 0) return null;

  const close = () => { if (!pending) { setDialog(null); setResults([]); setPlatformId(''); setRole(''); setUnitId(''); } };
  const execute = async (fn) => {
    setPending(true);
    const res = await runEach(selectedUsers, fn);
    setPending(false);
    setResults(res);
    onDone(res);
    if (res.every((r) => r.ok)) { setDialog(null); setResults([]); }
  };
  const platform = platforms.find((p) => p._id === platformId);

  return (
    <>
      <div role="status" className="flex flex-wrap items-center gap-3 bg-foreground px-6 py-3 text-background">
        <span className="text-sm font-bold">{count === 1 ? '1 usuario seleccionado' : `${count} usuarios seleccionados`}</span>
        <span className="flex-1" />
        <Button type="button" variant="secondary" size="sm" onClick={() => setDialog('unit')}>Asignar unidad</Button>
        <Button type="button" variant="secondary" size="sm" onClick={() => setDialog('grant')}>Dar acceso</Button>
        <Button type="button" variant="secondary" size="sm" onClick={() => setDialog('revoke')}>Quitar acceso</Button>
        <Button type="button" variant="destructive" size="sm" onClick={() => setDialog('disable')}>Desactivar</Button>
        <Button type="button" variant="ghost" size="sm" onClick={onClear}>Cancelar selección</Button>
      </div>

      <AlertDialog open={dialog === 'disable'} onOpenChange={(o) => !o && close()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Desactivar {count === 1 ? 'a 1 usuario' : `a ${count} usuarios`}?</AlertDialogTitle>
            <AlertDialogDescription>
              Perderán el acceso en su siguiente petición y podrás reactivarlos después. Nadie puede desactivarse a sí mismo
              ni dejar al sistema sin administrador global.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Results results={results} />
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>Cancelar</AlertDialogCancel>
            <Button type="button" variant="destructive" disabled={pending} onClick={() => execute((u) => usersApi.disable(u._id))}>
              {pending && <Spinner data-icon="inline-start" />}Desactivar
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={dialog === 'grant' || dialog === 'revoke'} onOpenChange={(o) => !o && close()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{dialog === 'grant' ? 'Dar acceso' : 'Quitar acceso'}</DialogTitle>
            <DialogDescription>Se aplica a {count === 1 ? '1 usuario' : `${count} usuarios`} seleccionados.</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="bulk-platform">Plataforma</FieldLabel>
              <Select value={platformId || undefined} onValueChange={(v) => { setPlatformId(v); setRole(''); }}>
                <SelectTrigger id="bulk-platform"><SelectValue placeholder="Selecciona una plataforma" /></SelectTrigger>
                <SelectContent><SelectGroup>
                  {platforms.map((p) => <SelectItem key={p._id} value={p._id}>{p._id === 'iam' ? 'Administración de usuarios' : p.name}</SelectItem>)}
                </SelectGroup></SelectContent>
              </Select>
            </Field>
            {dialog === 'grant' && (
              <Field>
                <FieldLabel htmlFor="bulk-role">Rol</FieldLabel>
                <Select value={role || undefined} onValueChange={setRole} disabled={!platform}>
                  <SelectTrigger id="bulk-role"><SelectValue placeholder="Selecciona un rol" /></SelectTrigger>
                  <SelectContent><SelectGroup>
                    {(platform?.roles ?? []).map((r) => <SelectItem key={r} value={r}>{platformId === 'iam' && r === 'admin' ? 'Admin global' : (ROLE_LABELS[r] ?? r)}</SelectItem>)}
                  </SelectGroup></SelectContent>
                </Select>
              </Field>
            )}
          </FieldGroup>
          <Results results={results} />
          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={close}>Cancelar</Button>
            <Button type="button" disabled={pending || !platformId || (dialog === 'grant' && !role)}
              onClick={() => execute((u) => (dialog === 'grant' ? usersApi.grantAccess(u._id, platformId, role) : usersApi.revokeAccess(u._id, platformId)))}>
              {pending && <Spinner data-icon="inline-start" />}{dialog === 'grant' ? 'Dar acceso' : 'Quitar acceso'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialog === 'unit'} onOpenChange={(o) => !o && close()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Asignar unidad</DialogTitle>
            <DialogDescription>Solo aplica a funcionarios SLEP; los usuarios de establecimiento se informarán como no procesados.</DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="bulk-unit">Unidad</FieldLabel>
            <UnitSelect id="bulk-unit" units={units} value={unitId} onChange={setUnitId} />
          </Field>
          <Results results={results} />
          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={close}>Cancelar</Button>
            <Button type="button" disabled={pending || !unitId} onClick={() => execute((u) => usersApi.update(u._id, { unit_id: unitId }))}>
              {pending && <Spinner data-icon="inline-start" />}Asignar unidad
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
