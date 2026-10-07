import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { permissionChips } from '@/lib/format';

/**
 * Permisos en una sola línea: el chip principal y, si hay más, un contador "+N" que abre el detalle.
 * La fila mantiene la misma altura sin importar cuántas plataformas tenga el usuario.
 */
export default function PermissionsCell({ user, fullName }) {
  const chips = permissionChips(user.access);
  if (chips.length === 0) {
    return <Badge variant="outline" className="text-muted-foreground border-dashed">Sin accesos</Badge>;
  }
  const [main, ...rest] = chips;
  return (
    <div className="flex items-center gap-1.5">
      <Badge variant={main.variant} className="max-w-[116px] truncate" title={main.label}>{main.label}</Badge>
      {rest.length > 0 && (
        <Popover>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="sm" className="h-6 px-2 text-xs rounded-full"
              aria-label={`Ver los ${chips.length} permisos de ${fullName}`}>
              +{rest.length}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64" aria-label={`Permisos de ${fullName}`}>
            <div className="flex flex-col gap-3">
              <p className="text-xs font-semibold">Permisos de {fullName}</p>
              <ul className="flex flex-col gap-2">
                {chips.map((c) => (
                  <li key={c.platformId} className="flex items-center justify-between gap-3 text-sm">
                    <span>{c.platform}</span>
                    <Badge variant={c.variant}>{c.role}</Badge>
                  </li>
                ))}
              </ul>
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
