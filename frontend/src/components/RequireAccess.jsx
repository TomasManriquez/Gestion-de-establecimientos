import React from 'react';
import { Link, Outlet } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { hasAccess } from '@/lib/access';

/**
 * Guard de rol (compone con ProtectedRoute, que no se modifica). Si el usuario no tiene un rol
 * permitido en la plataforma muestra una pantalla de «Sin acceso» en vez de redirigir (evita
 * bucles). Es solo experiencia de usuario: el backend responde 403 igualmente (`require_access`).
 */
export default function RequireAccess({ currentUser, platform, roles }) {
  if (hasAccess(currentUser, platform, roles)) return <Outlet />;
  return (
    <Empty className="py-24">
      <EmptyHeader>
        <EmptyMedia variant="icon"><ShieldAlert /></EmptyMedia>
        <EmptyTitle>Sin acceso a esta sección</EmptyTitle>
        <EmptyDescription>Tu cuenta no tiene permiso para administrar usuarios. Si lo necesitas, solicítalo a un administrador.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button asChild variant="outline"><Link to="/dashboard">Volver al panel</Link></Button>
      </EmptyContent>
    </Empty>
  );
}
