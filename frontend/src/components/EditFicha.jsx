import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { Save, X, Plus, Trash2, ShieldAlert, RefreshCw, AlertTriangle } from 'lucide-react';
import EditFichaEstadisticas from './EditFichaEstadisticas';
import EditConectividad from './EditConectividad';
import { withDefaults } from '@/lib/connectivity';
import { buildMetricPayloads } from '@/lib/metricFields';

/**
 * EditFicha — FE-03
 * Lee el RBD desde useParams(). Acepta datos pre-cargados via location.state
 * (al navegar desde FichaEstablecimiento), o los carga autónomamente si el
 * acceso es directo (F5, bookmark). Elimina dependencia de props initialEst/onSaveSuccess.
 * La pestaña «Estadísticas» edita `metrics` por año: al guardar se envía un PUT por año con
 * solo los campos cambiados (`buildMetricPayloads`).
 */
export default function EditFicha() {
  const { rbd } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  // Si venimos de FichaEstablecimiento, los datos ya están en location.state
  const stateData = location.state ?? {};
  const hasStateData = Boolean(stateData.initialEst);

  const [loadingData, setLoadingData] = useState(!hasStateData);
  const [est, setEst] = useState(hasStateData ? { ...stateData.initialEst, connectivity: withDefaults(stateData.initialEst.connectivity) } : null);
  const [cps, setCps] = useState(hasStateData ? [...(stateData.initialCps ?? [])] : []);
  const [deletedCpIds, setDeletedCpIds] = useState([]);
  const [saving, setSaving] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState(stateData.initialTab ?? 'general');
  const [metrics, setMetrics] = useState(stateData.initialMetrics ?? []);
  const [metricEdits, setMetricEdits] = useState({});
  const [metricErrors, setMetricErrors] = useState({});
  const [extraYears, setExtraYears] = useState([]);
  const [selectedYear, setSelectedYear] = useState(null);

  // Carga autónoma solo cuando no hay datos en location.state
  useEffect(() => {
    if (hasStateData) return;
    const loadData = async () => {
      setLoadingData(true);
      try {
        const [estRes, cpRes, metRes] = await Promise.all([
          axios.get(`/api/establishments/${rbd}`),
          axios.get(`/api/counterparts/establishment/${rbd}`),
          axios.get(`/api/metrics/establishment/${rbd}`),
        ]);
        setEst({ ...estRes.data, connectivity: withDefaults(estRes.data?.connectivity) });
        setCps([...cpRes.data]);
        setMetrics(Array.isArray(metRes.data) ? metRes.data : []);
      } catch (err) {
        console.error('Error loading EditFicha data', err);
      } finally {
        setLoadingData(false);
      }
    };
    loadData();
  }, [rbd, hasStateData]);

  // Si se llegó con datos en location.state pero sin métricas, se piden solo las métricas
  useEffect(() => {
    if (!hasStateData || stateData.initialMetrics) return;
    axios.get(`/api/metrics/establishment/${rbd}`)
      .then((res) => setMetrics(Array.isArray(res.data) ? res.data : []))
      .catch((err) => console.error('Error loading metrics', err));
  }, [rbd, hasStateData]);

  const years = [...new Set([...metrics.map((m) => m.year), ...extraYears])].sort((a, b) => b - a);
  const activeYear = selectedYear ?? years[0] ?? null;

  if (loadingData || !est) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <RefreshCw size={32} className="animate-spin text-sky-500" />
        <p className="text-sm font-medium text-slate-500">Cargando datos del establecimiento...</p>
      </div>
    );
  }


  // Input change handlers
  const handleGeneralChange = (field, value) => {
    setEst(prev => ({
      ...prev,
      general_info: {
        ...prev.general_info,
        [field]: value
      }
    }));
  };

  // Counterparts operations
  const handleCpChange = (index, field, value) => {
    const updated = [...cps];
    updated[index] = { ...updated[index], [field]: value };
    setCps(updated);
  };

  const handleAddCp = () => {
    setCps(prev => [
      ...prev,
      {
        rbd: est.rbd,
        role: "TI",
        origin: "SLEP",
        name: "",
        email: "",
        phone: ""
      }
    ]);
  };

  const handleRemoveCp = (index) => {
    const cp = cps[index];
    if (cp._id || cp.id) {
      setDeletedCpIds(prev => [...prev, cp._id || cp.id]);
    }
    setCps(prev => prev.filter((_, idx) => idx !== index));
  };

  // Owned printers operations
  const handleAddOwnedPrinter = () => {
    setEst(prev => ({
      ...prev,
      printers: {
        ...prev.printers,
        owned: [
          ...prev.printers.owned,
          { model: "", qty: 1, type: "BN", provider: "", licitation_code: "", expiry_date: "" }
        ]
      }
    }));
  };

  const handleRemoveOwnedPrinter = (index) => {
    setEst(prev => ({
      ...prev,
      printers: {
        ...prev.printers,
        owned: prev.printers.owned.filter((_, idx) => idx !== index)
      }
    }));
  };

  const handleOwnedPrinterChange = (index, field, value) => {
    const updated = [...est.printers.owned];
    updated[index] = { ...updated[index], [field]: field === 'qty' ? parseInt(value) || 0 : value };
    setEst(prev => ({
      ...prev,
      printers: {
        ...prev.printers,
        owned: updated
      }
    }));
  };

  // Statistics (metrics) operations
  const handleMetricEdit = (year, key, value) => {
    setMetricEdits(prev => ({ ...prev, [year]: { ...prev[year], [key]: value } }));
    setMetricErrors(prev => {
      if (!prev[year]?.[key]) return prev;
      const rest = { ...prev[year] };
      delete rest[key];
      return { ...prev, [year]: rest };
    });
  };

  const handleAddYear = (year) => {
    setExtraYears(prev => (prev.includes(year) ? prev : [...prev, year]));
    setSelectedYear(year);
  };

  const handleSave = async () => {
    // Validar estadísticas antes de escribir nada: si hay errores no se guarda ninguna pestaña.
    const { payloads: metricPayloads, errors } = buildMetricPayloads(metrics, metricEdits);
    const yearsWithErrors = Object.keys(errors).map(Number);
    if (yearsWithErrors.length) {
      setMetricErrors(errors);
      setActiveSubTab('statistics');
      setSelectedYear(yearsWithErrors[0]);
      return;
    }

    setSaving(true);
    try {
      // 1. Save base establishment (general_info, connectivity, printers)
      const lat = est.location?.lat;
      const lng = est.location?.lng;
      const estPayload = {
        name: est.name,
        comuna: est.comuna,
        area_type: est.area_type,
        address: est.address,
        location: Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : undefined,
        general_info: est.general_info,
        connectivity: est.connectivity,
        printers: est.printers
      };
      await axios.put(`/api/establishments/${est.rbd}`, estPayload);

      // 2. Delete counterparts flagged for removal
      for (const id of deletedCpIds) {
        await axios.delete(`/api/counterparts/${id}`);
      }

      // 3. Create or Update remaining counterparts
      for (const cp of cps) {
        const cpId = cp._id || cp.id;
        if (cpId) {
          // Update
          const updatePayload = {
            name: cp.name,
            email: cp.email,
            phone: cp.phone,
            role: cp.role,
            origin: cp.origin
          };
          await axios.put(`/api/counterparts/${cpId}`, updatePayload);
        } else {
          // Create
          const createPayload = {
            rbd: est.rbd,
            role: cp.role,
            origin: cp.origin,
            name: cp.name,
            email: cp.email,
            phone: cp.phone
          };
          await axios.post('/api/counterparts', createPayload);
        }
      }

      // 4. Estadísticas: un PUT por año, solo con los campos cambiados
      for (const { year, body } of metricPayloads) {
        await axios.put(`/api/metrics/establishment/${est.rbd}/${year}`, body);
      }

      navigate(`/establecimientos/${est.rbd}`);
    } catch (err) {
      console.error('Error saving Ficha data', err);
      alert('Ocurrió un error al guardar los cambios: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-6 animate-fade-in font-sans">
      
      {/* Editor Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <span className="text-xs font-bold text-slate-400 uppercase">Editor de Registro</span>
          <h2 className="text-xl font-extrabold text-slate-800 tracking-tight font-outfit">{est.name}</h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 font-semibold rounded-xl text-sm transition-all"
          >
            <X size={16} />
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-xl text-sm shadow-md shadow-sky-600/10 transition-all disabled:opacity-50"
          >
            <Save size={16} />
            {saving ? 'Guardando...' : 'Guardar Cambios'}
          </button>
        </div>
      </div>

      {/* Sub Tabs for Editing sections */}
      <div className="flex gap-2 border-b border-slate-100 pb-2 overflow-x-auto text-xs font-semibold">
        {[
          { id: 'general', label: 'Datos Generales' },
          { id: 'statistics', label: 'Estadísticas' },
          { id: 'counterparts', label: 'Contrapartes Técnicas' },
          { id: 'connectivity', label: 'Conectividad' },
          { id: 'printers', label: 'Inventario Impresoras' }
        ].map(sub => (
          <button
            key={sub.id}
            onClick={() => setActiveSubTab(sub.id)}
            className={`px-4 py-2 rounded-lg transition-all ${
              activeSubTab === sub.id
                ? 'bg-sky-50 text-sky-700'
                : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'
            }`}
          >
            {sub.label}
          </button>
        ))}
      </div>

      {/* Edit Form Body */}
      <div className="space-y-6 pt-2">
        
        {/* Editor Tab 1: General */}
        {activeSubTab === 'general' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Nombre del Establecimiento</label>
              <input
                type="text"
                value={est.name}
                onChange={(e) => setEst({ ...est, name: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Dirección</label>
              <input
                type="text"
                value={est.address}
                onChange={(e) => setEst({ ...est, address: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Latitud</label>
              <input
                type="number"
                step="any"
                value={est.location?.lat ?? ''}
                onChange={(e) => {
                  const val = e.target.value;
                  setEst({
                    ...est,
                    location: { ...(est.location ?? {}), lat: val === '' ? undefined : parseFloat(val) }
                  });
                }}
                placeholder="-41.320720"
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Longitud</label>
              <input
                type="number"
                step="any"
                value={est.location?.lng ?? ''}
                onChange={(e) => {
                  const val = e.target.value;
                  setEst({
                    ...est,
                    location: { ...(est.location ?? {}), lng: val === '' ? undefined : parseFloat(val) }
                  });
                }}
                placeholder="-72.980972"
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Comuna</label>
              <input
                type="text"
                value={est.comuna}
                onChange={(e) => setEst({ ...est, comuna: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Área Geográfica</label>
              <select
                value={est.area_type}
                onChange={(e) => setEst({ ...est, area_type: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              >
                <option value="URBANO">URBANO</option>
                <option value="RURAL">RURAL</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Categoría</label>
              <input
                type="text"
                value={est.general_info.category}
                onChange={(e) => handleGeneralChange('category', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Cobertura Curricular</label>
              <input
                type="text"
                value={est.general_info.covertura}
                onChange={(e) => handleGeneralChange('covertura', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-500 font-sans"
              />
            </div>
          </div>
        )}

        {/* Editor Tab: Estadísticas por año */}
        {activeSubTab === 'statistics' && (
          <>
            {Object.values(metricErrors).some((e) => Object.keys(e).length > 0) && (
              <div role="alert" className="flex items-center gap-2 p-3 bg-rose-50 border border-rose-200 rounded-xl text-sm font-semibold text-rose-700">
                <AlertTriangle size={16} />
                Hay valores fuera de rango. Corrígelos para poder guardar.
              </div>
            )}
            <EditFichaEstadisticas
              metrics={metrics}
              years={years}
              selectedYear={activeYear}
              onSelectYear={setSelectedYear}
              onAddYear={handleAddYear}
              edits={metricEdits}
              errors={metricErrors}
              onEdit={handleMetricEdit}
            />
          </>
        )}

        {/* Editor Tab 2: Contrapartes Técnicas */}
        {activeSubTab === 'counterparts' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400 uppercase">Asignaciones de Encargados</span>
              <button
                onClick={handleAddCp}
                className="flex items-center gap-1 px-3 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 font-bold rounded-lg text-xs transition-all"
              >
                <Plus size={14} />
                Agregar Encargado
              </button>
            </div>

            <div className="space-y-3">
              {cps.map((cp, idx) => (
                <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-150 flex flex-col md:flex-row gap-4 items-end md:items-center">
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 flex-1 w-full text-xs">
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Nombre</label>
                      <input
                        type="text"
                        value={cp.name}
                        onChange={(e) => handleCpChange(idx, 'name', e.target.value)}
                        placeholder="ej. Juan Perez"
                        className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Rol Técnico</label>
                      <select
                        value={cp.role}
                        onChange={(e) => handleCpChange(idx, 'role', e.target.value)}
                        className="w-full px-2 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      >
                        <option value="TI">TI</option>
                        <option value="RRHH">RECURSOS HUMANOS</option>
                        <option value="INFRAESTRUCTURA">INFRAESTRUCTURA</option>
                        <option value="COMPRAS">COMPRAS</option>
                        <option value="TERRITORIAL">TERRITORIAL</option>
                        <option value="DIRECTOR">DIRECTOR</option>
                        <option value="UTP_JEFE">JEFE UTP</option>
                        <option value="PIE_ENCARGADO">ENCARGADO PIE</option>
                        <option value="CONVIVENCIA_ESCOLAR">CONVIVENCIA ESCOLAR</option>
                        <option value="INSPECTOR_GENERAL">INSPECTOR GENERAL</option>
                        <option value="SIGE_ENCARGADO">ENCARGADO SIGE</option>
                        <option value="PAME">PAME</option>
                        <option value="PROFESIONAL_INCLUSION">PROFESIONAL INCLUSIÓN</option>
                        <option value="PROFESIONAL_AME_NT">PROFESIONAL AME NT</option>
                        <option value="PERSONAL_PROCESOS_ADM">PERSONAL PROCESOS ADM</option>
                        <option value="GESTOR_INFRAESTRUCTURA">GESTOR INFRAESTRUCTURA</option>
                        <option value="COMPRADOR">COMPRADOR</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Pertenencia</label>
                      <select
                        value={cp.origin}
                        onChange={(e) => handleCpChange(idx, 'origin', e.target.value)}
                        className="w-full px-2 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      >
                        <option value="SLEP">SLEP LLANQUIHUE</option>
                        <option value="ESTABLECIMIENTO">ESTABLECIMIENTO</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Email</label>
                      <input
                        type="email"
                        value={cp.email}
                        onChange={(e) => handleCpChange(idx, 'email', e.target.value)}
                        placeholder="correo@slep.cl"
                        className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Teléfono</label>
                      <input
                        type="text"
                        value={cp.phone}
                        onChange={(e) => handleCpChange(idx, 'phone', e.target.value)}
                        placeholder="+569..."
                        className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      />
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemoveCp(idx)}
                    className="p-2 text-rose-600 hover:bg-rose-50 rounded-lg transition-colors flex-shrink-0"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Editor Tab 3: Conectividad (2030, BAM y otro tipo) */}
        {activeSubTab === 'connectivity' && (
          <EditConectividad conn={est.connectivity} onChange={(connectivity) => setEst({ ...est, connectivity })} />
        )}

        {/* Editor Tab 4: Impresoras */}
        {activeSubTab === 'printers' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h3 className="text-xs font-bold text-slate-600 uppercase tracking-wider">Impresoras Propias</h3>
              <button
                onClick={handleAddOwnedPrinter}
                className="flex items-center gap-1 px-3 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 font-bold rounded-lg text-xs transition-all"
              >
                <Plus size={14} />
                Agregar Impresora
              </button>
            </div>

            <div className="space-y-3">
              {est.printers.owned?.map((pr, idx) => (
                <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-150 flex flex-col md:flex-row gap-4 items-end md:items-center">
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 flex-1 w-full text-xs">
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Modelo</label>
                      <input
                        type="text"
                        value={pr.model}
                        onChange={(e) => handleOwnedPrinterChange(idx, 'model', e.target.value)}
                        placeholder="ej. HP X57945dn"
                        className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Tipo</label>
                      <select
                        value={pr.type}
                        onChange={(e) => handleOwnedPrinterChange(idx, 'type', e.target.value)}
                        className="w-full px-2 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      >
                        <option value="BN">BN (Monocromática)</option>
                        <option value="COLOR">COLOR</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Cantidad</label>
                      <input
                        type="number"
                        min="1"
                        value={pr.qty}
                        onChange={(e) => handleOwnedPrinterChange(idx, 'qty', e.target.value)}
                        className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Proveedor</label>
                      <input
                        type="text"
                        value={pr.provider}
                        onChange={(e) => handleOwnedPrinterChange(idx, 'provider', e.target.value)}
                        className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Licitación</label>
                      <input
                        type="text"
                        value={pr.licitation_code}
                        onChange={(e) => handleOwnedPrinterChange(idx, 'licitation_code', e.target.value)}
                        className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-sans text-xs"
                      />
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemoveOwnedPrinter(idx)}
                    className="p-2 text-rose-600 hover:bg-rose-50 rounded-lg transition-colors flex-shrink-0"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
