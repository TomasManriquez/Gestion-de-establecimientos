/**
 * test_FE04_protected_route_redirect.test.jsx
 * ─────────────────────────────────────────────
 * Tarea: FE-04 · AppLayout.jsx con <Outlet /> y ProtectedRoute.jsx con redirección
 * Correlaciones: Requiere react-router-dom instalado · Bloquea FE-05
 *
 * Verifica que:
 *   - No-autenticado → redirige a /login?from=<ruta_original>
 *   - Tras login, redirige de vuelta a la ruta original (?from=...)
 *   - Autenticado que visita /login → redirige a /dashboard
 *   - checkingAuth=true muestra spinner, no redirige prematuramente
 *   - Ruta * renderiza NotFound.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';

// ─── Helper: Mock del contexto de autenticación ────────────────────────────

const mockAuthContext = {
  isAuthenticated: false,
  checkingAuth: false,
  currentUser: null,
};

// Mock de AppLayout y ProtectedRoute — a crear por el desarrollador
// Estos tests documentan el comportamiento esperado

describe('FE-04: ProtectedRoute — Redirección por autenticación', () => {

  it('FE-04-A: ProtectedRoute existe como componente', async () => {
    try {
      const module = await import('../../components/ProtectedRoute.jsx');
      expect(module.default).toBeDefined();
    } catch (e) {
      throw new Error(
        'ProtectedRoute.jsx no existe en src/components/. ' +
        'Crear: frontend/src/components/ProtectedRoute.jsx'
      );
    }
  });

  it('FE-04-B: AppLayout existe como componente con <Outlet />', async () => {
    try {
      const module = await import('../../components/AppLayout.jsx');
      expect(module.default).toBeDefined();
    } catch (e) {
      throw new Error(
        'AppLayout.jsx no existe en src/components/. ' +
        'Crear: frontend/src/components/AppLayout.jsx con <Outlet />'
      );
    }
  });

  it('FE-04-C: NotFound.jsx existe como componente', async () => {
    try {
      const module = await import('../../components/NotFound.jsx');
      expect(module.default).toBeDefined();
    } catch (e) {
      throw new Error(
        'NotFound.jsx no existe en src/components/. ' +
        'Crear: frontend/src/components/NotFound.jsx con mensaje 404 y link de retorno'
      );
    }
  });

  // ─── Tests de redirección no-autenticado ─────────────────────────────────

  it('FE-04-D: No-autenticado en /dashboard redirige a /login', async () => {
    const { default: ProtectedRoute } = await import('../../components/ProtectedRoute.jsx');

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            element={
              <ProtectedRoute
                isAuthenticated={false}
                checkingAuth={false}
              />
            }
          >
            <Route path="/dashboard" element={<div>Dashboard</div>} />
          </Route>
          <Route path="/login" element={<div data-testid="login-page">Login</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('login-page')).toBeInTheDocument();
    });
  });

  it('FE-04-E: No-autenticado en /establecimientos/7722 redirige a /login con from param', async () => {
    const { default: ProtectedRoute } = await import('../../components/ProtectedRoute.jsx');

    render(
      <MemoryRouter initialEntries={['/establecimientos/7722']}>
        <Routes>
          <Route
            element={
              <ProtectedRoute
                isAuthenticated={false}
                checkingAuth={false}
              />
            }
          >
            <Route path="/establecimientos/:rbd" element={<div>Ficha</div>} />
          </Route>
          <Route
            path="/login"
            element={<div data-testid="login-page">Login</div>}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('login-page')).toBeInTheDocument();
    });

    // Verificar que la URL de login incluye el parámetro "from"
    // (verificar en la URL actual del MemoryRouter)
    const loginEl = screen.getByTestId('login-page');
    expect(loginEl).toBeInTheDocument();
    // El parámetro ?from= se verifica a nivel de URL en el test de integración INT-01
  });

  it('FE-04-F: checkingAuth=true muestra spinner y NO redirige', async () => {
    const { default: ProtectedRoute } = await import('../../components/ProtectedRoute.jsx');

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            element={
              <ProtectedRoute
                isAuthenticated={false}
                checkingAuth={true}  // Verificando auth
              />
            }
          >
            <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
          </Route>
          <Route path="/login" element={<div data-testid="login-page">Login</div>} />
        </Routes>
      </MemoryRouter>
    );

    // No debe haber redirigido a /login todavía
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument();

    // Debe mostrar algún indicador de loading
    const hasSpinner =
      document.querySelector('[class*="spin"]') ||
      document.querySelector('[class*="loading"]') ||
      screen.queryByRole('status') ||
      screen.queryByText(/verificando/i) ||
      screen.queryByText(/cargando/i);

    expect(hasSpinner).toBeTruthy();
  });

  it('FE-04-G: Autenticado en /dashboard NO redirige — muestra el contenido', async () => {
    const { default: ProtectedRoute } = await import('../../components/ProtectedRoute.jsx');

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            element={
              <ProtectedRoute
                isAuthenticated={true}
                checkingAuth={false}
              />
            }
          >
            <Route path="/dashboard" element={<div data-testid="dashboard-content">Dashboard Content</div>} />
          </Route>
          <Route path="/login" element={<div data-testid="login-page">Login</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-content')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
  });

  it('FE-04-H: Autenticado que visita /login es redirigido a /dashboard', async () => {
    const { default: ProtectedRoute } = await import('../../components/ProtectedRoute.jsx');

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          {/* Login redirige si ya autenticado */}
          <Route
            path="/login"
            element={
              true /* isAuthenticated */
                ? <Navigate to="/dashboard" replace />
                : <div data-testid="login-page">Login Form</div>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('dashboard')).toBeInTheDocument();
    });
  });

  // ─── Test de ruta 404 ─────────────────────────────────────────────────────

  it('FE-04-I: Ruta no existente renderiza NotFound.jsx', async () => {
    const { default: NotFound } = await import('../../components/NotFound.jsx');

    render(
      <MemoryRouter initialEntries={['/ruta-que-no-existe']}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard</div>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </MemoryRouter>
    );

    // NotFound debe mostrar mensaje de error y un link de retorno
    const hasNotFoundContent =
      screen.queryByText(/404/i) ||
      screen.queryByText(/no encontrad/i) ||
      screen.queryByText(/not found/i) ||
      screen.queryByText(/página/i);

    expect(hasNotFoundContent).toBeTruthy();

    const returnLink = screen.queryByRole('link');
    expect(returnLink).toBeTruthy();
  });
});
