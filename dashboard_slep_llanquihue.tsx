import React, { useState, useMemo } from 'react';
import { 
  BarChart3, 
  Users, 
  MapPin, 
  Building2, 
  Search, 
  Filter, 
  ChevronRight, 
  ArrowLeft,
  Upload,
  PieChart,
  School,
  GraduationCap
} from 'lucide-react';

// --- DATOS DE MUESTRA BASADOS EN TUS CSV ---
const initialData = [
  {
    RBD: '7720', NOM_ESTABLECIMIENTO: 'LICEO BICENTENARIO PEDRO AGUIRRE CERDA', COMUNA: 'PUERTO VARAS', TIPO_AREA: 'URBANO',
    DIRECTOR: 'Patricio Vargas Lara', CATEGORIA: 'Liceo', Cobertura: 'I a IV Medio', ADP: 'Sí', PAME: 'Claudia Hofmann',
    MATRICULA_2026: 450, MATRICULA_2025: 430, PROMEDIO_ASIST_2025: '88%', IVE_BASICA: 0, IVE_MEDIA: 85, NUM_DOCENTES: 40, NUM_ASISTENTES: 20
  },
  {
    RBD: '35154', NOM_ESTABLECIMIENTO: 'JARDÍN INFANTIL MURTITAS DE ENSENADA', COMUNA: 'PUERTO VARAS', TIPO_AREA: 'RURAL',
    DIRECTOR: 'Pamela Valeska Villarroel', CATEGORIA: 'J. INFANTIL - S. CUNA', Cobertura: 'E. Parvularia', ADP: 'No', PAME: 'Marcela Wigolorchew',
    MATRICULA_2026: 27, MATRICULA_2025: 26, PROMEDIO_ASIST_2025: '75%', IVE_BASICA: 0, IVE_MEDIA: 0, NUM_DOCENTES: 3, NUM_ASISTENTES: 4
  },
  {
    RBD: '35155', NOM_ESTABLECIMIENTO: 'JARDÍN INFANTIL MI NUEVA AVENTURA', COMUNA: 'PUERTO VARAS', TIPO_AREA: 'RURAL',
    DIRECTOR: 'Karen Valeska Vidal', CATEGORIA: 'J. INFANTIL - S. CUNA', Cobertura: 'E. Parvularia', ADP: 'No', PAME: 'Marcela Wigolorchew',
    MATRICULA_2026: 39, MATRICULA_2025: 19, PROMEDIO_ASIST_2025: '80%', IVE_BASICA: 0, IVE_MEDIA: 0, NUM_DOCENTES: 4, NUM_ASISTENTES: 5
  },
  {
    RBD: '7722', NOM_ESTABLECIMIENTO: 'COLEGIO ROSITA NOVARO DE NOVARO', COMUNA: 'PUERTO VARAS', TIPO_AREA: 'URBANO',
    DIRECTOR: 'Víctor Muñoz Zúñiga', CATEGORIA: 'Colegio', Cobertura: 'Ed. Parvularia a IV Medio', ADP: 'Sí', PAME: 'Claudia Hofmann',
    MATRICULA_2026: 800, MATRICULA_2025: 780, PROMEDIO_ASIST_2025: '90%', IVE_BASICA: 70, IVE_MEDIA: 75, NUM_DOCENTES: 60, NUM_ASISTENTES: 30
  },
  {
    RBD: '8001', NOM_ESTABLECIMIENTO: 'ESCUELA RURAL LOS LINARES', COMUNA: 'LOS MUERMOS', TIPO_AREA: 'RURAL',
    DIRECTOR: 'Ana Maria Silva', CATEGORIA: 'Escuela', Cobertura: '1° a 8° Básico', ADP: 'No', PAME: 'Juan Perez',
    MATRICULA_2026: 120, MATRICULA_2025: 125, PROMEDIO_ASIST_2025: '85%', IVE_BASICA: 90, IVE_MEDIA: 0, NUM_DOCENTES: 10, NUM_ASISTENTES: 5
  },
  {
    RBD: '8002', NOM_ESTABLECIMIENTO: 'LICEO POLITECNICO LLANQUIHUE', COMUNA: 'LLANQUIHUE', TIPO_AREA: 'URBANO',
    DIRECTOR: 'Carlos Soto', CATEGORIA: 'Liceo', Cobertura: 'I a IV Medio', ADP: 'Sí', PAME: 'Maria Gonzalez',
    MATRICULA_2026: 600, MATRICULA_2025: 590, PROMEDIO_ASIST_2025: '82%', IVE_BASICA: 0, IVE_MEDIA: 88, NUM_DOCENTES: 45, NUM_ASISTENTES: 25
  },
  {
    RBD: '8003', NOM_ESTABLECIMIENTO: 'ESCUELA BASICA FRESIA', COMUNA: 'FRESIA', TIPO_AREA: 'URBANO',
    DIRECTOR: 'Luis Martinez', CATEGORIA: 'Escuela', Cobertura: '1° a 8° Básico', ADP: 'No', PAME: 'Pedro Jimenez',
    MATRICULA_2026: 350, MATRICULA_2025: 340, PROMEDIO_ASIST_2025: '89%', IVE_BASICA: 75, IVE_MEDIA: 0, NUM_DOCENTES: 25, NUM_ASISTENTES: 12
  }
];

