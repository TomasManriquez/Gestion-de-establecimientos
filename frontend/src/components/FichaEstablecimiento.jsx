import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, Edit3, School, Users, Wifi, Printer, 
  UserCheck, History, Calendar, CheckCircle2, XCircle, Info, PhoneCall,
  Mail, Phone, X, TrendingUp, Copy, Check
} from 'lucide-react';
import { toast } from 'sonner';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip
} from 'recharts';
import EstablishmentMap from './EstablishmentMap';
import ConectividadFicha from './ConectividadFicha';
import { can } from '@/lib/access';

/** Fila de «Detalles generales»: etiqueta pequeña y valor, sin tarjeta propia. */
function DetailRow({ label, value }) {
  return (
    <div className="px-5 py-2.5">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="font-semibold text-slate-800">{value}</dd>
    </div>
  );
}

const roleLabel = (role) => {
  const text = (role || '').replace(/_/g, ' ').toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

/** Copia al portapapeles. Sin la API moderna (contexto no seguro) cae en un textarea temporal. */
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    document.body.removeChild(area);
    return ok;
  }
}

/** Dato de contacto como texto seleccionable (sin hipervínculo) y un botón que lo copia. */
function ContactLine({ icon: Icon, kind, value, person }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (await copyText(value)) {
      setCopied(true);
      toast.success(`${kind} copiado`);
      setTimeout(() => setCopied(false), 1500);
    } else {
      toast.error(`No se pudo copiar el ${kind.toLowerCase()}. Selecciónalo y cópialo a mano.`);
    }
  };
  return (
    <div className="flex items-center gap-1.5 text-xs text-slate-600">
      <Icon size={12} className="shrink-0 text-slate-400" aria-hidden="true" />
      <span className="min-w-0 flex-1 select-text break-all">{value}</span>
      <button type="button" onClick={copy} title={`Copiar ${kind.toLowerCase()}`}
        aria-label={`Copiar ${kind.toLowerCase()} de ${person}`}
        className="shrink-0 p-1 rounded-md text-slate-400 hover:text-sky-600 hover:bg-sky-50 transition-colors">
        {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
      </button>
    </div>
  );
}

/**
 * Contrapartes en una sola tarjeta: una fila por persona con cargo y nombre; correo y teléfono
 * visibles bajo el nombre, seleccionables, con un botón para copiarlos.
 */
