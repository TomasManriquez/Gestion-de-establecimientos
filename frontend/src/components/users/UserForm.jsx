import React, { useEffect, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { parseApiError, usersApi } from '@/lib/api';
import { POSITION_LABELS } from '@/lib/format';
import EstablishmentCombobox from './EstablishmentCombobox';
import UnitSelect from './UnitSelect';

const EMPTY = {
  first_name: '', last_name: '', email: '', personal_phone: '', work_extension: '',
  is_slep_staff: true, unit_id: '', rbd: '', positions: [''],
};

const fromUser = (u) => ({
  first_name: u.first_name ?? '', last_name: u.last_name ?? '', email: u.email ?? '',
  personal_phone: u.personal_phone ?? '', work_extension: u.work_extension ?? '',
  is_slep_staff: !!u.is_slep_staff, unit_id: u.unit_id ?? '', rbd: u.rbd ?? '',
  positions: u.positions?.length ? [...u.positions] : [''],
});

/** Un campo de texto con su etiqueta y su error: el 409 del correo se marca en el propio campo. */
function TextField({ id, label, value, onChange, error, type = 'text', placeholder, description, autoComplete }) {
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input id={id} type={type} value={value} placeholder={placeholder} autoComplete={autoComplete}
        aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined}
        onChange={(e) => onChange(e.target.value)} />
      {description && !error && <FieldDescription>{description}</FieldDescription>}
      {error && <FieldError id={`${id}-error`}>{error}</FieldError>}
    </Field>
  );
}

/**
 * Crear y editar usuario: UN solo formulario (el backend es la frontera de validación).
 * Al cambiar el interruptor "Funcionario SLEP" se limpian los campos del otro modo, así que el
 * body nunca lleva `unit_id` y `rbd` a la vez.
 */
