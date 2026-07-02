import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { School, PieChart, Building2, LogOut, User, RefreshCw } from 'lucide-react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import Directory from './components/Directory';
import FichaEstablecimiento from './components/FichaEstablecimiento';
import EditFicha from './components/EditFicha';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  
  // Navigation states
  const [activeTab, setActiveTab] = useState('dashboard'); // dashboard, directory
  const [selectedRbd, setSelectedRbd] = useState(null);
  
  // Editing state
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({ est: null, cps: [], metrics: [] });

  // Initialize axios and auth state
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchCurrentUser();
    } else {
      setCheckingAuth(false);
    }

    // Response interceptor to handle 401 errors (expired tokens)
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          handleLogout();
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, []);

  const fetchCurrentUser = async () => {
    try {
      const response = await axios.get('/api/auth/me');
      setCurrentUser(response.data);
      setIsAuthenticated(true);
    } catch (err) {
      console.error('Error validating token', err);
      handleLogout();
    } finally {
      setCheckingAuth(false);
    }
  };

  const handleLoginSuccess = () => {
    fetchCurrentUser();
  };

  const handleLogout = async () => {
    // Try notifying backend logout endpoint, ignore failure
    try {
      await axios.post('/api/auth/logout');
    } catch {}
    
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setIsAuthenticated(false);
    setCurrentUser(null);
    setSelectedRbd(null);
    setIsEditing(false);
  };

  const handleSelectEstablishment = (rbd) => {
    setSelectedRbd(rbd);
    setIsEditing(false);
  };

  const handleOpenEdit = (est, cps, metrics) => {
    setEditData({ est, cps, metrics });
    setIsEditing(true);
  };

  const handleSaveSuccess = () => {
    setIsEditing(false);
    // Reload data inside FichaEstablecimiento by triggering state reload (re-selecting it)
    const r = selectedRbd;
    setSelectedRbd(null);
    setTimeout(() => {
      setSelectedRbd(r);
    }, 10);
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center gap-3">
        <RefreshCw size={32} className="animate-spin text-sky-500" />
        <p className="text-sm font-semibold text-slate-400">Verificando sesión segura...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex text-slate-800 font-sans antialiased">
      
      {/* SIDEBAR */}
      <aside className="w-72 bg-slate-900 text-slate-300 h-screen sticky top-0 flex flex-col z-20 shadow-xl border-r border-slate-800">
        
        {/* Brand block */}
        <div className="p-6 border-b border-slate-800 flex items-center gap-3">
          <div className="p-2.5 bg-sky-600 text-white rounded-xl shadow-md shadow-sky-600/10">
            <School size={24} />
          </div>
          <div>
            <h1 className="text-lg font-extrabold font-outfit text-white leading-tight">
              SLEP
            </h1>
            <p className="text-[10px] font-bold text-sky-400 uppercase tracking-widest leading-none">
              Llanquihue
            </p>
          </div>
        </div>

        {/* User profile section */}
        <div className="p-5 border-b border-slate-800 flex items-center gap-3 bg-slate-950/40">
          <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-sky-400 border border-slate-700 shadow-inner">
            <User size={20} />
          </div>
          <div className="min-w-0 flex-1">
            <span className="block text-xs text-slate-500 font-semibold uppercase tracking-wider">
              {currentUser?.role === 'admin' ? 'Administrador' : 'Usuario'}
            </span>
            <h4 className="text-sm font-bold text-white truncate font-outfit">
              {currentUser?.full_name || 'Usuario SLEP'}
            </h4>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="p-5 flex-1 space-y-2">
          <button 
            onClick={() => { setActiveTab('dashboard'); setSelectedRbd(null); setIsEditing(false); }}
            className={`flex items-center gap-3.5 w-full px-4 py-3 rounded-xl text-sm font-bold transition-all font-outfit ${
              activeTab === 'dashboard' && !selectedRbd 
                ? 'bg-sky-600 text-white shadow-lg shadow-sky-600/10' 
                : 'hover:bg-slate-800 hover:text-white'
            }`}
          >
            <PieChart size={18} />
            Panel General
          </button>
          
          <button 
            onClick={() => { setActiveTab('directory'); setSelectedRbd(null); setIsEditing(false); }}
            className={`flex items-center gap-3.5 w-full px-4 py-3 rounded-xl text-sm font-bold transition-all font-outfit ${
              activeTab === 'directory' && !selectedRbd 
                ? 'bg-sky-600 text-white shadow-lg shadow-sky-600/10' 
                : 'hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Building2 size={18} />
            Directorio de Recintos
          </button>
        </nav>

        {/* Logout block */}
        <div className="p-5 border-t border-slate-800 bg-slate-950/20">
          <button 
            onClick={handleLogout}
            className="flex items-center justify-center gap-2.5 w-full py-3 bg-slate-800 hover:bg-rose-950/30 hover:text-rose-400 text-slate-400 hover:border-rose-950/40 border border-slate-700/50 font-bold rounded-xl text-xs transition-all uppercase tracking-wider font-outfit"
          >
            <LogOut size={14} />
            Cerrar Sesión
          </button>
        </div>

      </aside>

      {/* MAIN VIEW AREA */}
      <main className="flex-1 min-w-0 p-8 lg:p-10 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {selectedRbd ? (
            isEditing ? (
              <EditFicha 
                initialEst={editData.est} 
                initialCps={editData.cps} 
                initialMetrics={editData.metrics}
                onSaveSuccess={handleSaveSuccess} 
                onCancel={() => setIsEditing(false)} 
              />
            ) : (
              <FichaEstablecimiento 
                rbd={selectedRbd} 
                onBack={() => setSelectedRbd(null)} 
                onEdit={handleOpenEdit} 
              />
            )
          ) : activeTab === 'dashboard' ? (
            <Dashboard />
          ) : (
            <Directory onSelectEstablishment={handleSelectEstablishment} />
          )}
        </div>
      </main>

    </div>
  );
}
