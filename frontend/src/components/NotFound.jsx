import React from 'react';
import { Link } from 'react-router-dom';
import { Home } from 'lucide-react';

/**
 * NotFound — FE-04
 * Renderizada para cualquier ruta no definida (path="*").
 */
export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-6 p-8">
      <div className="text-center space-y-3">
        <span className="text-8xl font-extrabold text-slate-200 font-outfit">404</span>
        <h1 className="text-2xl font-bold text-slate-700 font-outfit">Página no encontrada</h1>
        <p className="text-slate-400 text-sm max-w-sm">
          La ruta que ingresaste no existe o fue movida.
        </p>
      </div>
      <Link
        to="/dashboard"
        className="flex items-center gap-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-xl text-sm transition-all"
      >
        <Home size={16} />
        Volver al inicio
      </Link>
    </div>
  );
}
