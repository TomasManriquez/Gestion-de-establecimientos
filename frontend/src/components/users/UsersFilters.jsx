import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import UnitSelect, { ALL } from './UnitSelect';

const KINDS = [['slep', 'Funcionarios SLEP'], ['establishment', 'Establecimientos']];
const PLATFORMS = [['datos', 'Datos'], ['selloverde', 'Sello Verde'], ['iam', 'Usuarios']];
const ROLES = [['admin', 'Admin'], ['editor', 'Editor'], ['viewer', 'Viewer']];
const STATUSES = [['active', 'Activo'], ['invited', 'Invitado'], ['disabled', 'Inactivo']];

function SimpleSelect({ id, label, value, onChange, options, allLabel }) {
  return (
    <Field className="w-36">
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? '' : v)}>
        <SelectTrigger id={id}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value={ALL}>{allLabel}</SelectItem>
            {options.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectGroup>
        </SelectContent>
      </Select>
    </Field>
  );
}

/** Barra de filtros horizontal (propuesta A). Cada control escribe en la URL (patrón FE01). */
export default function UsersFilters({ search, onSearch, params, setParam, units, onClear }) {
  const hasFilters = !!(search || params.unit || params.kind || params.platform || params.role || params.status);
  return (
    <Card>
      <CardContent className="p-4">
        <FieldGroup className="flex flex-row flex-wrap items-end gap-4">
          <Field className="min-w-[220px] flex-1">
            <FieldLabel htmlFor="users-search">Buscar</FieldLabel>
            <Input id="users-search" type="search" placeholder="Nombre, apellido o correo" value={search} onChange={(e) => onSearch(e.target.value)} />
          </Field>
          <Field className="w-56">
            <FieldLabel htmlFor="users-unit">Unidad</FieldLabel>
            <UnitSelect id="users-unit" units={units} value={params.unit} onChange={(v) => setParam('unit', v)} allLabel="Todas las unidades" />
          </Field>
          {params.unit && (
            <Field orientation="horizontal" className="w-auto items-center pb-2.5">
              <Checkbox id="users-sub" checked={params.sub} onCheckedChange={(v) => setParam('sub', v ? '1' : '0')} />
              <FieldLabel htmlFor="users-sub" className="font-normal">Incluir subunidades</FieldLabel>
            </Field>
          )}
          <SimpleSelect id="users-kind" label="Tipo" value={params.kind} onChange={(v) => setParam('kind', v)} options={KINDS} allLabel="Todos" />
          <SimpleSelect id="users-platform" label="Plataforma" value={params.platform} onChange={(v) => setParam('platform', v)} options={PLATFORMS} allLabel="Todas" />
          <SimpleSelect id="users-role" label="Rol" value={params.role} onChange={(v) => setParam('role', v)} options={ROLES} allLabel="Todos" />
          <SimpleSelect id="users-status" label="Estado" value={params.status} onChange={(v) => setParam('status', v)} options={STATUSES} allLabel="Todos" />
          <Button type="button" variant="ghost" onClick={onClear} disabled={!hasFilters}>Limpiar</Button>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}
