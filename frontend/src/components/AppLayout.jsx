import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { School, PieChart, Building2, LogOut, User, Users, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { isIamAdmin } from '@/lib/access';

const STORAGE_KEY = 'sidebar-collapsed';

function readCollapsed() {
  try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
}

/**
 * AppLayout — FE-04
 * Layout compartido para todas las rutas autenticadas.
 * Renderiza el Sidebar con NavLinks semánticos y el área principal con <Outlet />.
 * El sidebar se puede colapsar a una columna de íconos; el contenido se ensancha solo (flex).
 */
export default function AppLayout({ currentUser, onLogout }) {
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggle = () => setCollapsed((c) => {
    const next = !c;
    try { localStorage.setItem(STORAGE_KEY, next ? '1' : '0'); } catch { /* sin almacenamiento: no pasa nada */ }
    return next;
  });

  const handleLogout = async () => {
    try { await axios.post('/api/auth/logout'); } catch {}
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    onLogout();
    navigate('/login', { replace: true });
  };

  const logoutLabel = 'Cerrar Sesión';

  // Clases del NavLink. Colapsado: ícono centrado en un cuadro de 48×48, accionable.
  const navClass = (forceActive = false) => ({ isActive }) => {
    const active = isActive || forceActive;
    return `flex items-center rounded-xl text-sm font-bold transition-all font-outfit ${
      collapsed ? 'justify-center w-12 h-12 shrink-0' : 'gap-3.5 w-full px-4 py-3'
    } ${active ? 'bg-sky-600 text-white shadow-lg shadow-sky-600/10' : 'text-slate-300 hover:bg-slate-800 hover:text-white'}`;
  };
  // Colapsado: el nombre de la sección sale como tooltip (el nombre accesible es el aria-label).
  const withTip = (label, node) => (collapsed ? (
    <Tooltip>
      <TooltipTrigger asChild>{node}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  ) : node);

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-slate-50 flex text-slate-800 font-sans antialiased">

        {/* SIDEBAR */}
        <aside
          data-collapsed={collapsed ? 'true' : 'false'}
          className={`${collapsed ? 'w-[72px]' : 'w-72'} shrink-0 bg-slate-900 text-slate-300 h-screen sticky top-0 flex flex-col z-20 shadow-xl border-r border-slate-800 transition-[width] duration-200`}
        >

          {/* Brand block */}
          <div className={`border-b border-slate-800 flex items-center ${collapsed ? 'justify-center py-5' : 'p-6 gap-3'}`}>
            <div className="p-2.5 bg-sky-600 text-white rounded-xl shadow-md shadow-sky-600/10">
              <School size={24} />
            </div>
            {!collapsed && (
              <div className="flex-1">
                <h1 className="text-lg font-extrabold font-outfit text-white leading-tight">SLEP</h1>
                <p className="text-[10px] font-bold text-sky-400 uppercase tracking-widest leading-none">
                  Llanquihue
                </p>
              </div>
            )}
          </div>

          {/* Alternar */}
          <div className={`border-b border-slate-800 flex ${collapsed ? 'justify-center py-2.5' : 'justify-end px-4 py-2.5'}`}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={toggle}
                  aria-label={collapsed ? 'Expandir barra lateral' : 'Contraer barra lateral'}
                  aria-expanded={!collapsed}
                  className="flex items-center justify-center w-11 h-11 rounded-xl border border-slate-800 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
                >
                  {collapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">{collapsed ? 'Expandir barra lateral' : 'Contraer barra lateral'}</TooltipContent>
            </Tooltip>
          </div>

          {/* User profile */}
          <div className={`border-b border-slate-800 flex items-center bg-slate-950/40 ${collapsed ? 'justify-center py-4' : 'p-5 gap-3'}`}>
            <div className="w-10 h-10 shrink-0 rounded-full bg-slate-800 flex items-center justify-center text-sky-400 border border-slate-700 shadow-inner" title={collapsed ? (currentUser?.full_name || 'Usuario SLEP') : undefined}>
              <User size={20} />
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <span className="block text-xs text-slate-500 font-semibold uppercase tracking-wider">
                  {currentUser?.role === 'admin' ? 'Administrador' : 'Usuario'}
                </span>
                <h4 className="text-sm font-bold text-white truncate font-outfit">
                  {currentUser?.full_name || 'Usuario SLEP'}
                </h4>
              </div>
            )}
          </div>

          {/* Navigation — NavLink semántico con clase activa automática */}
          <nav aria-label="Principal" className={`flex-1 flex flex-col gap-2 ${collapsed ? 'items-center py-4' : 'p-5'}`}>
            {withTip('Panel General', (
              <NavLink to="/dashboard" className={navClass()} aria-label={collapsed ? 'Panel General' : undefined}>
                <PieChart size={18} />
                {!collapsed && 'Panel General'}
              </NavLink>
            ))}

            {/* Directorio activo también cuando se está en /establecimientos/:rbd o /editar */}
            {withTip('Directorio de Recintos', (
              <NavLink
                to="/establecimientos"
                className={navClass(window.location.pathname.startsWith('/establecimientos/'))}
                aria-label={collapsed ? 'Directorio de Recintos' : undefined}
              >
                <Building2 size={18} />
                {!collapsed && 'Directorio de Recintos'}
              </NavLink>
            ))}

            {isIamAdmin(currentUser) && (
              <>
                {collapsed
                  ? <div role="separator" aria-label="Configuración" className="my-2 h-px w-8 bg-slate-700" />
                  : <p className="mt-5 px-4 pb-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">Configuración</p>}
                {withTip('Usuarios', (
                  <NavLink to="/configuracion/usuarios" className={navClass()} aria-label={collapsed ? 'Usuarios' : undefined}>
                    <Users size={18} />
                    {!collapsed && 'Usuarios'}
                  </NavLink>
                ))}
              </>
            )}
          </nav>

          {/* Logout */}
          <div className={`border-t border-slate-800 bg-slate-950/20 flex ${collapsed ? 'justify-center py-4' : 'p-5'}`}>
            {collapsed ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={handleLogout}
                    aria-label={logoutLabel}
                    className="flex items-center justify-center w-12 h-12 bg-slate-800 hover:bg-rose-950/30 hover:text-rose-400 text-slate-400 border border-slate-700/50 rounded-xl transition-all"
                  >
                    <LogOut size={16} />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">{logoutLabel}</TooltipContent>
              </Tooltip>
            ) : (
              <button
                onClick={handleLogout}
                className="flex items-center justify-center gap-2.5 w-full py-3 bg-slate-800 hover:bg-rose-950/30 hover:text-rose-400 text-slate-400 hover:border-rose-950/40 border border-slate-700/50 font-bold rounded-xl text-xs transition-all uppercase tracking-wider font-outfit"
              >
                <LogOut size={14} />
                {logoutLabel}
              </button>
            )}
          </div>
        </aside>

        {/* MAIN — Outlet renderiza la ruta hija activa */}
        <main className="flex-1 min-w-0 p-8 lg:p-10 overflow-y-auto">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>

      </div>
    </TooltipProvider>
  );
}
