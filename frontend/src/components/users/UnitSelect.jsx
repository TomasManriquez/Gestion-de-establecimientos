import React from 'react';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export const ALL = '__all__';

/**
 * Select de unidades con sangría por nivel. `units` ya viene ordenado (lib/units.js).
 * `allLabel` agrega la opción "todas" (para filtros); sin ella es un selector de una unidad.
 */
export default function UnitSelect({ id, units, value, onChange, allLabel, placeholder = 'Seleccione una unidad', invalid = false, ariaLabel }) {
  return (
    <Select value={value || (allLabel ? ALL : undefined)} onValueChange={(v) => onChange(v === ALL ? '' : v)}>
      <SelectTrigger id={id} aria-invalid={invalid || undefined} aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {allLabel && <SelectItem value={ALL}>{allLabel}</SelectItem>}
          {units.map((u) => (
            <SelectItem key={u._id} value={u._id} disabled={u.status !== 'active'}>
              <span style={{ paddingLeft: `${u.depth * 12}px` }}>{u.name}</span>
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
