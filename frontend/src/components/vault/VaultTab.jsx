import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Copy, Eye, EyeOff, ExternalLink, KeyRound, Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { parseApiError, vaultApi } from '@/lib/api';
import { useIsDesktop } from '@/lib/useMediaQuery';

/** La contraseña revelada se oculta sola: no queda en pantalla si la persona se va. */
const REVEAL_VISIBLE_MS = 30_000;

/** Mensaje de un 429 de `reveal`: «Alcanzaste el límite de revelaciones; vuelve en X min». */
function revealErrorMessage(err) {
  const e = parseApiError(err);
  if (e.status === 429) {
    const minutes = Math.max(1, Math.ceil(Number(err.response?.headers?.['retry-after'] ?? 60) / 60));
    return `Alcanzaste el límite de revelaciones; vuelve en ${minutes} min.`;
  }
  return e.status === 503 ? 'No se pudo registrar la revelación, así que la contraseña no se entregó. Inténtalo de nuevo.' : e.message;
}

function CredentialForm({ open, onOpenChange, rbd, credential, onSaved }) {
  const editing = Boolean(credential);
  const [form, setForm] = useState({ name: '', username: '', password: '', url: '' });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState({ message: '', fields: {} });

  useEffect(() => {
    if (open) {
      setForm({ name: credential?.name ?? '', username: credential?.username ?? '', password: '', url: credential?.url ?? '' });
      setError({ message: '', fields: {} });
    }
  }, [open, credential]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    // Vacío = sin dato. En edición, contraseña vacía = no cambiarla (el backend ignora el campo ausente).
    const body = { name: form.name.trim(), username: form.username.trim() || null, url: form.url.trim() || null };
    if (form.password) body.password = form.password;
    setPending(true);
    try {
      const saved = editing ? await vaultApi.update(rbd, credential._id, body) : await vaultApi.create(rbd, body);
      toast.success(editing ? 'Credencial actualizada' : 'Credencial guardada');
      onSaved(saved);
      onOpenChange(false);
    } catch (err) {
      const { message, fields } = parseApiError(err);
      setError({ message, fields });
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className="max-w-md">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{editing ? 'Editar credencial' : 'Nueva credencial'}</DialogTitle>
            <DialogDescription>
              La contraseña se guarda cifrada y solo la ven las personas con acceso a esta bóveda. Cada vez que se revela queda registrada.
            </DialogDescription>
          </DialogHeader>
          {error.message && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
          <FieldGroup>
            <Field data-invalid={Boolean(error.fields.name) || undefined}>
              <FieldLabel htmlFor="vault-name">Nombre</FieldLabel>
              <Input id="vault-name" value={form.name} onChange={set('name')} required maxLength={80} placeholder="SIGE, Google Workspace…" className="text-base" />
              <FieldError>{error.fields.name}</FieldError>
            </Field>
            <Field>
              <FieldLabel htmlFor="vault-username">Usuario (opcional)</FieldLabel>
              <Input id="vault-username" value={form.username} onChange={set('username')} maxLength={120} autoComplete="off" className="text-base" />
            </Field>
            <Field data-invalid={Boolean(error.fields.password) || undefined}>
              <FieldLabel htmlFor="vault-password">{editing ? 'Contraseña nueva (vacía = no cambiar)' : 'Contraseña'}</FieldLabel>
              <Input id="vault-password" type="password" value={form.password} onChange={set('password')} required={!editing}
                maxLength={256} autoComplete="new-password" className="text-base" />
              <FieldError>{error.fields.password}</FieldError>
            </Field>
            <Field data-invalid={Boolean(error.fields.url) || undefined}>
              <FieldLabel htmlFor="vault-url">Enlace (opcional)</FieldLabel>
              <Input id="vault-url" type="url" value={form.url} onChange={set('url')} maxLength={500} placeholder="https://…" className="text-base" />
              <FieldError>{error.fields.url}</FieldError>
            </Field>
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

/** Contraseña de una credencial: oculta por defecto; «Mostrar» la pide al servidor (queda registrado). */
function PasswordCell({ rbd, credential }) {
  const [value, setValue] = useState(null);
  const [pending, setPending] = useState(false);
  const [copied, setCopied] = useState(false);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const reveal = async () => {
    setPending(true);
    try {
      const password = await vaultApi.reveal(rbd, credential._id);
      setValue(password);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setValue(null), REVEAL_VISIBLE_MS);
      return password;
    } catch (err) {
      toast.error(revealErrorMessage(err));
      return null;
    } finally {
      setPending(false);
    }
  };

  const copy = async () => {
    const password = value ?? await reveal();          // copiar también es una revelación: pasa por el servidor
    if (password == null) return;
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('No se pudo copiar. Muestra la contraseña y cópiala a mano.');
    }
  };

  return (
    <div className="flex items-center gap-1.5">
      <code className="min-w-[7rem] rounded bg-slate-100 px-2 py-1 text-sm break-all" data-testid={`pw-${credential._id}`}>
        {value ?? '••••••••'}
      </code>
      <Button type="button" variant="ghost" size="icon" disabled={pending} onClick={value ? () => setValue(null) : reveal}
        aria-label={value ? `Ocultar contraseña de ${credential.name}` : `Mostrar contraseña de ${credential.name}`}>
        {pending ? <Spinner /> : value ? <EyeOff size={16} /> : <Eye size={16} />}
      </Button>
      <Button type="button" variant="ghost" size="icon" onClick={copy} aria-label={`Copiar contraseña de ${credential.name}`}>
        {copied ? <Check size={16} /> : <Copy size={16} />}
      </Button>
    </div>
  );
}

function CredentialCard({ rbd, credential, onEdit, onDelete }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-bold text-slate-800">{credential.name}</h3>
          <p className="text-sm text-slate-500">{credential.username || 'Sin usuario'}</p>
        </div>
        <div className="flex shrink-0">
          <Button type="button" variant="ghost" size="icon" onClick={() => onEdit(credential)} aria-label={`Editar ${credential.name}`}><Pencil size={16} /></Button>
          <Button type="button" variant="ghost" size="icon" onClick={() => onDelete(credential)} aria-label={`Eliminar ${credential.name}`}><Trash2 size={16} /></Button>
        </div>
      </div>
      <div className="mt-3"><PasswordCell rbd={rbd} credential={credential} /></div>
      {credential.url && (
        <a href={credential.url} target="_blank" rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-sky-700 hover:underline">
          <ExternalLink size={14} aria-hidden="true" />Abrir enlace
        </a>
      )}
    </div>
  );
}

/**
 * Pestaña «Bóveda» de la ficha (ADR-021). Solo se monta si el servidor ya respondió 200 al listar:
 * ocultarla es comodidad, la barrera es el 403 del backend.
 */
export default function VaultTab({ rbd, initial }) {
  const isDesktop = useIsDesktop();
  const [items, setItems] = useState(initial ?? []);
  const [form, setForm] = useState({ open: false, credential: null });
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const reload = useCallback(async () => {
    try { setItems(await vaultApi.list(rbd)); } catch (err) { toast.error(parseApiError(err).message); }
  }, [rbd]);

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await vaultApi.remove(rbd, toDelete._id);
      toast.success('Credencial eliminada');
      setToDelete(null);
      await reload();
    } catch (err) {
      toast.error(parseApiError(err).message);
    } finally {
      setDeleting(false);
    }
  };

  const edit = (credential) => setForm({ open: true, credential });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500">
          Credenciales de este establecimiento. Las contraseñas están cifradas y cada vez que alguien las muestra o copia queda registrado.
        </p>
        <Button type="button" onClick={() => setForm({ open: true, credential: null })}><Plus data-icon="inline-start" />Nueva credencial</Button>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-500">
          <KeyRound className="mx-auto mb-2" aria-hidden="true" />
          Aún no hay credenciales guardadas para este establecimiento.
        </div>
      ) : isDesktop ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-2">Nombre</th><th className="px-4 py-2">Usuario</th><th className="px-4 py-2">Contraseña</th><th className="px-4 py-2">Enlace</th><th className="px-4 py-2"><span className="sr-only">Acciones</span></th></tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c._id} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-semibold text-slate-800">{c.name}</td>
                  <td className="px-4 py-2">{c.username || '—'}</td>
                  <td className="px-4 py-2"><PasswordCell rbd={rbd} credential={c} /></td>
                  <td className="px-4 py-2">
                    {c.url ? <a href={c.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sky-700 hover:underline"><ExternalLink size={14} aria-hidden="true" />Abrir</a> : '—'}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Button type="button" variant="ghost" size="icon" onClick={() => edit(c)} aria-label={`Editar ${c.name}`}><Pencil size={16} /></Button>
                    <Button type="button" variant="ghost" size="icon" onClick={() => setToDelete(c)} aria-label={`Eliminar ${c.name}`}><Trash2 size={16} /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((c) => <CredentialCard key={c._id} rbd={rbd} credential={c} onEdit={edit} onDelete={setToDelete} />)}
        </div>
      )}

      <CredentialForm open={form.open} onOpenChange={(open) => setForm((f) => ({ ...f, open }))} rbd={rbd}
        credential={form.credential} onSaved={reload} />

      <AlertDialog open={Boolean(toDelete)} onOpenChange={(open) => !open && !deleting && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar «{toDelete?.name}»?</AlertDialogTitle>
            <AlertDialogDescription>La contraseña se borra y no se puede recuperar. Queda registro de quién la eliminó.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancelar</AlertDialogCancel>
            <AlertDialogAction disabled={deleting} onClick={(e) => { e.preventDefault(); confirmDelete(); }}>Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