// --- COMPONENTES VISUALES REUTILIZABLES ---
const Card = ({ title, value, icon: Icon, subtitle }) => (
  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex items-start gap-4">
    <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
      <Icon size={24} />
    </div>
    <div>
      <p className="text-sm font-medium text-slate-500 mb-1">{title}</p>
      <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
      {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
    </div>
  </div>
);

// Gráfico de Barras Simple en CSS (Sin dependencias externas)
const SimpleBarChart = ({ data, title }) => {
  const maxVal = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
      <h3 className="text-base font-semibold text-slate-800 mb-6">{title}</h3>
      <div className="flex items-end gap-4 h-48 mt-4">
        {data.map((item, idx) => (
          <div key={idx} className="flex-1 flex flex-col items-center gap-2">
            <div className="relative w-full flex-1 bg-slate-50 rounded-t-md flex items-end justify-center group">
              {/* Tooltip on hover */}
              <div className="absolute -top-8 bg-slate-800 text-white text-xs py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                {item.value}
              </div>
              <div 
                className="w-4/5 bg-blue-500 rounded-t-md transition-all duration-500"
                style={{ height: `${(item.value / maxVal) * 100}%` }}
              ></div>
            </div>
            <span className="text-xs font-medium text-slate-600 text-center truncate w-full" title={item.label}>
              {item.label}
            </span>
            <span className="text-sm font-bold text-slate-800">{item.value.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// --- NUEVO COMPONENTE: GRÁFICO DE TORTA / DONA ---
const CustomPieChart = ({ data, title }) => {
  const total = data.reduce((sum, item) => sum + (Number(item.value) || 0), 0);
  let cumulativePercent = 0;

  // Función para asignar los mismos colores descriptivos de la tabla
  const getColor = (label, index) => {
    const upperLabel = label?.toString().toUpperCase();
    if (upperLabel === 'URBANO') return '#4f46e5'; // Indigo-600 (Igual que tabla)
    if (upperLabel === 'RURAL') return '#10b981';  // Emerald-500 (Igual que tabla)
    
    // Paleta de colores para las comunas
    const palette = ['#3b82f6', '#f97316', '#8b5cf6', '#ec4899', '#0ea5e9', '#14b8a6', '#f43f5e'];
    return palette[index % palette.length];
  };

  const getCoordinatesForPercent = (percent) => {
    const x = Math.cos(2 * Math.PI * percent);
    const y = Math.sin(2 * Math.PI * percent);
    return [x, y];
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex flex-col items-center h-full">
      <h3 className="text-base font-semibold text-slate-800 mb-6 w-full text-left">{title}</h3>
      {total === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">Sin datos para mostrar</div>
      ) : (
        <div className="flex flex-col sm:flex-row items-center gap-8 w-full justify-center flex-1">
          <div className="relative w-48 h-48">
            <svg viewBox="-1 -1 2 2" className="w-full h-full transform -rotate-90 drop-shadow-md">
              {data.map((item, idx) => {
                const value = Number(item.value) || 0;
                if (value === 0) return null;
                
                const percent = value / total;
                const color = getColor(item.label, idx);
                
                // Caso especial: Si un valor es el 100%, dibujamos un círculo completo
                if (percent === 1) {
                  return <circle key={idx} cx="0" cy="0" r="1" fill={color} />;
                }

                const [startX, startY] = getCoordinatesForPercent(cumulativePercent);
                cumulativePercent += percent;
                const [endX, endY] = getCoordinatesForPercent(cumulativePercent);
                const largeArcFlag = percent > 0.5 ? 1 : 0;
                
                const pathData = [
                  `M ${startX} ${startY}`,
                  `A 1 1 0 ${largeArcFlag} 1 ${endX} ${endY}`,
                  `L 0 0`
                ].join(' ');

                return (
                  <path 
                    key={idx} 
                    d={pathData} 
                    fill={color} 
                    className="hover:opacity-80 transition-opacity cursor-pointer duration-300"
                  >
                    <title>{item.label}: {value.toLocaleString()} ({Math.round(percent * 100)}%)</title>
                  </path>
                );
              })}
              {/* Hueco central para efecto Dona */}
              <circle cx="0" cy="0" r="0.6" fill="white" />
            </svg>
            
            {/* Total al centro de la dona */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-xs text-slate-400 font-medium">Total</span>
              <span className="text-lg font-bold text-slate-800">{total.toLocaleString()}</span>
            </div>
          </div>
          
          {/* Leyenda lateral interactiva */}
          <div className="flex flex-col gap-3 flex-1 w-full">
            {data.map((item, idx) => {
              const value = Number(item.value) || 0;
              if (value === 0) return null;
              const percent = (value / total) * 100;
              
              return (
                <div key={idx} className="flex items-center gap-3 text-sm group">
                  <span className="w-3.5 h-3.5 rounded-full shadow-sm flex-shrink-0" style={{ backgroundColor: getColor(item.label, idx) }}></span>
                  <span className="text-slate-600 font-medium truncate group-hover:text-slate-900 transition-colors" title={item.label}>
                    {item.label}
                  </span>
                  <div className="ml-auto text-right flex-shrink-0">
                    <span className="text-slate-800 font-bold block leading-none">{value.toLocaleString()}</span>
                    <span className="text-xs text-slate-400 font-medium">{percent.toFixed(1)}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default function App() {
  // Estado principal
  const [data, setData] = useState(initialData);
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard', 'directory'
  const [selectedEstablecimiento, setSelectedEstablecimiento] = useState(null);
  
  // Estado de Filtros
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    COMUNA: '',
    TIPO_AREA: '',
    CATEGORIA: '',
    Cobertura: '',
    ADP: ''
  });

  // Extraer opciones únicas para los filtros basados en los datos actuales
  const filterOptions = useMemo(() => {
    return {
      COMUNA: [...new Set(data.map(d => d.COMUNA))].filter(Boolean),
      TIPO_AREA: [...new Set(data.map(d => d.TIPO_AREA))].filter(Boolean),
      CATEGORIA: [...new Set(data.map(d => d.CATEGORIA))].filter(Boolean),
      Cobertura: [...new Set(data.map(d => d.Cobertura))].filter(Boolean),
      ADP: [...new Set(data.map(d => d.ADP))].filter(Boolean),
    };
  }, [data]);

  // Aplicar filtros e interacciones de búsqueda
  const filteredData = useMemo(() => {
    return data.filter(item => {
      // Búsqueda por texto (Nombre o RBD)
      const matchesSearch = searchTerm === '' || 
        item.NOM_ESTABLECIMIENTO?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.RBD?.toString().includes(searchTerm);
      
      // Filtros desplegables
      const matchesComuna = filters.COMUNA === '' || item.COMUNA === filters.COMUNA;
      const matchesArea = filters.TIPO_AREA === '' || item.TIPO_AREA === filters.TIPO_AREA;
      const matchesCategoria = filters.CATEGORIA === '' || item.CATEGORIA === filters.CATEGORIA;
      const matchesCobertura = filters.Cobertura === '' || item.Cobertura === filters.Cobertura;
      const matchesADP = filters.ADP === '' || item.ADP === filters.ADP;

      return matchesSearch && matchesComuna && matchesArea && matchesCategoria && matchesCobertura && matchesADP;
    });
  }, [data, searchTerm, filters]);

  // Cálculos para Gráficos (Cruces de información)
  const dashboardStats = useMemo(() => {
    const totalMatricula26 = filteredData.reduce((sum, item) => sum + (Number(item.MATRICULA_2026) || 0), 0);
    const totalMatricula25 = filteredData.reduce((sum, item) => sum + (Number(item.MATRICULA_2025) || 0), 0);
    const totalDocentes = filteredData.reduce((sum, item) => sum + (Number(item.NUM_DOCENTES) || 0), 0);
    
    // Matrícula por Tipo de Área (Cruce solicitado)
    const areaDataObj = filteredData.reduce((acc, item) => {
      const area = item.TIPO_AREA || 'Sin Dato';
      acc[area] = (acc[area] || 0) + (Number(item.MATRICULA_2026) || 0);
      return acc;
    }, {});
    const matriculaPorArea = Object.keys(areaDataObj).map(key => ({ label: key, value: areaDataObj[key] }));

    // Matrícula por Comuna
    const comunaDataObj = filteredData.reduce((acc, item) => {
      const comuna = item.COMUNA || 'Sin Dato';
      acc[comuna] = (acc[comuna] || 0) + (Number(item.MATRICULA_2026) || 0);
      return acc;
    }, {});
    const matriculaPorComuna = Object.keys(comunaDataObj).map(key => ({ label: key, value: comunaDataObj[key] }));

    return { totalMatricula26, totalMatricula25, totalDocentes, matriculaPorArea, matriculaPorComuna };
  }, [filteredData]);

  // Manejador de cambio de filtros
  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setSelectedEstablecimiento(null); // Reset detail view on filter change
  };

  // Parser simple de CSV para carga de archivos propios
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target.result;
        const rows = text.split('\n');
        const headers = rows[0].split(',').map(h => h.trim());
        
        const parsedData = rows.slice(1).map(row => {
          const values = row.split(','); // Nota: Esto es simple, falla si hay comas dentro de las celdas ("")
          const obj = {};
          headers.forEach((header, index) => {
            obj[header] = values[index]?.trim() || '';
          });
          return obj;
        }).filter(item => item.RBD); // Filtrar filas vacías

        if (parsedData.length > 0) {
          setData(parsedData);
          alert('Datos cargados exitosamente');
        }
      };
      reader.readAsText(file);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-800">
      
      {/* BARRA LATERAL (Filtros) */}
      <aside className="w-72 bg-white border-r border-slate-200 h-screen sticky top-0 overflow-y-auto flex flex-col">
        <div className="p-6 border-b border-slate-100">
          <div className="flex items-center gap-3 text-blue-700 mb-2">
            <School size={28} />
            <h1 className="text-xl font-bold leading-tight">SLEP<br/>Llanquihue</h1>
          </div>
          <p className="text-xs text-slate-500">Sistema de Gestión Visual</p>
        </div>

        <div className="p-6 flex-1 flex flex-col gap-6">
          {/* Navegación */}
          <div className="flex flex-col gap-2">
            <button 
              onClick={() => { setActiveTab('dashboard'); setSelectedEstablecimiento(null); }}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'dashboard' && !selectedEstablecimiento ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-50'}`}
            >
              <PieChart size={18} />
              Panel General (Dashboard)
            </button>
            <button 
              onClick={() => { setActiveTab('directory'); setSelectedEstablecimiento(null); }}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'directory' && !selectedEstablecimiento ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-50'}`}
            >
              <Building2 size={18} />
              Directorio de Recintos
            </button>
          </div>

          <div className="h-px bg-slate-100"></div>

          {/* Buscador y Filtros */}
          <div>
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Filter size={14} />
              Filtros Dinámicos
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">Buscar por Nombre o RBD</label>
                <div className="relative">
                  <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
                  <input 
                    type="text" 
                    placeholder="Ej. Pedro Aguirre..."
                    className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </div>

              {Object.entries(filterOptions).map(([key, options]) => (
                <div key={key}>
                  <label className="text-xs font-medium text-slate-600 mb-1.5 block">
                    {key.replace('_', ' ')}
                  </label>
                  <select 
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                    value={filters[key]}
                    onChange={(e) => handleFilterChange(key, e.target.value)}
                  >
                    <option value="">Todos</option>
                    {options.map(opt => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-xs text-slate-500 mb-2">Mostrando <b>{filteredData.length}</b> registros de {data.length}</p>
              {(searchTerm !== '' || Object.values(filters).some(v => v !== '')) && (
                <button 
                  onClick={() => {
                    setSearchTerm('');
                    setFilters({COMUNA: '', TIPO_AREA: '', CATEGORIA: '', Cobertura: '', ADP: ''});
                  }}
                  className="text-xs text-red-500 font-medium hover:underline"
                >
                  Limpiar todos los filtros
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Carga de Datos Personales */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 mt-auto">
          <label className="flex items-center justify-center gap-2 w-full py-2 px-3 border border-dashed border-slate-300 rounded-lg text-xs font-medium text-slate-600 hover:bg-white hover:border-blue-400 cursor-pointer transition-colors">
            <Upload size={14} />
            Cargar mi propio CSV
            <input type="file" accept=".csv" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
      </aside>

      {/* ÁREA PRINCIPAL */}
      <main className="flex-1 p-8 overflow-y-auto">
        
        {/* --- VISTA: FICHA DE ESTABLECIMIENTO (Detalle aislado) --- */}
        {selectedEstablecimiento ? (
          <div className="max-w-5xl mx-auto animation-fade-in">
            <button 
              onClick={() => setSelectedEstablecimiento(null)}
              className="flex items-center gap-2 text-sm text-blue-600 hover:underline mb-6 font-medium"
            >
              <ArrowLeft size={16} /> Volver a la vista anterior
            </button>
            
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              {/* Cabecera Ficha */}
              <div className="bg-slate-900 p-8 text-white relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-10">
                  <School size={120} />
                </div>
                <div className="relative z-10">
                  <div className="flex gap-2 mb-3">
                    <span className="px-3 py-1 bg-blue-600 text-xs font-bold rounded-full uppercase tracking-wide">RBD: {selectedEstablecimiento.RBD}</span>
                    <span className="px-3 py-1 bg-white/20 text-xs font-medium rounded-full">{selectedEstablecimiento.COMUNA}</span>
                    <span className="px-3 py-1 bg-white/20 text-xs font-medium rounded-full">{selectedEstablecimiento.TIPO_AREA}</span>
                  </div>
                  <h2 className="text-3xl font-bold mb-2">{selectedEstablecimiento.NOM_ESTABLECIMIENTO}</h2>
                  <p className="text-slate-300 flex items-center gap-2">
                    <MapPin size={16} /> {selectedEstablecimiento.DIRECCION || 'Dirección no especificada'}
                  </p>
                </div>
              </div>

              <div className="p-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Columna Izquierda: Info de Gestión */}
                <div className="space-y-6">
                  <div>
                    <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">Equipo Directivo / Gestión</h4>
                    <ul className="space-y-3">
                      <li className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                        <span className="block text-xs text-slate-500 mb-0.5">Director / Encargado</span>
                        <span className="font-semibold text-slate-800">{selectedEstablecimiento.DIRECTOR || '-'}</span>
                      </li>
                      <li className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                        <span className="block text-xs text-slate-500 mb-0.5">PAME</span>
                        <span className="font-semibold text-slate-800">{selectedEstablecimiento.PAME || '-'}</span>
                      </li>
                      <li className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                        <span className="block text-xs text-slate-500 mb-0.5">Categoría</span>
                        <span className="font-semibold text-slate-800">{selectedEstablecimiento.CATEGORIA || '-'}</span>
                      </li>
                      <li className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                        <span className="block text-xs text-slate-500 mb-0.5">Cobertura</span>
                        <span className="font-semibold text-slate-800">{selectedEstablecimiento.Cobertura || '-'}</span>
                      </li>
                    </ul>
                  </div>
                </div>

                {/* Columnas Central/Derecha: Datos Duros (Métricas) */}
                <div className="lg:col-span-2 space-y-8">
                  
                  {/* Sección Matrícula */}
                  <section>
                    <div className="flex items-center gap-2 border-b border-slate-100 pb-2 mb-4">
                      <GraduationCap size={20} className="text-blue-600" />
                      <h3 className="text-lg font-bold text-slate-800">Métricas de Alumnado</h3>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      <div className="p-4 bg-white border border-slate-200 rounded-xl text-center">
                        <p className="text-xs text-slate-500 mb-1">Matrícula 2026</p>
                        <p className="text-2xl font-bold text-blue-600">{selectedEstablecimiento.MATRICULA_2026 || 0}</p>
                      </div>
                      <div className="p-4 bg-white border border-slate-200 rounded-xl text-center">
                        <p className="text-xs text-slate-500 mb-1">Matrícula 2025</p>
                        <p className="text-2xl font-bold text-slate-700">{selectedEstablecimiento.MATRICULA_2025 || 0}</p>
                      </div>
                      <div className="p-4 bg-white border border-slate-200 rounded-xl text-center">
                        <p className="text-xs text-slate-500 mb-1">Asistencia 2025</p>
                        <p className="text-2xl font-bold text-slate-700">{selectedEstablecimiento.PROMEDIO_ASIST_2025 || '-'}</p>
                      </div>
                      <div className="p-4 bg-white border border-slate-200 rounded-xl text-center">
                        <p className="text-xs text-slate-500 mb-1">Variación</p>
                        <p className={`text-2xl font-bold ${Number(selectedEstablecimiento.MATRICULA_2026) >= Number(selectedEstablecimiento.MATRICULA_2025) ? 'text-green-500' : 'text-red-500'}`}>
                           {Number(selectedEstablecimiento.MATRICULA_2026) - Number(selectedEstablecimiento.MATRICULA_2025)}
                        </p>
                      </div>
                    </div>
                  </section>

                  {/* Sección Vulnerabilidad e Indicadores */}
                  <section>
                    <div className="flex items-center gap-2 border-b border-slate-100 pb-2 mb-4">
                      <BarChart3 size={20} className="text-blue-600" />
                      <h3 className="text-lg font-bold text-slate-800">Vulnerabilidad (IVE) y Personal</h3>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-orange-50 p-4 rounded-xl border border-orange-100 flex justify-between items-center">
                        <div>
                          <p className="text-sm font-semibold text-orange-900">IVE Básica</p>
                          <p className="text-xs text-orange-700">Índice Vulnerabilidad</p>
                        </div>
                        <p className="text-2xl font-bold text-orange-600">{selectedEstablecimiento.IVE_BASICA || 0}%</p>
                      </div>
                      <div className="bg-orange-50 p-4 rounded-xl border border-orange-100 flex justify-between items-center">
                        <div>
                          <p className="text-sm font-semibold text-orange-900">IVE Media</p>
                          <p className="text-xs text-orange-700">Índice Vulnerabilidad</p>
                        </div>
                        <p className="text-2xl font-bold text-orange-600">{selectedEstablecimiento.IVE_MEDIA || 0}%</p>
                      </div>
                      <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 flex justify-between items-center">
                        <div>
                          <p className="text-sm font-semibold text-blue-900">N° Docentes</p>
                          <p className="text-xs text-blue-700">Planta Docente</p>
                        </div>
                        <p className="text-2xl font-bold text-blue-600">{selectedEstablecimiento.NUM_DOCENTES || 0}</p>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex justify-between items-center">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">N° Asistentes</p>
                          <p className="text-xs text-slate-500">Asistentes Educación</p>
                        </div>
                        <p className="text-2xl font-bold text-slate-600">{selectedEstablecimiento.NUM_ASISTENTES || 0}</p>
                      </div>
                    </div>
                  </section>

                </div>
              </div>
            </div>
          </div>

        ) : activeTab === 'dashboard' ? (
          
          /* --- VISTA: DASHBOARD (Gráficos y KPIs) --- */
          <div className="max-w-6xl mx-auto animation-fade-in">
            <header className="mb-8">
              <h2 className="text-2xl font-bold text-slate-800">Resumen del Territorio</h2>
              <p className="text-slate-500">Análisis visual cruzado de la información institucional.</p>
            </header>

            {/* KPIs */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <Card 
                title="Total Establecimientos" 
                value={filteredData.length} 
                icon={Building2} 
                subtitle="Según filtros aplicados"
              />
              <Card 
                title="Matrícula Total (2026)" 
                value={dashboardStats.totalMatricula26.toLocaleString()} 
                icon={Users} 
                subtitle={`vs ${dashboardStats.totalMatricula25.toLocaleString()} en 2025`}
              />
              <Card 
                title="Dotación Docente" 
                value={dashboardStats.totalDocentes.toLocaleString()} 
                icon={Users} 
                subtitle="Total en área seleccionada"
              />
              <Card 
                title="Comunas Involucradas" 
                value={filterOptions.COMUNA.length} 
                icon={MapPin} 
                subtitle="En el territorio SLEP"
              />
            </div>

            {/* Gráficos de Cruce de Información */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Cruce específico solicitado: Urbano vs Rural */}
          <CustomPieChart 
            title="Distribución: Matrícula Urbano vs Rural" 
            data={dashboardStats.matriculaPorArea} 
          />
          
          {/* Distribución por Comuna */}
          <CustomPieChart 
            title="Distribución de Matrícula por Comuna" 
            data={dashboardStats.matriculaPorComuna} 
          />
        </div>
      </div>

    ) : (

          /* --- VISTA: DIRECTORIO (Tabla Relacional) --- */
          <div className="max-w-6xl mx-auto animation-fade-in">
            <header className="mb-6 flex justify-between items-end">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Directorio de Establecimientos</h2>
                <p className="text-slate-500">Selecciona un establecimiento para ver su ficha detallada.</p>
              </div>
            </header>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-6 py-4 font-semibold text-slate-600">RBD</th>
                      <th className="px-6 py-4 font-semibold text-slate-600">Establecimiento</th>
                      <th className="px-6 py-4 font-semibold text-slate-600">Comuna</th>
                      <th className="px-6 py-4 font-semibold text-slate-600">Área</th>
                      <th className="px-6 py-4 font-semibold text-slate-600 text-right">Matrícula '26</th>
                      <th className="px-6 py-4 font-semibold text-slate-600 text-center">Acción</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredData.length === 0 ? (
                      <tr>
                        <td colSpan="6" className="px-6 py-12 text-center text-slate-500">
                          No hay establecimientos que coincidan con los filtros actuales.
                        </td>
                      </tr>
                    ) : (
                      filteredData.map((item, idx) => (
                        <tr 
                          key={idx} 
                          className="hover:bg-blue-50/50 transition-colors group cursor-pointer"
                          onClick={() => setSelectedEstablecimiento(item)}
                        >
                          <td className="px-6 py-4 text-slate-500 font-mono">{item.RBD}</td>
                          <td className="px-6 py-4 font-medium text-slate-800">{item.NOM_ESTABLECIMIENTO}</td>
                          <td className="px-6 py-4 text-slate-600">{item.COMUNA}</td>
                          <td className="px-6 py-4">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${item.TIPO_AREA === 'URBANO' ? 'bg-indigo-100 text-indigo-700' : 'bg-emerald-100 text-emerald-700'}`}>
                              {item.TIPO_AREA}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right font-semibold text-slate-700">
                            {item.MATRICULA_2026 || 0}
                          </td>
                          <td className="px-6 py-4 text-center">
                            <button className="text-blue-600 font-medium text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center w-full gap-1">
                              Ver Ficha <ChevronRight size={14} />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Estilos Base incrustados para animaciones y scroll */}
      <style dangerouslySetInnerHTML={{__html: `
        .animation-fade-in { animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        /* Custom scrollbar for sidebar */
        aside::-webkit-scrollbar { width: 6px; }
        aside::-webkit-scrollbar-track { background: transparent; }
        aside::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 20px; }
      `}} />
    </div>
  );
}