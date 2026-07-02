import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  ArrowLeft, Edit3, School, MapPin, Users, Wifi, Printer, 
  UserCheck, History, Calendar, CheckCircle2, XCircle, Info, PhoneCall
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip
} from 'recharts';

export default function FichaEstablecimiento({ rbd, onBack, onEdit }) {
  const [establishment, setEstablishment] = useState(null);
  const [counterparts, setCounterparts] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('general'); // general, counterparts, connectivity, printers

  const fetchFichaData = async () => {
    setLoading(true);
    try {
      const [estRes, cpRes, metRes] = await Promise.all([
        axios.get(`/api/establishments/${rbd}`),
        axios.get(`/api/counterparts/establishment/${rbd}`),
        axios.get(`/api/metrics/establishment/${rbd}`)
      ]);
      setEstablishment(estRes.data);
      setCounterparts(cpRes.data);
      setMetrics(metRes.data);
    } catch (err) {
      console.error('Error fetching school detail data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFichaData();
  }, [rbd]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="w-12 h-12 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin"></div>
        <p className="text-sm font-medium text-slate-500">Cargando expediente del establecimiento...</p>
      </div>
    );
  }

  if (!establishment) {
    return (
      <div className="p-8 text-center text-slate-500 font-sans">
        No se pudo cargar la información del establecimiento.
      </div>
    );
  }

  // Group counterparts by origin
  const schoolCounterparts = counterparts.filter(c => c.origin === 'ESTABLECIMIENTO');
  const slepCounterparts = counterparts.filter(c => c.origin === 'SLEP');

  // Format historical metrics data for Recharts
  const enrollmentHistoryData = metrics.map(m => ({
    year: m.year.toString(),
    matricula: m.enrollment
  })).sort((a, b) => a.year.localeCompare(b.year));

  const latestMetric = metrics.find(m => m.year === 2026) || {};

  return (
    <div className="space-y-6 animate-fade-in font-sans">
      
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div className="flex items-center gap-4">
          <button 
            onClick={onBack}
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-xl transition-all"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="px-2.5 py-0.5 bg-sky-900 text-white text-[10px] font-bold rounded-full uppercase tracking-wider">
                RBD: {establishment.rbd_full}
              </span>
              <span className="px-2.5 py-0.5 bg-slate-100 text-slate-600 text-[10px] font-semibold rounded-full uppercase">
                {establishment.comuna}
              </span>
              <span className="px-2.5 py-0.5 bg-slate-100 text-slate-600 text-[10px] font-semibold rounded-full uppercase">
                {establishment.area_type}
              </span>
            </div>
            <h1 className="text-2xl font-extrabold font-outfit text-slate-800 tracking-tight leading-none">
              {establishment.name}
            </h1>
          </div>
        </div>

        <button 
          onClick={() => onEdit(establishment, counterparts, metrics)}
          className="flex items-center justify-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-xl text-sm shadow-md shadow-sky-600/10 hover:shadow-sky-500/20 transition-all font-outfit"
        >
          <Edit3 size={16} />
          Editar Ficha
        </button>
      </div>

      {/* Tabs list */}
      <div className="flex border-b border-slate-200 overflow-x-auto gap-2 pb-px">
        {[
          { id: 'general', label: 'General e Historial', icon: School },
          { id: 'counterparts', label: 'Contrapartes Técnicas', icon: UserCheck },
          { id: 'connectivity', label: 'Internet y Conectividad', icon: Wifi },
          { id: 'printers', label: 'Inventario Impresoras', icon: Printer }
        ].map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-3 font-semibold text-sm transition-all border-b-2 whitespace-nowrap font-outfit ${
                activeTab === tab.id 
                  ? 'border-sky-600 text-sky-600' 
                  : 'border-transparent text-slate-400 hover:text-slate-600'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tabs Content */}
      <div className="mt-4">
        
        {/* Tab 1: General e Historial */}
        {activeTab === 'general' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left side: General details */}
            <div className="lg:col-span-1 space-y-6">
              <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Detalles Generales</h3>
                
                <div className="space-y-3 text-sm">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase">Director / Encargado</span>
                    <span className="font-bold text-slate-800">{establishment.general_info.director || 'Sin especificar'}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase">Dirección</span>
                    <span className="font-bold text-slate-800 flex items-center gap-1">
                      <MapPin size={14} className="text-sky-500 flex-shrink-0" />
                      {establishment.address || 'Sin especificar'}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase">Categoría de establecimiento</span>
                    <span className="font-bold text-slate-800">{establishment.general_info.category || '-'}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase">Cobertura Curricular</span>
                    <span className="font-bold text-slate-800">{establishment.general_info.covertura || '-'}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase">Licitación ADP</span>
                    <span className="font-bold text-slate-800">{establishment.general_info.adp || 'No'}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase">Profesional PAME</span>
                    <span className="font-bold text-slate-800">{establishment.general_info.pame || '-'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right side: Charts and Stats */}
            <div className="lg:col-span-2 space-y-6">
              
              {/* Enrollment chart */}
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[320px]">
                <div className="flex items-center gap-2 mb-4">
                  <History size={16} className="text-sky-600" />
                  <h3 className="text-sm font-bold text-slate-800 font-outfit">Evolución Histórica de Matrícula</h3>
                </div>
                <div className="flex-1 min-h-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={enrollmentHistoryData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="year" tick={{ fill: '#64748b', fontSize: 11 }} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
                      <Tooltip formatter={(value) => [value + " Alumnos", "Matrícula"]} />
                      <Line type="monotone" dataKey="matricula" stroke="#0ea5e9" strokeWidth={3} dot={{ r: 6 }} activeDot={{ r: 8 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Advanced metrics details */}
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Indicadores de Matrícula y Rendimiento (2026)</h3>
                
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 bg-sky-50/50 rounded-xl border border-sky-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">Matrícula actual</span>
                    <span className="text-xl font-extrabold text-sky-700 font-outfit">{latestMetric.enrollment || 0}</span>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">Asistencia Prom.</span>
                    <span className="text-xl font-extrabold text-slate-700 font-outfit">
                      {latestMetric.attendance_avg ? `${(parseFloat(latestMetric.attendance_avg) * 100).toFixed(1)}%` : '-'}
                    </span>
                  </div>
                  <div className="p-4 bg-orange-50/40 rounded-xl border border-orange-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">IVE Básica</span>
                    <span className="text-xl font-extrabold text-orange-700 font-outfit">
                      {latestMetric.ive_basica ? `${(latestMetric.ive_basica * 100).toFixed(0)}%` : '-'}
                    </span>
                  </div>
                  <div className="p-4 bg-orange-50/40 rounded-xl border border-orange-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">IVE Media</span>
                    <span className="text-xl font-extrabold text-orange-700 font-outfit">
                      {latestMetric.ive_media ? `${(latestMetric.ive_media * 100).toFixed(0)}%` : '-'}
                    </span>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">Docentes</span>
                    <span className="text-xl font-extrabold text-slate-700 font-outfit">{latestMetric.num_teachers || 0}</span>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">Asistentes</span>
                    <span className="text-xl font-extrabold text-slate-700 font-outfit">{latestMetric.num_assistants || 0}</span>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">Promedio Notas</span>
                    <span className="text-xl font-extrabold text-slate-700 font-outfit">{latestMetric.grade_avg?.toFixed(2) || '-'}</span>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center">
                    <span className="block text-xs font-semibold text-slate-500 mb-1">Retención %</span>
                    <span className="text-xl font-extrabold text-slate-700 font-outfit">{latestMetric.tasa_retencion || '-'}</span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* Tab 2: Contrapartes Técnicas */}
        {activeTab === 'counterparts' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* Contrapartes del Establecimiento */}
            <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-6">
              <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
                <h3 className="text-base font-bold text-slate-800 font-outfit flex items-center gap-2">
                  <span className="w-2.5 h-2.5 bg-blue-500 rounded-full"></span>
                  Equipo del Establecimiento
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {schoolCounterparts.length === 0 ? (
                  <p className="text-sm text-slate-400 col-span-2 text-center py-6">No hay contrapartes registradas para el recinto.</p>
                ) : (
                  schoolCounterparts.map((cp, idx) => (
                    <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[9px] font-bold rounded-md uppercase tracking-wider">
                        {cp.role.replace('_', ' ')}
                      </span>
                      <h4 className="font-bold text-slate-800 mt-1">{cp.name}</h4>
                      {cp.email && <p className="text-xs text-slate-500 break-all">{cp.email}</p>}
                      {cp.phone && <p className="text-xs text-slate-400 font-semibold">{cp.phone}</p>}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Contrapartes del SLEP */}
            <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-6">
              <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
                <h3 className="text-base font-bold text-slate-800 font-outfit flex items-center gap-2">
                  <span className="w-2.5 h-2.5 bg-sky-500 rounded-full"></span>
                  Contrapartes Técnicas del SLEP Llanquihue
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {slepCounterparts.length === 0 ? (
                  <p className="text-sm text-slate-400 col-span-2 text-center py-6">No hay contrapartes técnicas asignadas del servicio local.</p>
                ) : (
                  slepCounterparts.map((cp, idx) => (
                    <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                      <span className="px-2 py-0.5 bg-sky-100 text-sky-800 text-[9px] font-bold rounded-md uppercase tracking-wider">
                        {cp.role.replace('_', ' ')}
                      </span>
                      <h4 className="font-bold text-slate-800 mt-1">{cp.name}</h4>
                      {cp.email && <p className="text-xs text-slate-500 break-all">{cp.email}</p>}
                      {cp.phone && <p className="text-xs text-slate-400 font-semibold">{cp.phone}</p>}
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>
        )}

        {/* Tab 3: Conectividad */}
        {activeTab === 'connectivity' && (
          <div className="space-y-6">
            
            {/* Telsur 2030 Status */}
            <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-5">
              <h3 className="text-base font-bold text-slate-800 font-outfit flex items-center gap-2">
                Conectividad 2030 (TELSUR)
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 flex items-center justify-between">
                  <div>
                    <span className="block text-[10px] font-bold text-slate-400 uppercase">Estado Conexión</span>
                    <span className="font-bold text-slate-800 text-sm">
                      {establishment.connectivity.internet_provider === 'TELSUR' ? 'TELSUR' : 'Otro Proveedor'}
                    </span>
                  </div>
                  {establishment.connectivity.internet_provider === 'TELSUR' ? (
                    <CheckCircle2 className="text-emerald-500" size={24} />
                  ) : (
                    <Info className="text-amber-500" size={24} />
                  )}
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                  <span className="block text-[10px] font-bold text-slate-400 uppercase">SSID / Red Wifi</span>
                  <span className="font-bold text-slate-800 text-sm">{establishment.connectivity.ssid || '-'}</span>
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                  <span className="block text-[10px] font-bold text-slate-400 uppercase">Clave Wifi</span>
                  <span className="font-bold text-slate-800 text-sm">{establishment.connectivity.ssid_password || '-'}</span>
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                  <span className="block text-[10px] font-bold text-slate-400 uppercase">Velocidad de Bajada</span>
                  <span className="font-bold text-slate-800 text-sm">
                    {establishment.connectivity.download_speed_2030 ? `${establishment.connectivity.download_speed_2030} Mbps` : '-'}
                  </span>
                </div>
              </div>

              {/* Starlink Status */}
              <div className="p-4 bg-sky-50/50 rounded-xl border border-sky-100 flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <Wifi size={20} className="text-sky-600" />
                  <div>
                    <span className="font-bold text-slate-800">Antena Starlink Instalada</span>
                    <p className="text-xs text-slate-500">Conectividad satelital de respaldo en el establecimiento</p>
                  </div>
                </div>
                {establishment.connectivity.starlink?.installed ? (
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-xs font-bold rounded-full">INSTALADO</span>
                    <span className="text-xs text-slate-500">{establishment.connectivity.starlink.date || ''}</span>
                  </div>
                ) : (
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-xs font-bold rounded-full">NO</span>
                )}
              </div>
            </div>

            {/* BAM details */}
            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden space-y-4 p-6">
              <h3 className="text-base font-bold text-slate-800 font-outfit">Inventario de Banda Ancha Móvil (BAM)</h3>
              
              <div className="overflow-x-auto border border-slate-100 rounded-xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="px-4 py-3">N° BAM</th>
                      <th className="px-4 py-3">IMEI</th>
                      <th className="px-4 py-3">Equipo</th>
                      <th className="px-4 py-3">OC Asignación</th>
                      <th className="px-4 py-3">Término de Contrato</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-600 font-sans">
                    {establishment.connectivity.bam?.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                          Sin bolsas o dispositivos BAM registrados en el establecimiento.
                        </td>
                      </tr>
                    ) : (
                      establishment.connectivity.bam.map((b, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/50">
                          <td className="px-4 py-3 font-semibold text-slate-800">{b.number}</td>
                          <td className="px-4 py-3 font-mono">{b.imei}</td>
                          <td className="px-4 py-3">{b.device}</td>
                          <td className="px-4 py-3 font-mono">{b.oc}</td>
                          <td className="px-4 py-3">{b.end || 'Vigente'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Internal network points & phone extensions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-slate-800 font-outfit">Redes Internas (Puntos de Red)</h3>
                
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between border-b border-slate-50 pb-2">
                    <span className="text-slate-500">Año de Instalación:</span>
                    <span className="font-semibold text-slate-800">{establishment.connectivity.internal_network?.installed_year || '-'}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-50 pb-2">
                    <span className="text-slate-500">Cantidad Puntos de Red:</span>
                    <span className="font-semibold text-slate-800">{establishment.connectivity.internal_network?.points_count || '-'}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-50 pb-2">
                    <span className="text-slate-500">Estado de la Red:</span>
                    <span className="font-semibold text-slate-800">{establishment.connectivity.internal_network?.status || 'Sin datos'}</span>
                  </div>
                  {establishment.connectivity.internal_network?.obs && (
                    <div className="p-3 bg-amber-50/30 text-amber-800 border border-amber-100 rounded-lg text-xs mt-1">
                      <b>Obs:</b> {establishment.connectivity.internal_network.obs}
                    </div>
                  )}
                </div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-slate-800 font-outfit">Anexos Telefónicos</h3>
                
                {establishment.connectivity.phone_extensions?.length === 0 ? (
                  <p className="text-sm text-slate-400 py-4 text-center">Sin números de anexo registrados.</p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {establishment.connectivity.phone_extensions.map((ext, idx) => (
                      <div key={idx} className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-center gap-2">
                        <PhoneCall size={14} className="text-sky-600" />
                        <span className="font-mono text-sm font-semibold text-slate-700">{ext}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

          </div>
        )}

        {/* Tab 4: Inventario Impresoras */}
        {activeTab === 'printers' && (
          <div className="space-y-6">
            
            {/* Owned printers */}
            <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-4">
              <h3 className="text-base font-bold text-slate-800 font-outfit flex items-center gap-2">
                Impresoras Propias (Adquiridas por Licitación)
              </h3>
              
              <div className="overflow-x-auto border border-slate-100 rounded-xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="px-4 py-3">Modelo</th>
                      <th className="px-4 py-3">Tipo</th>
                      <th className="px-4 py-3">Cantidad</th>
                      <th className="px-4 py-3">Proveedor</th>
                      <th className="px-4 py-3">Código Licitación</th>
                      <th className="px-4 py-3">Vence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-600 font-sans">
                    {establishment.printers.owned?.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                          Sin impresoras propias registradas en este recinto.
                        </td>
                      </tr>
                    ) : (
                      establishment.printers.owned.map((pr, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/50">
                          <td className="px-4 py-3 font-semibold text-slate-800">{pr.model}</td>
                          <td className="px-4 py-3">
                            <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-md ${
                              pr.type === 'COLOR' ? 'bg-pink-50 text-pink-700' : 'bg-slate-100 text-slate-700'
                            }`}>
                              {pr.type}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-bold">{pr.qty}</td>
                          <td className="px-4 py-3">{pr.provider}</td>
                          <td className="px-4 py-3 font-mono">{pr.licitation_code}</td>
                          <td className="px-4 py-3">{pr.expiry_date || 'Sin vencimiento'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Leased printers */}
            <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-4">
              <h3 className="text-base font-bold text-slate-800 font-outfit flex items-center gap-2">
                Servicio de Arriendo de Impresoras (Equipos Arrendados)
              </h3>
              
              <div className="overflow-x-auto border border-slate-100 rounded-xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="px-4 py-3">Marca/Modelo</th>
                      <th className="px-4 py-3">Tipo</th>
                      <th className="px-4 py-3">Número de Serie</th>
                      <th className="px-4 py-3">Ubicación</th>
                      <th className="px-4 py-3">Dirección IP</th>
                      <th className="px-4 py-3">Instalación</th>
                      <th className="px-4 py-3">Contador Inicial</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-600 font-sans">
                    {establishment.printers.leased?.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                          Sin impresoras arrendadas registradas en el establecimiento.
                        </td>
                      </tr>
                    ) : (
                      establishment.printers.leased.map((pr, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/50">
                          <td className="px-4 py-3 font-semibold text-slate-800">{pr.brand} {pr.model}</td>
                          <td className="px-4 py-3">
                            <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-md ${
                              pr.type === 'COLOR' ? 'bg-pink-50 text-pink-700' : 'bg-slate-100 text-slate-700'
                            }`}>
                              {pr.type}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono font-semibold text-slate-800">{pr.serial_number}</td>
                          <td className="px-4 py-3">{pr.location}</td>
                          <td className="px-4 py-3 font-mono text-slate-500">{pr.ip_address || '-'}</td>
                          <td className="px-4 py-3">{pr.installed_date || '-'}</td>
                          <td className="px-4 py-3 font-bold">{pr.initial_counter}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}