function CounterpartList({ title, dotClass, items, empty }) {
  return (
    <section className="bg-white rounded-2xl border border-slate-100 shadow-sm">
      <h3 className="flex items-center gap-2 px-5 pt-4 pb-2 text-sm font-bold text-slate-800 font-outfit">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} aria-hidden="true"></span>
        {title}
        <span className="ml-auto text-xs font-semibold text-slate-400">{items.length}</span>
      </h3>
      {items.length === 0 ? (
        <p className="px-5 pb-5 pt-2 text-xs text-slate-400">{empty}</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {items.map((cp, idx) => (
            <li key={cp._id || idx} className="px-5 py-2 hover:bg-slate-50/70 transition-colors">
              <span className="block text-[11px] font-semibold text-slate-400">{roleLabel(cp.role)}</span>
              <span className="block font-semibold text-slate-800 truncate" title={cp.name}>{cp.name}</span>
              {cp.email && <ContactLine icon={Mail} kind="Correo" value={cp.email} person={cp.name} />}
              {cp.phone && <ContactLine icon={Phone} kind="Teléfono" value={cp.phone} person={cp.name} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * FichaEstablecimiento — FE-02
 * Lee el RBD desde la URL via useParams() en vez de recibirlo como prop.
 * Deep-link directo a /establecimientos/:rbd funciona en F5 y bookmarks.
 * "Volver" usa navigate con la ruta de origen guardada en location.state.from,
 * o navigate(-1) como fallback si viene de navegación de historial.
 * "Editar" navega a /establecimientos/:rbd/editar con datos en location.state
 * para evitar re-fetch innecesario si EditFicha ya los tiene disponibles.
 */
export default function FichaEstablecimiento({ currentUser }) {
  const { rbd } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [establishment, setEstablishment] = useState(null);
  const [counterparts, setCounterparts] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('general');
  const [showDirectorContact, setShowDirectorContact] = useState(false);
  const canEdit = can(currentUser, 'datos', 'write');

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

  // Click outside handler for director contact popover
  useEffect(() => {
    if (!showDirectorContact) return;
    const handleOutsideClick = (e) => {
      if (!e.target.closest('#director-contact-popup') && !e.target.closest('#director-name-btn')) {
        setShowDirectorContact(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [showDirectorContact]);

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
  // El director ya figura arriba en «Director / Encargado» (con su «Contacto»): no se repite en el equipo.
  // Si la ficha no tiene director registrado, se conserva para no perder a la persona.
  const hasDirector = Boolean(establishment?.general_info?.director);
  const schoolCounterparts = counterparts.filter(
    c => c.origin === 'ESTABLECIMIENTO' && !(hasDirector && c.role === 'DIRECTOR')
  );
  const slepCounterparts = counterparts.filter(c => c.origin === 'SLEP');

  // Format historical metrics data for Recharts
  const enrollmentHistoryData = metrics.map(m => ({
    year: m.year.toString(),
    matricula: m.enrollment
  })).sort((a, b) => a.year.localeCompare(b.year));

  // El año más reciente cargado, no uno fijo: al registrar 2027 la ficha lo muestra sin tocar código.
  const latestMetric = metrics.reduce((best, m) => (!best.year || m.year > best.year ? m : best), {});

  return (
    <div className="space-y-6 animate-fade-in font-sans">
      
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => {
              // Volver a la URL del directorio con los filtros que tenía al navegar
              const backTo = location.state?.from
                ? `/establecimientos${location.state.from}`
                : '/establecimientos';
              navigate(backTo);
            }}
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
              {establishment.status === 'closed' && (
                <span className="px-2.5 py-0.5 bg-rose-100 text-rose-800 text-[10px] font-bold rounded-full uppercase">
                  Cerrado{establishment.closed_year ? ` en ${establishment.closed_year}` : ''}
                </span>
              )}
            </div>
            <h1 className="text-2xl font-extrabold font-outfit text-slate-800 tracking-tight leading-none">
              {establishment.name}
            </h1>
          </div>
        </div>

        {canEdit && (
          <button 
            onClick={() =>
              navigate(`/establecimientos/${rbd}/editar`, {
                state: {
                  initialEst: establishment,
                  initialCps: counterparts,
                  initialMetrics: metrics,
                }
              })
            }
            className="flex items-center justify-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-xl text-sm shadow-md shadow-sky-600/10 hover:shadow-sky-500/20 transition-all font-outfit"
          >
            <Edit3 size={16} />
            Editar Ficha
          </button>
        )}
      </div>

      {/* Tabs list */}
      <div className="flex border-b border-slate-200 overflow-x-auto gap-2 pb-px">
        {[
          { id: 'general', label: 'Información General', icon: School },
          { id: 'statistics', label: 'Estadísticas e Historial', icon: History },
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
        
        {/* Tab 1: Información General y Contrapartes */}
        {activeTab === 'general' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

            {/* Full-width: Ubicación */}
            <div className="lg:col-span-3">
              <EstablishmentMap
                lat={establishment.location?.lat}
                lng={establishment.location?.lng}
                name={establishment.name}
                address={establishment.address}
              />
            </div>

            {/* Left side: General details */}
            <section className="bg-white rounded-2xl border border-slate-100 shadow-sm">
              <h3 className="px-5 pt-4 pb-2 text-xs font-bold text-slate-400 uppercase tracking-wider">Detalles generales</h3>
              <dl className="divide-y divide-slate-100 text-sm">
                <div className="relative flex items-center justify-between gap-3 px-5 py-2.5">
                  <div className="min-w-0">
                    <dt className="text-xs text-slate-400">Director / Encargado</dt>
                    <dd className="font-semibold text-slate-800 truncate">{establishment.general_info.director || 'Sin especificar'}</dd>
                  </div>
                  {establishment.general_info.director && (
                    <button
                      id="director-name-btn"
                      type="button"
                      onClick={() => setShowDirectorContact(!showDirectorContact)}
                      aria-expanded={showDirectorContact}
                      className="shrink-0 text-xs font-semibold text-sky-700 hover:bg-sky-50 px-2 py-1 rounded-md transition-colors"
                    >
                      Contacto
                    </button>
                  )}

                  {/* Popover contact card */}
                  {showDirectorContact && establishment.general_info.director && (
                    <div
                      id="director-contact-popup"
                      onClick={(e) => e.stopPropagation()}
                      className="absolute left-full top-0 ml-3 z-50 w-72 bg-white rounded-2xl border border-slate-200 shadow-2xl p-4 animate-fade-in space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h4 className="font-bold text-slate-800 text-sm leading-tight">{establishment.general_info.director}</h4>
                          <span className="text-[11px] text-slate-400 font-semibold">Director / Encargado</span>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowDirectorContact(false); }}
                          aria-label="Cerrar contacto"
                          className="p-1 hover:bg-slate-100 text-slate-400 rounded-lg transition-colors"
                        >
                          <X size={15} />
                        </button>
                      </div>
                      <div className="border-t border-slate-100 pt-3 space-y-2 text-xs">
                        <div className="flex items-center gap-2.5 text-slate-600">
                          <Mail size={14} className="text-slate-400 flex-shrink-0" />
                          {establishment.general_info.director_email ? (
                            <a href={`mailto:${establishment.general_info.director_email}`} className="font-semibold text-sky-600 hover:underline break-all">
                              {establishment.general_info.director_email}
                            </a>
                          ) : (
                            <span className="text-slate-400 italic">Sin correo registrado</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2.5 text-slate-600">
                          <Phone size={14} className="text-slate-400 flex-shrink-0" />
                          {establishment.general_info.director_phone ? (
                            <a href={`tel:${establishment.general_info.director_phone}`} className="font-semibold text-slate-700 hover:text-sky-600 hover:underline">
                              {establishment.general_info.director_phone}
                            </a>
                          ) : (
                            <span className="text-slate-400 italic">Sin teléfono registrado</span>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                <DetailRow label="Dirección" value={establishment.address || 'Sin especificar'} />
                <DetailRow label="Categoría" value={establishment.general_info.category || '-'} />
                <DetailRow label="Cobertura curricular" value={establishment.general_info.covertura || '-'} />
                <DetailRow label="Licitación ADP" value={establishment.general_info.adp || 'No'} />
                <DetailRow label="Profesional PAME" value={establishment.general_info.pame || '-'} />
              </dl>
            </section>

            {/* Contrapartes: una fila por persona */}
            <CounterpartList
              title="Equipo del establecimiento"
              dotClass="bg-blue-500"
              items={schoolCounterparts}
              empty="No hay contrapartes registradas para el recinto."
            />
            <CounterpartList
              title="Contrapartes técnicas del SLEP"
              dotClass="bg-sky-500"
              items={slepCounterparts}
              empty="No hay contrapartes técnicas asignadas del servicio local."
            />

          </div>
        )}

        {/* Tab 2: Estadísticas e Historial */}
        {activeTab === 'statistics' && (
          <div className="space-y-6">
            
            {/* Indicators Grid */}
            <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h3 className="text-sm font-bold text-slate-450 uppercase tracking-wider">
                  Indicadores de Matrícula y Rendimiento{latestMetric.year ? ` (${latestMetric.year})` : ''}
                </h3>
                {canEdit && (
                  <button
                    onClick={() => navigate(`/establecimientos/${rbd}/editar`, {
                      state: { initialEst: establishment, initialCps: counterparts, initialMetrics: metrics, initialTab: 'statistics' }
                    })}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 font-bold rounded-lg text-xs transition-all"
                  >
                    <Edit3 size={14} />
                    Editar estadísticas
                  </button>
                )}
              </div>
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 bg-sky-50/50 rounded-xl border border-sky-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">Matrícula actual</span>
                  <span className="text-2xl font-extrabold text-sky-700 font-outfit">{latestMetric.enrollment || 0}</span>
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">Asistencia Prom.</span>
                  <span className="text-2xl font-extrabold text-slate-700 font-outfit">
                    {latestMetric.attendance_avg ? `${(parseFloat(latestMetric.attendance_avg) * 100).toFixed(1)}%` : '-'}
                  </span>
                </div>
                <div className="p-4 bg-orange-50/40 rounded-xl border border-orange-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">IVE Básica</span>
                  <span className="text-2xl font-extrabold text-orange-700 font-outfit">
                    {latestMetric.ive_basica ? `${(latestMetric.ive_basica * 100).toFixed(0)}%` : '-'}
                  </span>
                </div>
                <div className="p-4 bg-orange-50/40 rounded-xl border border-orange-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">IVE Media</span>
                  <span className="text-2xl font-extrabold text-orange-700 font-outfit">
                    {latestMetric.ive_media ? `${(latestMetric.ive_media * 100).toFixed(0)}%` : '-'}
                  </span>
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">Docentes</span>
                  <span className="text-2xl font-extrabold text-slate-700 font-outfit">{latestMetric.num_teachers || 0}</span>
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">Asistentes</span>
                  <span className="text-2xl font-extrabold text-slate-700 font-outfit">{latestMetric.num_assistants || 0}</span>
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">Promedio Notas</span>
                  <span className="text-2xl font-extrabold text-slate-700 font-outfit">{latestMetric.grade_avg?.toFixed(2) || '-'}</span>
                </div>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center hover:shadow-sm transition-all duration-200">
                  <span className="block text-xs font-semibold text-slate-500 mb-1">Retención %</span>
                  <span className="text-2xl font-extrabold text-slate-700 font-outfit">{latestMetric.tasa_retencion || '-'}</span>
                </div>
              </div>
            </div>

            {/* Enrollment chart at full width */}
            <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[380px]">
              <div className="flex items-center gap-2 mb-4">
                <History size={18} className="text-sky-600" />
                <h3 className="text-base font-bold text-slate-800 font-outfit">Evolución Histórica de Matrícula</h3>
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

            {/* Future segments for future expansion */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Segment 1: Future Stats / Performance Analysis */}
              <div className="bg-white p-6 rounded-2xl border border-slate-150 border-dashed shadow-sm flex flex-col items-center justify-center text-center p-8 min-h-[160px] group hover:border-sky-300 transition-colors duration-200">
                <div className="w-12 h-12 rounded-xl bg-slate-50 group-hover:bg-sky-50 flex items-center justify-center mb-3 transition-colors duration-200">
                  <TrendingUp className="text-slate-400 group-hover:text-sky-600 transition-colors duration-200" size={20} />
                </div>
                <h4 className="text-sm font-bold text-slate-700 font-outfit">Módulo de Análisis de Rendimiento</h4>
                <p className="text-xs text-slate-400 mt-1.5 max-w-xs">Futuro segmento para comparar indicadores de asistencia mensual, metas SLEP e historial de repitencia.</p>
              </div>
    </div>
              {/* Segment 2: Future Stats / SIMCE & Evaluation */}
              <div className="bg-white p-6 rounded-2xl border border-slate-150 border-dashed shadow-sm flex flex-col items-center justify-center text-center p-8 min-h-[160px] group hover:border-sky-300 transition-colors duration-200">
                <div className="w-12 h-12 rounded-xl bg-slate-50 group-hover:bg-sky-50 flex items-center justify-center mb-3 transition-colors duration-200">
                  <Users className="text-slate-400 group-hover:text-sky-600 transition-colors duration-200" size={20} />
                </div>
                <h4 className="text-sm font-bold text-slate-700 font-outfit">Módulo de Evaluaciones Estandarizadas</h4>
                <p className="text-xs text-slate-400 mt-1.5 max-w-xs">Próximamente se integrará el historial de puntajes SIMCE, indicadores de desarrollo personal y social, y caracterización socioeconómica.</p>
              </div>

          </div>
        )}

        {/* Tab 3: Conectividad */}
        {activeTab === 'connectivity' && (
          <div className="space-y-6">
            
            {/* 2030, BAM y otro tipo: solo los bloques con datos */}
            <ConectividadFicha connectivity={establishment.connectivity} />

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
