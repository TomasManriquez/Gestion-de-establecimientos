import React, { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { parseApiError, usersApi } from '@/lib/api';
import { fullNameOf, ROLE_LABELS } from '@/lib/format';

const NONE = 'none';
const platformName = (p) => (p._id === 'iam' ? 'Administración de usuarios' : p.name);
const roleLabel = (platformId, role) => (platformId === 'iam' && role === 'admin' ? 'Admin global' : (ROLE_LABELS[role] ?? role));

/**
 * Un rol por plataforma. Se guardan solo los cambios; un 409 (por ejemplo "último admin global")
 * se muestra dentro del diálogo, no como un error genérico.
 */
export default function AccessDialog({ open, onOpenChange, user, platforms, onSaved }) {
  const [roles, setRoles] = useState({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  const current = (platformId) => user?.access?.find((a) => a.platform_id === platformId)?.role ?? NONE;

  useEffect(() => {
    if (open && user) {
      setRoles(Object.fromEntries(platforms.map((p) => [p._id, current(p._id)])));
      setError('');
      setPending(false);
    }
  }, [open, user, platforms]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!user) return null;
  const changes = platforms.filter((p) => (roles[p._id] ?? NONE) !== current(p._id));

  const save = async () => {
    setPending(true);
    setError('');
    let latest = user;
    try {
      for (const p of changes) {
        const role = roles[p._id];
        latest = role === NONE ? await usersApi.revokeAccess(user._id, p._id) : await usersApi.grantAccess(user._id, p._id, role);
      }
      onSaved(latest);
      onOpenChange(false);
    } catch (err) {
      setError(parseApiError(err).message);
      if (latest !== user) onSaved(latest);          // los cambios previos ya se aplicaron: refrescar la fila
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Accesos de {fullNameOf(user)}</DialogTitle>
          <DialogDescription>Un rol por plataforma. El cambio se aplica en la siguiente petición de la persona.</DialogDescription>
        </DialogHeader>
        <FieldGroup>
          {platforms.map((p) => (
            <Field key={p._id} orientation="horizontal" className="items-center justify-between rounded-xl border p-3">
              <FieldLabel htmlFor={`access-${p._id}`}>{platformName(p)}</FieldLabel>
              <Select value={roles[p._id] ?? NONE} onValueChange={(v) => setRoles((r) => ({ ...r, [p._id]: v }))}>
                <SelectTrigger id={`access-${p._id}`} className="w-44" aria-label={`Rol en ${platformName(p)}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value={NONE}>Sin acceso</SelectItem>
                    {p.roles.map((r) => <SelectItem key={r} value={r}>{roleLabel(p._id, r)}</SelectItem>)}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          ))}
        </FieldGroup>
        {error && <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert>}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button type="button" disabled={pending || changes.length === 0} onClick={save}>
            {pending && <Spinner data-icon="inline-start" />}
            Guardar accesos
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
