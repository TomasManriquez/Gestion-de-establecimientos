import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';

import Login from './components/Login';
import Dashboard from './components/Dashboard';
import Directory from './components/Directory';
import FichaEstablecimiento from './components/FichaEstablecimiento';
import EditFicha from './components/EditFicha';
import AppLayout from './components/AppLayout';
import ProtectedRoute from './components/ProtectedRoute';
import NotFound from './components/NotFound';
import RequireAccess from './components/RequireAccess';
import UsersPage from './components/users/UsersPage';
import { Toaster } from '@/components/ui/sonner';

/**
 * App — FE-05
 * Solo gestiona estado de autenticación (isAuthenticated, currentUser, checkingAuth).
 * La navegación entre vistas la maneja React Router — ya no hay estado de navegación
 * en memoria ni hacks de recarga basados en temporizadores.
 */
export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [checkingAuth, setCheckingAuth]       = useState(true);
  const [currentUser, setCurrentUser]         = useState(null);

  // Inicializar axios con el token guardado y registrar interceptor 401
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchCurrentUser();
    } else {
      setCheckingAuth(false);
    }

    const interceptor = axios.interceptors.response.use(
      response => response,
      error => {
        if (error.response?.status === 401) handleLogout();
        return Promise.reject(error);
      }
    );

    return () => axios.interceptors.response.eject(interceptor);
  }, []);

  const fetchCurrentUser = async () => {
    try {
      const { data } = await axios.get('/api/auth/me');
      setCurrentUser(data);
      setIsAuthenticated(true);
    } catch {
      handleLogout();
    } finally {
      setCheckingAuth(false);
    }
  };

  const handleLoginSuccess = () => fetchCurrentUser();

  const handleLogout = () => {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setIsAuthenticated(false);
    setCurrentUser(null);
  };

  return (
    <>
    <Toaster richColors closeButton position="top-right" />
    <Routes>
      {/* Ruta pública */}
      <Route
        path="/login"
        element={
          isAuthenticated
            ? <Navigate to="/dashboard" replace />
            : <Login onLoginSuccess={handleLoginSuccess} />
        }
      />

      {/* Rutas protegidas — ProtectedRoute actúa como layout guard */}
      <Route
        element={
          <ProtectedRoute
            isAuthenticated={isAuthenticated}
            checkingAuth={checkingAuth}
          />
        }
      >
        {/* AppLayout contiene Sidebar + <Outlet /> */}
        <Route
          element={
            <AppLayout
              currentUser={currentUser}
              onLogout={handleLogout}
            />
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"                          element={<Dashboard />} />
          <Route path="/establecimientos"                   element={<Directory />} />
          <Route path="/establecimientos/:rbd"              element={<FichaEstablecimiento />} />
          <Route path="/establecimientos/:rbd/editar"       element={<EditFicha />} />

          {/* Configuración: solo el admin global (iam/admin). El backend vuelve a verificarlo. */}
          <Route element={<RequireAccess currentUser={currentUser} platform="iam" roles={['admin']} />}>
            <Route path="/configuracion" element={<Navigate to="/configuracion/usuarios" replace />} />
            <Route path="/configuracion/usuarios" element={<UsersPage currentUser={currentUser} />} />
          </Route>
        </Route>
      </Route>

      {/* 404 para cualquier ruta no definida */}
      <Route path="*" element={<NotFound />} />
    </Routes>
    </>
  );
}
