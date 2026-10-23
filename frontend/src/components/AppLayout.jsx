import React, { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { BarChart3, Building2, LogOut, User, Users, ChevronLeft } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { isIamAdmin } from '@/lib/access';

const STORAGE_KEY = 'sidebar-collapsed';

/** Marca del SLEP: el mosaico de la «L» (mismos colores que el logo). */
function BrandMark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" aria-hidden="true">
      <polygon points="0,0 10,0 10,10 0,10" fill="#76c93b" />
      <polygon points="0,10 10,10 10,22 0,22" fill="#f24f63" />
      <polygon points="10,12 22,22 10,22" fill="#f8c928" />
      <polygon points="0,22 10,22 10,30 0,30" fill="#ff7f96" />
      <polygon points="10,22 22,22 30,30 10,30" fill="#36bce7" />
      <polygon points="22,22 30,22 30,30" fill="#168fd5" />
    </svg>
  );
}

const STRIPE = ['bg-slep-green', 'bg-slep-sky', 'bg-slep-red', 'bg-slep-yellow', 'bg-slep-cyan', 'bg-slep-pink'];

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
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggle = () => setCollapsed((c) => {
    const next = !c;
    try { localStorage.setItem(STORAGE_KEY, next ? '1' : '0'); } catch { /* sin almacenamiento: no pasa nada */ }
    return next;
  });

  const handleLogout = async () => {
    // El servidor revoca las sesiones y borra la cookie HttpOnly; si falla, igual se cierra la vista.
    try { await axios.post('/api/auth/logout'); } catch {}
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
      active ? 'bg-slep-active text-white shadow-md shadow-black/10' : 'text-slate-200 hover:bg-white/10 hover:text-white'
    }`;
  };

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen bg-slep-paper flex text-slep-ink font-sans antialiased">

        {/* SIDEBAR */}
        <aside
          data-collapsed={collapsed ? 'true' : 'false'}
          className={`group/sidebar relative ${collapsed ? 'w-[72px]' : 'w-72'} shrink-0 h-screen sticky top-0 z-20 transition-[width] duration-300 ease-in-out motion-reduce:transition-none`}
        >
          <div className="flex h-full flex-col overflow-hidden bg-slep-navy text-slate-200 shadow-xl border-r border-white/10">

            {/* Brand block */}
            <div className="flex h-[72px] shrink-0 items-center border-b border-white/10 px-3">
              <span className={SLOT}>
                <BrandMark size={32} />
              </span>
              <div className={`min-w-0 flex-1 whitespace-nowrap ${fade}`} aria-hidden={collapsed}>
                <h1 className="text-lg font-extrabold font-outfit text-white leading-tight">SLEP</h1>
                <p className="text-[10px] font-bold text-slep-cyan uppercase tracking-widest leading-none">Llanquihue</p>
              </div>
            </div>

            {/* User profile */}
            <div className="flex h-[72px] shrink-0 items-center border-b border-white/10 bg-black/20 px-3"
              title={collapsed ? (currentUser?.full_name || 'Usuario SLEP') : undefined}>
              <span className={SLOT}>
                <span className="grid size-10 place-items-center rounded-full bg-slep-active text-white border border-white/20 shadow-inner">
                  <User size={20} />
                </span>
              </span>
              <div className={`min-w-0 flex-1 whitespace-nowrap pl-1 ${fade}`} aria-hidden={collapsed}>
                <span className="block text-xs text-slate-300 font-semibold uppercase tracking-wider">
                  {currentUser?.role === 'admin' ? 'Administrador' : 'Usuario'}
                </span>
                <h4 className="text-sm font-bold text-white truncate font-outfit">
                  {currentUser?.full_name || 'Usuario SLEP'}
                </h4>
              </div>
            </div>

            {/* Navigation — NavLink semántico con clase activa automática */}
            <nav aria-label="Principal" className="flex flex-1 flex-col gap-1 px-3 py-4">
              {/* Acceso directo a Matrícula; activo en cualquier /tableros/* (portal futuro) */}
              <RailTip collapsed={collapsed} label="Tableros">
                <NavLink to="/tableros/matricula" className={navClass(pathname.startsWith('/tableros'))} aria-label="Tableros">
                  <span className={SLOT}><BarChart3 size={18} /></span>
                  <span className={`whitespace-nowrap ${fade}`} aria-hidden={collapsed}>Tableros</span>
                </NavLink>
              </RailTip>

              {/* Directorio activo también cuando se está en /establecimientos/:rbd o /editar */}
              <RailTip collapsed={collapsed} label="Directorio de Recintos">
                <NavLink
                  to="/establecimientos"
                  className={navClass(pathname.startsWith('/establecimientos/'))}
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
                      className={`absolute inset-x-0 top-1/2 -translate-y-1/2 whitespace-nowrap px-4 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-300 ${fade}`}>
                      Configuración
                    </p>
                    <div aria-hidden="true"
                      className={`absolute left-1/2 top-1/2 h-px w-8 -translate-x-1/2 bg-white/30 transition-opacity duration-200 motion-reduce:transition-none ${collapsed ? 'opacity-100 delay-100' : 'opacity-0'}`} />
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
            <div className="shrink-0 border-t border-white/10 bg-black/10 px-3 py-4">
              <RailTip collapsed={collapsed} label={logoutLabel}>
                <button
                  type="button"
                  onClick={handleLogout}
                  aria-label={logoutLabel}
                  className="flex h-12 w-full items-center overflow-hidden rounded-xl bg-white/10 text-slate-200 ring-1 ring-inset ring-white/10 transition-colors duration-150 hover:bg-rose-500/20 hover:text-rose-200 font-outfit"
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
            className="absolute -right-3 top-[72px] grid size-6 -translate-y-1/2 place-items-center rounded-full border border-white/20 bg-slep-navy text-slate-300 opacity-0 shadow-sm transition-all duration-200 hover:bg-slep-active hover:text-white focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 group-hover/sidebar:opacity-100 motion-reduce:transition-none"
          >
            <ChevronLeft size={14} className={`transition-transform duration-300 motion-reduce:transition-none ${collapsed ? 'rotate-180' : ''}`} />
          </button>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Barra institucional: logo del SLEP y franja de colores del mosaico */}
          <header className="bg-white">
            <div className="flex items-center gap-4 px-8 py-3 lg:px-10">
              <img src="/slep-llanquihue.png" alt="Servicio Local de Educación Pública Llanquihue" className="h-9 w-auto" />
              <span className="hidden h-8 w-px bg-slep-line sm:block" aria-hidden="true" />
              <p className="hidden text-lg font-bold leading-tight text-slep-ink sm:block">Gestión de Establecimientos</p>
            </div>
            <div className="flex h-1" aria-hidden="true">
              {STRIPE.map((c) => <span key={c} className={`flex-1 ${c}`} />)}
            </div>
          </header>

          {/* MAIN — Outlet renderiza la ruta hija activa */}
          <main className="flex-1 min-w-0 p-8 lg:p-10 overflow-y-auto">
            <div className="max-w-7xl mx-auto">
              <Outlet />
            </div>
          </main>
        </div>

      </div>
    </TooltipProvider>
  );
}
