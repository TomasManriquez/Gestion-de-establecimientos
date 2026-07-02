import React, { useState } from 'react';
import axios from 'axios';
import { Save, X, Plus, Trash2, ShieldAlert } from 'lucide-react';

export default function EditFicha({ initialEst, initialCps, initialMetrics, onSaveSuccess, onCancel }) {
  const [est, setEst] = useState({ ...initialEst });
  const [cps, setCps] = useState([...initialCps]);
  const [deletedCpIds, setDeletedCpIds] = useState([]);
  const [saving, setSaving] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('general');

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

  const handleConnectivityChange = (field, value) => {
    setEst(prev => ({
      ...prev,
      connectivity: {
        ...prev.connectivity,
        [field]: value
      }
    }));
  };

  const handleStarlinkChange = (value) => {
    setEst(prev => ({
      ...prev,
      connectivity: {
        ...prev.connectivity,
        starlink: {
          ...prev.connectivity.starlink,
          installed: value
        }
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

  const handleSave = async () => {
    setSaving(true);
    try {
      // 1. Save base establishment (general_info, connectivity, printers)
      const estPayload = {
        name: est.name,
        comuna: est.comuna,
        area_type: est.area_type,
        address: est.address,
        general_info: est.general_info,
        connectivity: est.connectivity,
        printers: est.printers,
        licenses: est.licenses
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

      onSaveSuccess();
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
            onClick={onCancel}
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
          { id: 'counterparts', label: 'Contrapartes Técnicas' },
          { id: 'connectivity', label: 'Configuración Conectividad' },
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

        {/* Editor Tab 3: Conectividad */}
        {activeSubTab === 'connectivity' && (
          <div className="space-y-6">
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-4">
              <h3 className="text-xs font-bold text-slate-600 uppercase tracking-wider">Fibra óptica Conectividad 2030 (TELSUR)</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-500">SSID Red Wifi</label>
                  <input
                    type="text"
                    value={est.connectivity.ssid}
                    onChange={(e) => handleConnectivityChange('ssid', e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-sky-500 font-sans"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-500">Clave SSID</label>
                  <input
                    type="text"
                    value={est.connectivity.ssid_password}
                    onChange={(e) => handleConnectivityChange('ssid_password', e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-sky-500 font-sans"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-500">Velocidad (Mbps)</label>
                  <input
                    type="text"
                    value={est.connectivity.download_speed_2030}
                    onChange={(e) => handleConnectivityChange('download_speed_2030', e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-sky-500 font-sans"
                  />
                </div>
              </div>

              <div className="flex items-center gap-4 pt-2">
                <label className="text-xs font-semibold text-slate-600">¿Cuenta con Antena Starlink?</label>
                <div className="flex items-center gap-4">
                  <label className="inline-flex items-center gap-1.5 cursor-pointer text-xs">
                    <input
                      type="radio"
                      name="starlink"
                      checked={est.connectivity.starlink?.installed === true}
                      onChange={() => handleStarlinkChange(true)}
                      className="text-sky-600 focus:ring-sky-500"
                    />
                    Sí (Instalado)
                  </label>
                  <label className="inline-flex items-center gap-1.5 cursor-pointer text-xs">
                    <input
                      type="radio"
                      name="starlink"
                      checked={est.connectivity.starlink?.installed === false}
                      onChange={() => handleStarlinkChange(false)}
                      className="text-sky-600 focus:ring-sky-500"
                    />
                    No
                  </label>
                </div>
              </div>
            </div>
          </div>
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
