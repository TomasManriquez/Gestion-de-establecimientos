import React from 'react';
import { KeyRound, MailPlus, MoreVertical, Pencil, ShieldCheck, UserCheck, UserX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

/**
 * Acciones de una fila. "Reenviar invitación" y "Restablecer contraseña" quedan deshabilitadas
 * hasta que exista el envío de correo (F4): se muestran para que el menú sea el definitivo.
 */
export default function UserRowActions({ user, fullName, isSelf, onEdit, onAccess, onDisable, onEnable }) {
  const disabled = user.status === 'disabled';
  const canResend = user.status === 'invited';
  const canReset = user.status === 'active';
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="icon" aria-label={`Acciones de ${fullName}`}>
          <MoreVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuItem onSelect={() => onEdit(user)}><Pencil />Editar datos</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onAccess(user)}><ShieldCheck />Gestionar accesos</DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem disabled><MailPlus />Reenviar invitación{canResend ? ' (próximamente)' : ''}</DropdownMenuItem>
          <DropdownMenuItem disabled><KeyRound />Restablecer contraseña{canReset ? ' (próximamente)' : ''}</DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          {disabled ? (
            <DropdownMenuItem onSelect={() => onEnable(user)}><UserCheck />Reactivar</DropdownMenuItem>
          ) : (
            <DropdownMenuItem className="text-destructive focus:text-destructive" disabled={isSelf} onSelect={() => onDisable(user)}>
              <UserX />{isSelf ? 'Desactivar (eres tú)' : 'Desactivar'}
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
