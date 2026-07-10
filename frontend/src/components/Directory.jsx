import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Filter, RefreshCw, ChevronRight, School } from 'lucide-react';

export default function Directory({ onSelectEstablishment }) {
  const [establishments, setEstablishments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Filters state
  const [filters, setFilters] = useState({
    comuna: '',
    area_type: '',
    category: '',
    adp: ''
  });

  // Filter options derived from a standard set or dynamically loaded
  // To avoid complex APIs, we can just declare the standard local options
  const comunas = ["PUERTO VARAS", "FRUTILLAR", "FRESIA", "LLANQUIHUE", "LOS MUERMOS"];
  const areas = ["URBANO", "RURAL"];
  const categories = [
    { label: "Escuela Diferencial",  value: "0. ESCUELA DIFERENCIAL" },
    { label: "Sala Cuna",  value: "1. SALA CUNA" },
    { label: "J. Infantil - Sala Cuna", value: "2. J. INFANTIL - S. CUNA" },
    { label: "Jardín Infantil", value: "3. JARDIN INFANTIL" },
    { label: "Escuela Completa", value: "4. ESCUELA COMPLETA" },
    { label: "Escuela (Curso Combinado)", value: "5. ESCUELA COMPLETA (CON CURSO COMBINADO)" },
    { label: "Rural Multigrado", value: "6. RURAL MULTIGRADO" },
    { label: "Liceo Politécnico", value: "7. LICEO POLITÉCNICO" },
    { label: "Liceo T-P", value: "8. LICEO TÉCNICO - PROFESIONAL" },
    { label: "Colegio", value: "9. COLEGIO" },
  
  ];
  const adpOptions = ["Si", "No"];

  const fetchEstablishments = async () => {
    setLoading(true);
    try {
      const params = {};
      if (searchTerm) params.search = searchTerm;
      if (filters.comuna) params.comuna = filters.comuna;
      if (filters.area_type) params.area_type = filters.area_type;
      if (filters.category) params.category = filters.category;
      if (filters.adp) params.adp = filters.adp;

      const response = await axios.get('/api/establishments', { params });
      setEstablishments(response.data);
    } catch (err) {
      console.error('Error fetching establishments', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Debounce search slightly
    const delayDebounceFn = setTimeout(() => {
      fetchEstablishments();
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm, filters]);

  const handleResetFilters = () => {
    setSearchTerm('');
    setFilters({
      comuna: '',
      area_type: '',
      category: '',
      adp: ''
    });
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <header>
        <h1 className="text-3xl font-extrabold font-outfit text-slate-800 tracking-tight">
          Directorio de Recintos
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Busque y filtre la ficha de establecimientos educacionales de la comuna y acceda a su ficha técnica.
        </p>
      </header>

      <div className="flex flex-col lg:flex-row gap-6 items-start">
        
        {/* Filters Panel (Sidebar style inside layout) */}
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

          {/* Search bar */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Buscar</label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                placeholder="RBD o Nombre..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 transition-all font-sans"
              />
            </div>
          </div>

          {/* Comuna filter */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Comuna</label>
            <select
              value={filters.comuna}
              onChange={(e) => setFilters(prev => ({ ...prev, comuna: e.target.value }))}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Todas las comunas</option>
              {comunas.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Area Type filter */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Área Geográfica</label>
            <select
              value={filters.area_type}
              onChange={(e) => setFilters(prev => ({ ...prev, area_type: e.target.value }))}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Urbano / Rural</option>
              {areas.map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          {/* Category filter */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Categoría</label>
            <select
              value={filters.category}
              onChange={(e) => setFilters(prev => ({ ...prev, category: e.target.value }))}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Todas las categorías</option>
              {categories.map(c => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* ADP filter */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-500">Licitación ADP</label>
            <select
              value={filters.adp}
              onChange={(e) => setFilters(prev => ({ ...prev, adp: e.target.value }))}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-sky-500 font-sans"
            >
              <option value="">Cualquier estado</option>
              {adpOptions.map(o => (
                <option key={o} value={o}>{o === 'Si' ? 'Con Cargo ADP' : 'Sin Cargo ADP'}</option>
              ))}
            </select>
          </div>
        </aside>

        {/* Directory Table */}
        <div className="flex-1 w-full bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
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
                ) : establishments.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      No se encontraron establecimientos con los criterios ingresados.
                    </td>
                  </tr>
                ) : (
                  establishments.map((est) => (
                    <tr 
                      key={est.rbd} 
                      onClick={() => onSelectEstablishment(est.rbd)}
                      className="hover:bg-sky-50/30 transition-colors cursor-pointer group"
                    >
                      <td className="px-6 py-4 font-mono font-semibold text-slate-500 text-xs">
                        {est.rbd_full}
                      </td>
                      <td className="px-6 py-4 font-bold text-slate-800 group-hover:text-sky-600 transition-colors">
                        {est.name}
                      </td>
                      <td className="px-6 py-4 text-slate-500">
                        {est.comuna}
                      </td>
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
                        {est.general_info.category || '-'}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button className="text-sky-600 group-hover:translate-x-1 transition-transform inline-flex items-center gap-1 font-semibold text-xs">
                          Ficha <ChevronRight size={14} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          <div className="p-4 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 font-sans">
            <span>Mostrando <b>{establishments.length}</b> establecimientos</span>
          </div>
        </div>

      </div>
    </div>
  );
}
