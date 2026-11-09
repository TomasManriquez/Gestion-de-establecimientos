import React, { useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { Search, Filter, RefreshCw, ChevronRight, SlidersHorizontal } from 'lucide-react';
import { useIsDesktop } from '@/lib/useMediaQuery';

/** Directorio en móvil: una tarjeta por establecimiento; toda ella es el enlace (objetivo táctil amplio). */
function DirectoryCards({ items, loading, from }) {
  if (loading) {
    return (
      <p className="flex items-center justify-center gap-2 px-6 py-12 text-sm text-slate-400">
        <RefreshCw size={16} className="animate-spin text-sky-500" />
        Cargando base de datos...
      </p>
    );
  }
  if (items.length === 0) {
    return <p className="px-6 py-12 text-center text-sm text-slate-400">No se encontraron establecimientos con los criterios ingresados.</p>;
  }
  return (
    <ul className="divide-y divide-slate-100">
      {items.map(est => (
        <li key={est.rbd}>
          <Link to={`/establecimientos/${est.rbd}`} state={{ from }}
            className="flex min-h-16 items-center gap-3 px-4 py-3 transition-colors active:bg-sky-50">
            <div className="min-w-0 flex-1">
              <p className="font-bold leading-snug text-slate-800">{est.name}</p>
              <p className="mt-0.5 text-xs text-slate-500">RBD {est.rbd_full} · {est.comuna}</p>
              <p className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wider ${
                  est.area_type === 'URBANO' ? 'bg-blue-50 text-blue-700' : 'bg-emerald-50 text-emerald-700'
                }`}>{est.area_type}</span>
                {est.category && <span>{est.category}</span>}
              </p>
            </div>
            <ChevronRight size={18} className="shrink-0 text-slate-400" aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

/**
 * Directory — FE-01
 * Filtros sincronizados con la URL via useSearchParams → sobreviven F5 y navegación.
 * Filas usan <Link> semántico → accesible con Ctrl+Click y Cmd+Click.
 * Consume la respuesta paginada del backend {items, total, page, page_size, total_pages}.
 */
export default function Directory() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Leer estado de filtros desde la URL
  const searchTerm  = searchParams.get('search')    || '';
  const comunaF     = searchParams.get('comuna')    || '';
  const areaF       = searchParams.get('area_type') || '';
  const categoryF   = searchParams.get('category')  || '';
  const adpF        = searchParams.get('adp')       || '';
  const page        = parseInt(searchParams.get('page') || '1', 10);

  const [items, setItems] = React.useState([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const isDesktop = useIsDesktop();
  // En móvil solo la búsqueda está a la vista; los demás filtros se despliegan a pedido.
  const [showMore, setShowMore] = React.useState(false);

  const comunas = ['PUERTO VARAS', 'FRUTILLAR', 'FRESIA', 'LLANQUIHUE', 'LOS MUERMOS'];
  const areas   = ['URBANO', 'RURAL'];
  const categories = [
    { label: 'Escuela Diferencial',              value: '0. ESCUELA DIFERENCIAL' },
    { label: 'Sala Cuna',                        value: '1. SALA CUNA' },
    { label: 'J. Infantil - Sala Cuna',          value: '2. J. INFANTIL - S. CUNA' },
    { label: 'Jardín Infantil',                  value: '3. JARDIN INFANTIL' },
    { label: 'Escuela Completa',                 value: '4. ESCUELA COMPLETA' },
    { label: 'Escuela (Curso Combinado)',         value: '5. ESCUELA COMPLETA (CON CURSO COMBINADO)' },
    { label: 'Rural Multigrado',                 value: '6. RURAL MULTIGRADO' },
    { label: 'Liceo Politécnico',                value: '7. LICEO POLITÉCNICO' },
    { label: 'Liceo T-P',                        value: '8. LICEO TÉCNICO - PROFESIONAL' },
    { label: 'Colegio',                          value: '9. COLEGIO' },
  ];
  const adpOptions = ['Si', 'No'];

  // Helper: actualizar un param sin borrar los demás
  const setParam = (key, value) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      // Reiniciar página al cambiar filtros
      if (key !== 'page') next.delete('page');
      return next;
    });
  };

  const handleResetFilters = () => setSearchParams({});

  // Fetch con debounce solo en searchTerm; el resto es inmediato
  useEffect(() => {
    const controller = new AbortController();
    const delay = searchTerm ? 300 : 0;

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const params = {};
        if (searchTerm) params.search   = searchTerm;
        if (comunaF)    params.comuna   = comunaF;
        if (areaF)      params.area_type = areaF;
        if (categoryF)  params.category = categoryF;
        if (adpF)       params.adp      = adpF;
        params.page      = page;
        params.page_size = 100;

        const { data } = await axios.get('/api/establishments', {
          params,
          signal: controller.signal,
        });

        // Backend responde { items, total, page, page_size, total_pages }
        setItems(data.items ?? []);
        setTotal(data.total ?? 0);
      } catch (err) {
        if (err.name !== 'CanceledError') {
          console.error('Error fetching establishments', err);
        }
      } finally {
        setLoading(false);
      }
    }, delay);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchTerm, comunaF, areaF, categoryF, adpF, page]);

  return (
    <div className="space-y-6 animate-fade-in">
      <header>
        <h1 className="text-2xl lg:text-3xl font-extrabold font-outfit text-slate-800 tracking-tight">
          Directorio de Recintos
        </h1>
        <p className="hidden lg:block text-slate-500 text-sm mt-1">
          Busque y filtre la ficha de establecimientos educacionales de la comuna y acceda a su ficha técnica.
        </p>
      </header>

      <div className="flex flex-col lg:flex-row gap-6 items-start">

        {/* Panel de filtros */}
        <aside className="w-full lg:w-64 bg-white p-5 rounded-2xl border border-slate-100 shadow-sm space-y-5 flex-shrink-0">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-extrabold font-outfit text-slate-800 flex items-center gap-2">
              <Filter size={16} className="text-sky-600" />
              Filtros de Búsqueda
            </h3>
            <button
              onClick={handleResetFilters}
              className="text-xs text-sky-600 hover:text-sky-500 font-semibold transition-colors"
            >
              Limpiar
            </button>
          </div>

          {/* Búsqueda */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Buscar</label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                placeholder="RBD o Nombre..."
                value={searchTerm}
                onChange={e => setParam('search', e.target.value)}
                className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 transition-all font-sans"
              />
            </div>
          </div>

          {!isDesktop && (
            <button type="button" onClick={() => setShowMore(s => !s)} aria-expanded={showMore}
              className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-slate-200 text-sm font-semibold text-sky-700">
              <SlidersHorizontal size={16} aria-hidden="true" />
              {showMore ? 'Ocultar filtros' : 'Más filtros'}
            </button>
          )}

          <div className={`space-y-5 ${isDesktop || showMore ? '' : 'hidden'}`}>
          {/* Comuna */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Comuna</label>
            <select
              value={comunaF}
              onChange={e => setParam('comuna', e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Todas las comunas</option>
              {comunas.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Área geográfica */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Área Geográfica</label>
            <select
              value={areaF}
              onChange={e => setParam('area_type', e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Urbano / Rural</option>
              {areas.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>

          {/* Categoría */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Categoría</label>
            <select
              value={categoryF}
              onChange={e => setParam('category', e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Todas las categorías</option>
              {categories.map(c => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>

          {/* ADP */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Licitación ADP</label>
            <select
              value={adpF}
              onChange={e => setParam('adp', e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Cualquier estado</option>
              {adpOptions.map(o => (
                <option key={o} value={o}>{o === 'Si' ? 'Con Cargo ADP' : 'Sin Cargo ADP'}</option>
              ))}
            </select>
          </div>
          </div>
        </aside>

        {/* Tabla del directorio */}
        <div className="flex-1 w-full bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          {isDesktop ? <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100 text-xs font-bold text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-4 font-outfit">RBD</th>
                  <th className="px-6 py-4 font-outfit">Nombre Establecimiento</th>
                  <th className="px-6 py-4 font-outfit">Comuna</th>
                  <th className="px-6 py-4 font-outfit">Área</th>
                  <th className="px-6 py-4 font-outfit">Categoría</th>
                  <th className="px-6 py-4 font-outfit text-center">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm font-sans">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      <div className="flex items-center justify-center gap-2">
                        <RefreshCw size={16} className="animate-spin text-sky-500" />
                        Cargando base de datos...
                      </div>
                    </td>
                  </tr>
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      No se encontraron establecimientos con los criterios ingresados.
                    </td>
                  </tr>
                ) : (
                  items.map(est => (
                    /*
                     * FE-01: <Link> semántico en toda la fila.
                     * preserva los searchParams actuales en el state de navegación
                     * para que el botón "Volver" de la Ficha pueda restaurarlos.
                     */
                    <tr
                      key={est.rbd}
                      className="hover:bg-sky-50/30 transition-colors cursor-pointer group"
                    >
                      <td className="px-6 py-4 font-mono font-semibold text-slate-500 text-xs">
                        {est.rbd_full}
                      </td>
                      <td className="px-6 py-4 font-bold text-slate-800 group-hover:text-sky-600 transition-colors">
                        <Link
                          to={`/establecimientos/${est.rbd}`}
                          state={{ from: '?' + searchParams.toString() }}
                          className="hover:underline"
                        >
                          {est.name}
                        </Link>
                      </td>
                      <td className="px-6 py-4 text-slate-500">{est.comuna}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider ${
                          est.area_type === 'URBANO'
                            ? 'bg-blue-50 text-blue-700'
                            : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {est.area_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-500 text-xs truncate max-w-[150px]">
                        {est.category || '-'}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <Link
                          to={`/establecimientos/${est.rbd}`}
                          state={{ from: '?' + searchParams.toString() }}
                          className="text-sky-600 group-hover:translate-x-1 transition-transform inline-flex items-center gap-1 font-semibold text-xs"
                        >
                          Ficha <ChevronRight size={14} />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div> : <DirectoryCards items={items} loading={loading} from={'?' + searchParams.toString()} />}

          <div className="p-4 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 font-sans">
            <span>Mostrando <b>{items.length}</b> de <b>{total}</b> establecimientos</span>
          </div>
        </div>
      </div>
    </div>
  );
}
