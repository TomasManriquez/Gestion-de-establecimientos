import React from 'react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Checkbox } from '@/components/ui/checkbox';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { formatExact, formatRelative, fullNameOf, initialsOf, POSITION_LABELS, statusInfo } from '@/lib/format';
import PermissionsCell from './PermissionsCell';
import UserRowActions from './UserRowActions';

const DOT = { success: 'bg-success', primary: 'bg-primary', warning: 'bg-warning', muted: 'bg-muted-foreground' };

function WhereCell({ user, unitsById, establishmentsByRbd }) {
  if (user.is_slep_staff) {
    const unit = unitsById[user.unit_id];
    return (
      <>
        <div className="truncate text-sm font-medium" title={unit?.name ?? ''}>{unit?.name ?? 'Unidad sin nombre'}</div>
        <div className="truncate text-xs text-muted-foreground">{unit?.code ?? ''}</div>
      </>
    );
  }
  const est = establishmentsByRbd[user.rbd];
  const positions = (user.positions ?? []).map((p) => POSITION_LABELS[p] ?? p).join(', ');
  return (
    <>
      <div className="truncate text-sm font-medium" title={est?.name ?? ''}>{est?.name ?? `RBD ${user.rbd}`}</div>
      <div className="truncate text-xs text-muted-foreground" title={`RBD ${user.rbd} · ${positions}`}>RBD {user.rbd} · {positions}</div>
    </>
  );
}

/**
 * Tabla de usuarios. Columnas de ancho fijo y celdas de una línea: la altura de la fila no depende
 * de cuántos permisos tenga el usuario. La última actividad es columna propia (relativa, con la
 * fecha exacta en el `title`) y el estado es un punto con una etiqueta corta.
 */
export default function UsersTable({
  items, selected, onToggle, onToggleAll, unitsById, establishmentsByRbd, currentUserId,
  onEdit, onAccess, onDisable, onEnable,
}) {
  const allChecked = items.length > 0 && items.every((u) => selected[u._id]);
  const someChecked = items.some((u) => selected[u._id]);
  return (
    <Table className="table-fixed min-w-[900px]">
      <colgroup>
        <col className="w-11" />
        <col className="w-72" />
        <col />
        <col className="w-44" />
        <col className="w-28" />
        <col className="w-28" />
        <col className="w-14" />
      </colgroup>
      <TableHeader>
        <TableRow>
          <TableHead className="px-4">
            <Checkbox aria-label="Seleccionar todos los usuarios de esta página"
              checked={allChecked ? true : (someChecked ? 'indeterminate' : false)}
              onCheckedChange={() => onToggleAll(!allChecked)} />
          </TableHead>
          <TableHead className="px-2">Usuario</TableHead>
          <TableHead className="px-2">Unidad o establecimiento</TableHead>
          <TableHead className="px-2">Permisos</TableHead>
          <TableHead className="px-2 whitespace-nowrap">Últ. actividad</TableHead>
          <TableHead className="px-2">Estado</TableHead>
          <TableHead className="px-2"><span className="sr-only">Acciones</span></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((user) => {
          const fullName = fullNameOf(user);
          const status = statusInfo(user);
          return (
            <TableRow key={user._id} data-state={selected[user._id] ? 'selected' : undefined} className="h-16">
              <TableCell className="px-4 py-0">
                <Checkbox aria-label={`Seleccionar a ${fullName}`} checked={!!selected[user._id]} onCheckedChange={() => onToggle(user._id)} />
              </TableCell>
              <TableCell className="px-2 py-0">
                <div className="flex items-center gap-3 min-w-0">
                  <Avatar>
                    <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">{initialsOf(user)}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold" title={fullName}>{fullName}</div>
                    <div className="truncate text-xs text-muted-foreground" title={user.email}>{user.email}</div>
                  </div>
                </div>
              </TableCell>
              <TableCell className="px-2 py-0 min-w-0"><WhereCell user={user} unitsById={unitsById} establishmentsByRbd={establishmentsByRbd} /></TableCell>
              <TableCell className="px-2 py-0"><PermissionsCell user={user} fullName={fullName} /></TableCell>
              <TableCell className="px-2 py-0">
                <time className="text-xs text-muted-foreground whitespace-nowrap underline decoration-dotted underline-offset-4"
                  dateTime={user.last_activity_at ?? undefined} title={formatExact(user.last_activity_at)}>
                  {formatRelative(user.last_activity_at)}
                </time>
              </TableCell>
              <TableCell className="px-2 py-0">
                <span className="inline-flex items-center gap-2 text-xs font-medium whitespace-nowrap" title={status.title}>
                  <span className={cn('size-2 rounded-full', DOT[status.tone])} aria-hidden="true" />
                  {status.label}
                </span>
              </TableCell>
              <TableCell className="px-2 py-0">
                <UserRowActions user={user} fullName={fullName} isSelf={user._id === currentUserId}
                  onEdit={onEdit} onAccess={onAccess} onDisable={onDisable} onEnable={onEnable} />
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
