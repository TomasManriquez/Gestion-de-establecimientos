import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';

/**
 * ProtectedRoute — FE-04
 * Guarda rutas privadas verificando autenticación antes de renderizar.
 * - checkingAuth=true → muestra spinner, no redirige prematuramente.
 * - isAuthenticated=false → redirige a /login guardando la ruta de origen en ?from=...
 * - isAuthenticated=true → renderiza el <Outlet /> (la ruta hija).
 */
export default function ProtectedRoute({ isAuthenticated, checkingAuth }) {
  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center gap-3">
        <RefreshCw size={32} className="animate-spin text-sky-500" />
        <p className="text-sm font-semibold text-slate-400">Verificando sesión segura...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Guardar la ruta de destino original para redirigir tras login
    const from = window.location.pathname + window.location.search;
    const loginUrl = from && from !== '/'
      ? `/login?from=${encodeURIComponent(from)}`
      : '/login';
    return <Navigate to={loginUrl} replace />;
  }

  return <Outlet />;
}
