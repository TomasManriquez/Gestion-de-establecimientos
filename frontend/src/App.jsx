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

  // La sesión vive en una cookie HttpOnly (ADR-016): el navegador la envía solo y ningún script la lee.
  // Al cargar se pregunta quién es el usuario; un 401 significa «sin sesión». Se registra el interceptor 401.
  useEffect(() => {
    // Purga el token que versiones anteriores dejaron en localStorage (ya no se usa, y no debe quedar ahí).
    try { localStorage.removeItem('token'); } catch { /* sin almacenamiento: nada que purgar */ }
    fetchCurrentUser();

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

  // El cierre en el servidor (revocar y borrar la cookie) lo hace AppLayout con POST /api/auth/logout.
  const handleLogout = () => {
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
          <Route index element={<Navigate to="/tableros/matricula" replace />} />

          {/* Tableros: el acceso directo es Matrícula; /tableros/:tablero queda para el portal. */}
          <Route path="/tableros"                           element={<Navigate to="/tableros/matricula" replace />} />
          <Route path="/tableros/matricula"                 element={<Dashboard />} />
          {/* Ruta anterior del panel: se conserva para los enlaces y marcadores existentes. */}
          <Route path="/dashboard"                          element={<Navigate to="/tableros/matricula" replace />} />
          <Route path="/establecimientos"                   element={<Directory />} />
          <Route path="/establecimientos/:rbd"              element={<FichaEstablecimiento currentUser={currentUser} />} />

          {/* Editar exige la capacidad `write` en `datos`; el backend la vuelve a exigir en cada PUT. */}
          <Route element={<RequireAccess currentUser={currentUser} platform="datos" capability="write"
            message="Tu cuenta puede ver la ficha, pero no editarla. Si lo necesitas, solicítalo a un administrador." />}>
            <Route path="/establecimientos/:rbd/editar"     element={<EditFicha />} />
          </Route>

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
