import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Building2, Users, MapPin, Award, 
  TrendingUp, BarChart3, PieChart as PieIcon, Radio 
} from 'lucide-react';
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#6366f1', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6'];

const StatCard = ({ title, value, icon: Icon, description, trend }) => (
  <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-all duration-300 flex items-start justify-between group">
    <div className="space-y-2">
      <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">{title}</p>
      <h3 className="text-3xl font-extrabold font-outfit text-slate-800 tracking-tight">{value}</h3>
      {description && (
        <p className="text-xs text-slate-500 font-sans flex items-center gap-1">
          {trend && <span className="text-emerald-500 font-semibold">{trend}</span>}
          {description}
        </p>
      )}
    </div>
    <div className="p-3 bg-sky-50 text-sky-600 rounded-xl group-hover:bg-sky-600 group-hover:text-white transition-all duration-300 shadow-sm shadow-sky-500/5">
      <Icon size={22} />
    </div>
  </div>
);

export default function Dashboard() {
  const [kpis, setKpis] = useState(null);
  const [charts, setCharts] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [kpiRes, chartRes] = await Promise.all([
          axios.get('/api/analytics/kpis'),
          axios.get('/api/analytics/charts')
        ]);
        setKpis(kpiRes.data);
        setCharts(chartRes.data);
      } catch (err) {
        console.error('Error fetching analytics data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="w-12 h-12 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin"></div>
        <p className="text-sm font-medium text-slate-500">Cargando análisis de la red...</p>
      </div>
    );
  }

  const enrollmentTrend = kpis 
    ? `${Math.round(((kpis.total_enrollment_2026 - kpis.total_enrollment_2025) / kpis.total_enrollment_2025) * 100)}%` 
    : '0%';

  return (
    <div className="space-y-8 animate-fade-in">
      <header>
        <h1 className="text-3xl font-extrabold font-outfit text-slate-800 tracking-tight">
          Territorio Educativo
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Análisis demográfico y de conectividad de los establecimientos administrados por el SLEP Llanquihue.
        </p>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Establecimientos"
          value={kpis?.total_establishments || 0}
          icon={Building2}
          description="Escuelas y jardines infantiles"
        />
        <StatCard
          title="Matrícula Total 2026"
          value={kpis?.total_enrollment_2026?.toLocaleString() || 0}
          icon={Users}
          trend={kpis?.total_enrollment_2026 < kpis?.total_enrollment_2025 ? '' : '+'}
          description={`vs ${kpis?.total_enrollment_2025?.toLocaleString() || 0} en 2025`}
        />
        <StatCard
          title="Docentes Activos"
          value={kpis?.total_teachers_2026?.toLocaleString() || 0}
          icon={Award}
          description="Profesionales de aula 2026"
        />
        <StatCard
          title="Comunas Cobertas"
          value={kpis?.total_communes || 0}
          icon={MapPin}
          description="Puerto Varas, Frutillar, Fresia, etc."
        />
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Chart 1: Enrollment Urban vs Rural (Pie Chart) */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col h-[400px]">
          <div className="flex items-center gap-2 mb-6">
            <PieIcon size={18} className="text-sky-600" />
            <h3 className="text-base font-bold text-slate-800 font-outfit">Matrícula por Tipo de Área (2026)</h3>
          </div>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={charts?.enrollment_by_area || []}
                  cx="50%"
                  cy="45%"
                  innerRadius={70}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                >
                  {(charts?.enrollment_by_area || []).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={index === 0 ? '#3b82f6' : '#10b981'} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => [value.toLocaleString() + " Alumnos", "Matrícula"]} />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Enrollment by Commune (Bar Chart) */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col h-[400px]">
          <div className="flex items-center gap-2 mb-6">
            <BarChart3 size={18} className="text-sky-600" />
            <h3 className="text-base font-bold text-slate-800 font-outfit">Matrícula por Comuna (2026)</h3>
          </div>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts?.enrollment_by_commune || []} margin={{ bottom: 15 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(value) => [value.toLocaleString() + " Alumnos", "Matrícula"]} cursor={{ fill: '#f8fafc' }} />
                <Bar dataKey="value" fill="#6366f1" radius={[8, 8, 0, 0]} maxBarSize={50} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 3: Category distribution */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col h-[400px]">
          <div className="flex items-center gap-2 mb-6">
            <TrendingUp size={18} className="text-sky-600" />
            <h3 className="text-base font-bold text-slate-800 font-outfit">Establecimientos por Categoría</h3>
          </div>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts?.establishments_by_category || []} layout="vertical" margin={{ left: 30, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} width={120} />
                <Tooltip formatter={(value) => [value + " Recintos", "Cantidad"]} cursor={{ fill: '#f8fafc' }} />
                <Bar dataKey="value" fill="#3b82f6" radius={[0, 8, 8, 0]} maxBarSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 4: Internet Providers */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col h-[400px]">
          <div className="flex items-center gap-2 mb-6">
            <Radio size={18} className="text-sky-600" />
            <h3 className="text-base font-bold text-slate-800 font-outfit">Distribución de Conectividad (Proveedores)</h3>
          </div>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={charts?.establishments_by_connectivity || []}
                  cx="50%"
                  cy="45%"
                  innerRadius={0}
                  outerRadius={100}
                  paddingAngle={0}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {(charts?.establishments_by_connectivity || []).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => [value + " Establecimientos", "Cantidad"]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </div>
  );
}
