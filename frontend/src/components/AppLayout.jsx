import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { School, PieChart, Building2, LogOut, User, Users, ChevronLeft } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { isIamAdmin } from '@/lib/access';

const STORAGE_KEY = 'sidebar-collapsed';

function readCollapsed() {
  try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
}

/** Slot cuadrado de 48 px: con el riel de 72 px y px-3, el ícono queda en el mismo píxel abierto o cerrado. */
const SLOT = 'grid size-12 shrink-0 place-items-center';

/**
 * Tooltip que solo se abre con la barra colapsada. El árbol de nodos es el mismo en ambos estados.
 * El disparador es un <span> envolvente: `Slot` de Radix convertiría en texto el `className`
 * de función de NavLink y se perdería la clase activa.
 */
function RailTip({ collapsed, label, children }) {
  return (
    <Tooltip open={collapsed ? undefined : false}>
      <TooltipTrigger asChild><span className="block">{children}</span></TooltipTrigger>
      <TooltipContent side="right" sideOffset={10}>{label}</TooltipContent>
    </Tooltip>
  );
}

/**
 * AppLayout — FE-04
 * Layout compartido para todas las rutas autenticadas.
 * Renderiza el Sidebar con NavLinks semánticos y el área principal con <Outlet />.
 *
 * El sidebar se colapsa a un riel de íconos. Para que la animación sea fluida la geometría de
 * cada ítem no cambia entre estados: solo se anima el ancho de la barra y la opacidad de los
 * textos (que quedan recortados por `overflow-hidden`). El contenido se ensancha solo (flex).
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
  const toggleLabel = collapsed ? 'Expandir barra lateral' : 'Contraer barra lateral';

  // Texto que se desvanece al colapsar; al expandir espera a que la barra ya haya ganado ancho.
  const fade = `transition-opacity duration-200 motion-reduce:transition-none ${collapsed ? 'opacity-0' : 'opacity-100 delay-100'}`;

  // Clases del NavLink: altura y slot fijos, solo cambia el color.
  const navClass = (forceActive = false) => ({ isActive }) => {
    const active = isActive || forceActive;
    return `flex h-12 w-full items-center overflow-hidden rounded-xl text-sm font-bold font-outfit transition-colors duration-150 ${
      active ? 'bg-sky-600 text-white shadow-md shadow-sky-600/10' : 'text-slate-300 hover:bg-slate-800/70 hover:text-white'
    }`;
  };

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen bg-slate-50 flex text-slate-800 font-sans antialiased">

        {/* SIDEBAR */}
        <aside
          data-collapsed={collapsed ? 'true' : 'false'}
          className={`group/sidebar relative ${collapsed ? 'w-[72px]' : 'w-72'} shrink-0 h-screen sticky top-0 z-20 transition-[width] duration-300 ease-in-out motion-reduce:transition-none`}
        >
          <div className="flex h-full flex-col overflow-hidden bg-slate-900 text-slate-300 shadow-xl border-r border-slate-800">

            {/* Brand block */}
            <div className="flex h-[72px] shrink-0 items-center border-b border-slate-800 px-3">
              <span className={SLOT}>
                <span className="grid size-11 place-items-center rounded-xl bg-sky-600 text-white shadow-md shadow-sky-600/10">
                  <School size={22} />
                </span>
              </span>
              <div className={`min-w-0 flex-1 whitespace-nowrap ${fade}`} aria-hidden={collapsed}>
                <h1 className="text-lg font-extrabold font-outfit text-white leading-tight">SLEP</h1>
                <p className="text-[10px] font-bold text-sky-400 uppercase tracking-widest leading-none">Llanquihue</p>
              </div>
            </div>

            {/* User profile */}
            <div className="flex h-[72px] shrink-0 items-center border-b border-slate-800 bg-slate-950/40 px-3"
              title={collapsed ? (currentUser?.full_name || 'Usuario SLEP') : undefined}>
              <span className={SLOT}>
                <span className="grid size-10 place-items-center rounded-full bg-slate-800 text-sky-400 border border-slate-700 shadow-inner">
                  <User size={20} />
                </span>
              </span>
              <div className={`min-w-0 flex-1 whitespace-nowrap pl-1 ${fade}`} aria-hidden={collapsed}>
                <span className="block text-xs text-slate-500 font-semibold uppercase tracking-wider">
                  {currentUser?.role === 'admin' ? 'Administrador' : 'Usuario'}
                </span>
                <h4 className="text-sm font-bold text-white truncate font-outfit">
                  {currentUser?.full_name || 'Usuario SLEP'}
                </h4>
              </div>
            </div>

            {/* Navigation — NavLink semántico con clase activa automática */}
            <nav aria-label="Principal" className="flex flex-1 flex-col gap-1 px-3 py-4">
              <RailTip collapsed={collapsed} label="Panel General">
                <NavLink to="/dashboard" className={navClass()} aria-label="Panel General">
                  <span className={SLOT}><PieChart size={18} /></span>
                  <span className={`whitespace-nowrap ${fade}`} aria-hidden={collapsed}>Panel General</span>
                </NavLink>
              </RailTip>

              {/* Directorio activo también cuando se está en /establecimientos/:rbd o /editar */}
              <RailTip collapsed={collapsed} label="Directorio de Recintos">
                <NavLink
                  to="/establecimientos"
                  className={navClass(window.location.pathname.startsWith('/establecimientos/'))}
                  aria-label="Directorio de Recintos"
                >
                  <span className={SLOT}><Building2 size={18} /></span>
                  <span className={`whitespace-nowrap ${fade}`} aria-hidden={collapsed}>Directorio de Recintos</span>
                </NavLink>
              </RailTip>

              {isIamAdmin(currentUser) && (
                <>
                  {/* Encabezado de sección: el texto se desvanece y aparece una línea en su lugar */}
                  <div className="relative mt-3 h-8 shrink-0">
                    <p aria-hidden={collapsed}
                      className={`absolute inset-x-0 top-1/2 -translate-y-1/2 whitespace-nowrap px-4 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400 ${fade}`}>
                      Configuración
                    </p>
                    <div aria-hidden="true"
                      className={`absolute left-1/2 top-1/2 h-px w-8 -translate-x-1/2 bg-slate-700 transition-opacity duration-200 motion-reduce:transition-none ${collapsed ? 'opacity-100 delay-100' : 'opacity-0'}`} />
                  </div>
                  <RailTip collapsed={collapsed} label="Usuarios">
                    <NavLink to="/configuracion/usuarios" className={navClass()} aria-label="Usuarios">
                      <span className={SLOT}><Users size={18} /></span>
                      <span className={`whitespace-nowrap ${fade}`} aria-hidden={collapsed}>Usuarios</span>
                    </NavLink>
                  </RailTip>
                </>
              )}
            </nav>

            {/* Logout */}
            <div className="shrink-0 border-t border-slate-800 bg-slate-950/20 px-3 py-4">
              <RailTip collapsed={collapsed} label={logoutLabel}>
                <button
                  type="button"
                  onClick={handleLogout}
                  aria-label={logoutLabel}
                  className="flex h-12 w-full items-center overflow-hidden rounded-xl bg-slate-800 text-slate-400 ring-1 ring-inset ring-slate-700/50 transition-colors duration-150 hover:bg-rose-950/30 hover:text-rose-400 font-outfit"
                >
                  <span className={SLOT}><LogOut size={16} /></span>
                  <span className={`whitespace-nowrap text-xs font-bold uppercase tracking-wider ${fade}`} aria-hidden={collapsed}>{logoutLabel}</span>
                </button>
              </RailTip>
            </div>
          </div>

          {/* Tirador sobre el borde derecho: discreto, aparece al pasar el mouse o con el foco del teclado */}
          <button
            type="button"
            onClick={toggle}
            aria-label={toggleLabel}
            aria-expanded={!collapsed}
            title={toggleLabel}
            className="absolute -right-3 top-[72px] grid size-6 -translate-y-1/2 place-items-center rounded-full border border-slate-700 bg-slate-900 text-slate-400 opacity-0 shadow-sm transition-all duration-200 hover:bg-slate-800 hover:text-white focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 group-hover/sidebar:opacity-100 motion-reduce:transition-none"
          >
            <ChevronLeft size={14} className={`transition-transform duration-300 motion-reduce:transition-none ${collapsed ? 'rotate-180' : ''}`} />
          </button>
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
