import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { School, PieChart, Building2, LogOut, User } from 'lucide-react';

/**
 * AppLayout — FE-04
 * Layout compartido para todas las rutas autenticadas.
 * Renderiza el Sidebar con NavLinks semánticos y el área principal con <Outlet />.
 * NavLink aplica clase activa automáticamente según la ruta actual.
 */
export default function AppLayout({ currentUser, onLogout }) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try { await axios.post('/api/auth/logout'); } catch {}
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    onLogout();
    navigate('/login', { replace: true });
  };

  // Clases para NavLink activo e inactivo
  const navClass = ({ isActive }) =>
    `flex items-center gap-3.5 w-full px-4 py-3 rounded-xl text-sm font-bold transition-all font-outfit ${
      isActive
        ? 'bg-sky-600 text-white shadow-lg shadow-sky-600/10'
        : 'text-slate-300 hover:bg-slate-800 hover:text-white'
    }`;

  return (
    <div className="min-h-screen bg-slate-50 flex text-slate-800 font-sans antialiased">

      {/* SIDEBAR */}
      <aside className="w-72 bg-slate-900 text-slate-300 h-screen sticky top-0 flex flex-col z-20 shadow-xl border-r border-slate-800">

        {/* Brand block */}
        <div className="p-6 border-b border-slate-800 flex items-center gap-3">
          <div className="p-2.5 bg-sky-600 text-white rounded-xl shadow-md shadow-sky-600/10">
            <School size={24} />
          </div>
          <div>
            <h1 className="text-lg font-extrabold font-outfit text-white leading-tight">SLEP</h1>
            <p className="text-[10px] font-bold text-sky-400 uppercase tracking-widest leading-none">
              Llanquihue
            </p>
          </div>
        </div>

        {/* User profile */}
        <div className="p-5 border-b border-slate-800 flex items-center gap-3 bg-slate-950/40">
          <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-sky-400 border border-slate-700 shadow-inner">
            <User size={20} />
          </div>
          <div className="min-w-0 flex-1">
            <span className="block text-xs text-slate-500 font-semibold uppercase tracking-wider">
              {currentUser?.role === 'admin' ? 'Administrador' : 'Usuario'}
            </span>
            <h4 className="text-sm font-bold text-white truncate font-outfit">
              {currentUser?.full_name || 'Usuario SLEP'}
            </h4>
          </div>
        </div>

        {/* Navigation — NavLink semántico con clase activa automática */}
        <nav className="p-5 flex-1 space-y-2">
          <NavLink to="/dashboard" className={navClass}>
            <PieChart size={18} />
            Panel General
          </NavLink>

          {/* Directorio activo también cuando se está en /establecimientos/:rbd o /editar */}
          <NavLink
            to="/establecimientos"
            className={({ isActive }) =>
              navClass({
                isActive:
                  isActive ||
                  window.location.pathname.startsWith('/establecimientos/'),
              })
            }
          >
            <Building2 size={18} />
            Directorio de Recintos
          </NavLink>
        </nav>

        {/* Logout */}
        <div className="p-5 border-t border-slate-800 bg-slate-950/20">
          <button
            onClick={handleLogout}
            className="flex items-center justify-center gap-2.5 w-full py-3 bg-slate-800 hover:bg-rose-950/30 hover:text-rose-400 text-slate-400 hover:border-rose-950/40 border border-slate-700/50 font-bold rounded-xl text-xs transition-all uppercase tracking-wider font-outfit"
          >
            <LogOut size={14} />
            Cerrar Sesión
          </button>
        </div>
      </aside>

      {/* MAIN — Outlet renderiza la ruta hija activa */}
      <main className="flex-1 min-w-0 p-8 lg:p-10 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          <Outlet />
        </div>
      </main>

    </div>
  );
}