export default function UserForm({ open, onOpenChange, user = null, units, establishments, onSaved }) {
  const isEdit = !!user;
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(user ? fromUser(user) : EMPTY);
      setErrors({});
      setFormError('');
      setPending(false);
    }
  }, [open, user]);

  const set = (key) => (value) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const setMode = (isSlep) => {
    setForm((f) => (isSlep
      ? { ...f, is_slep_staff: true, rbd: '', positions: [''] }
      : { ...f, is_slep_staff: false, unit_id: '' }));
    setErrors({});
    setFormError('');
  };

  const setPosition = (index, value) => setForm((f) => ({ ...f, positions: f.positions.map((p, i) => (i === index ? value : p)) }));

  const buildBody = () => {
    const positions = form.positions.filter(Boolean);
    return {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim(),
      personal_phone: form.personal_phone.trim() || null,
      work_extension: form.work_extension.trim() || null,
      is_slep_staff: form.is_slep_staff,
      unit_id: form.is_slep_staff ? (form.unit_id || null) : null,
      rbd: form.is_slep_staff ? null : (form.rbd || null),
      positions: form.is_slep_staff ? [] : positions,
    };
  };

  const submit = async (event) => {
    event.preventDefault();
    if (pending) return;
    const body = buildBody();
    const local = {};
    if (!body.first_name) local.first_name = 'Ingresa el nombre.';
    if (!body.last_name) local.last_name = 'Ingresa el apellido.';
    if (!body.email) local.email = 'Ingresa el correo institucional.';
    if (body.is_slep_staff && !body.unit_id) local.unit_id = 'Selecciona la unidad.';
    if (!body.is_slep_staff && !body.rbd) local.rbd = 'Selecciona el establecimiento.';
    if (!body.is_slep_staff && body.positions.length === 0) local.positions = 'Selecciona al menos un cargo.';
    if (Object.keys(local).length) {
      setErrors(local);
      return;
    }
    setPending(true);
    setFormError('');
    try {
      let saved;
      if (isEdit) {
        // PATCH: solo lo que cambió (los None se ignoran en el servidor; cambiar de modo limpia el otro).
        const original = buildBodyFrom(user);
        const diff = {};
        for (const key of Object.keys(body)) {
          if (JSON.stringify(body[key]) !== JSON.stringify(original[key]) && body[key] !== null && body[key] !== undefined) diff[key] = body[key];
        }
        if (Object.keys(diff).length === 0) {
          onOpenChange(false);
          return;
        }
        saved = await usersApi.update(user._id, diff);
      } else {
        saved = await usersApi.create(body);
      }
      onSaved(saved, isEdit);
      onOpenChange(false);
    } catch (err) {
      const parsed = parseApiError(err);
      // El backend responde por campo; "positions" puede venir como positions.0
      const mapped = {};
      for (const [field, message] of Object.entries(parsed.fields)) mapped[field.split('.')[0]] = message;
      setErrors(mapped);
      setFormError(Object.keys(mapped).length ? '' : parsed.message);
    } finally {
      setPending(false);
    }
  };

  const usedPositions = form.positions.filter(Boolean);
  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Editar usuario' : 'Crear usuario'}</DialogTitle>
          <DialogDescription>
            {isEdit ? 'Cambia los datos de la persona. Los accesos se gestionan aparte.' : 'Recibirá un correo con un enlace de un solo uso para definir su contraseña.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} noValidate className="flex flex-col gap-5">
          <FieldGroup>
            <Field orientation="horizontal" className="rounded-xl border p-3 items-center justify-between">
              <div className="flex flex-col gap-0.5">
                <FieldLabel htmlFor="user-is-slep">Funcionario SLEP</FieldLabel>
                <FieldDescription>
                  {form.is_slep_staff ? 'Pertenece a una unidad del organigrama' : 'Pertenece a un establecimiento (RBD) y tiene cargo'}
                </FieldDescription>
              </div>
              <Switch id="user-is-slep" checked={form.is_slep_staff} onCheckedChange={setMode} />
            </Field>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <TextField id="user-first-name" label="Nombre" value={form.first_name} onChange={set('first_name')} error={errors.first_name} autoComplete="given-name" />
              <TextField id="user-last-name" label="Apellido" value={form.last_name} onChange={set('last_name')} error={errors.last_name} autoComplete="family-name" />
            </div>
            <TextField id="user-email" label="Correo institucional" type="email" value={form.email} onChange={set('email')}
              error={errors.email} placeholder="nombre.apellido@slepllanquihue.cl" autoComplete="off" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <TextField id="user-phone" label="Teléfono personal" type="tel" value={form.personal_phone} onChange={set('personal_phone')}
                error={errors.personal_phone} placeholder="+56912345678" description="Formato +56 y 9 dígitos." />
              <TextField id="user-extension" label="Anexo" value={form.work_extension} onChange={set('work_extension')}
                error={errors.work_extension} placeholder="4521" description="De 2 a 6 dígitos." />
            </div>

            {form.is_slep_staff ? (
              <Field data-invalid={errors.unit_id ? true : undefined}>
                <FieldLabel htmlFor="user-unit">Unidad</FieldLabel>
                <UnitSelect id="user-unit" units={units} value={form.unit_id} onChange={set('unit_id')} invalid={!!errors.unit_id} />
                {errors.unit_id && <FieldError>{errors.unit_id}</FieldError>}
              </Field>
            ) : (
              <>
                <Field data-invalid={errors.rbd ? true : undefined}>
                  <FieldLabel htmlFor="user-rbd">Establecimiento</FieldLabel>
                  <EstablishmentCombobox id="user-rbd" establishments={establishments} value={form.rbd} onChange={set('rbd')} invalid={!!errors.rbd} />
                  {errors.rbd && <FieldError>{errors.rbd}</FieldError>}
                </Field>
                <Field data-invalid={errors.positions ? true : undefined}>
                  <FieldLabel htmlFor="user-position-0">Cargo</FieldLabel>
                  <div className="flex flex-col gap-2">
                    {form.positions.map((position, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <Select value={position || undefined} onValueChange={(v) => { setPosition(index, v); setErrors((e) => ({ ...e, positions: undefined })); }}>
                          <SelectTrigger id={`user-position-${index}`} aria-invalid={errors.positions ? true : undefined} aria-label={`Cargo ${index + 1}`}>
                            <SelectValue placeholder="Selecciona un cargo" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {Object.entries(POSITION_LABELS).map(([value, label]) => (
                                <SelectItem key={value} value={value} disabled={usedPositions.includes(value) && value !== position}>{label}</SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                        {index > 0 && (
                          <Button type="button" variant="ghost" size="icon" aria-label={`Quitar el cargo ${index + 1}`}
                            onClick={() => setForm((f) => ({ ...f, positions: f.positions.filter((_, i) => i !== index) }))}>
                            <X />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                  {form.positions.length < Object.keys(POSITION_LABELS).length && form.positions.every(Boolean) && (
                    <Button type="button" variant="link" className="self-start px-0"
                      onClick={() => setForm((f) => ({ ...f, positions: [...f.positions, ''] }))}>
                      <Plus />Agregar otro cargo
                    </Button>
                  )}
                  {errors.positions && <FieldError>{errors.positions}</FieldError>}
                </Field>
              </>
            )}
          </FieldGroup>

          {formError && (
            <Alert variant="destructive" role="alert"><AlertDescription>{formError}</AlertDescription></Alert>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={pending}>
              {pending && <Spinner data-icon="inline-start" />}
              {isEdit ? 'Guardar cambios' : 'Crear y enviar invitación'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function buildBodyFrom(user) {
  return {
    first_name: user.first_name ?? '', last_name: user.last_name ?? '', email: user.email ?? '',
    personal_phone: user.personal_phone || null, work_extension: user.work_extension || null,
    is_slep_staff: !!user.is_slep_staff, unit_id: user.unit_id ?? null, rbd: user.rbd ?? null, positions: user.positions ?? [],
  };
}
