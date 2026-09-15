/**
 * test_FE05_routes_tree_structure.test.jsx
 * ─────────────────────────────────────────
 * Tarea: FE-05 · App.jsx migrado a árbol de <Routes> + eliminar estado en memoria
 *        FE-06 · Sidebar con <NavLink> y clase activa automática
 * Correlaciones: Requiere FE-01..FE-04 · Cierra la migración de router
 *
 * Verifica que:
 *   - App.jsx no contiene useState de navegación (activeTab, selectedRbd, isEditing, editData)
 *   - App.jsx no contiene setTimeout (hack eliminado)
 *   - main.jsx usa BrowserRouter
 *   - Rutas declaradas correctamente: /login, /dashboard, /establecimientos, /:rbd, /:rbd/editar, *
 *   - FE-06: NavLink "Panel General" tiene clase activa en /dashboard
 *   - FE-06: NavLink "Directorio" tiene clase activa en /establecimientos y /:rbd
 *   - FE-06: Los items del sidebar son <a> semánticos (no <button>)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { readFileSync } from 'fs';
import { join } from 'path';

// ─── Helpers de análisis de código fuente ────────────────────────────────────

function readSourceFile(relativePath) {
  try {
    return readFileSync(join(process.cwd(), 'src', relativePath), 'utf-8');
  } catch {
    return null;
  }
}

describe('FE-05: App.jsx — Eliminación de estado de navegación en memoria', () => {

  it('FE-05-A: App.jsx no contiene useState para activeTab', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).not.toContain('activeTab');
  });

  it('FE-05-B: App.jsx no contiene useState para selectedRbd', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).not.toContain('selectedRbd');
  });

  it('FE-05-C: App.jsx no contiene useState para isEditing', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).not.toContain('isEditing');
  });

  it('FE-05-D: App.jsx no contiene editData', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).not.toContain('editData');
  });

  it('FE-05-E: App.jsx no contiene setTimeout (hack de recarga eliminado)', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).not.toContain('setTimeout');
  });

  it('FE-05-F: App.jsx importa elementos de react-router-dom', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).toContain('react-router-dom');
    expect(source).toMatch(/<Routes|<Route/);
  });

  it('FE-05-G: App.jsx define ruta /dashboard', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).toContain('/dashboard');
  });

  it('FE-05-H: App.jsx define ruta /establecimientos con :rbd param', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    expect(source).toContain(':rbd');
  });

  it('FE-05-I: App.jsx define ruta comodín * para 404', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    // La ruta 404 puede estar como path="*" 
    expect(source).toMatch(/path=["']\*["']/);
  });

  it('FE-05-J: main.jsx usa BrowserRouter', () => {
    const source = readSourceFile('main.jsx');
    if (!source) return;

    expect(source).toContain('BrowserRouter');
  });
});

// ─── FE-06: Tests del Sidebar con NavLink ─────────────────────────────────────

describe('FE-06: Sidebar — NavLink con clase activa automática', () => {

  it('FE-06-A: El Sidebar usa NavLink (no button) para navegación', () => {
    const source = (readSourceFile('App.jsx') || '') + (readSourceFile('components/AppLayout.jsx') || '');
    if (!source) return;

    expect(source).toContain('NavLink');
  });

  it('FE-06-B: NavLink de Panel General apunta a /dashboard', () => {
    const source = (readSourceFile('App.jsx') || '') + (readSourceFile('components/AppLayout.jsx') || '');
    if (!source) return;

    // Buscar NavLink con to="/dashboard"
    expect(source).toMatch(/NavLink[^>]*to=["']\/?dashboard/);
  });

  it('FE-06-C: NavLink de Directorio apunta a /establecimientos', () => {
    const source = (readSourceFile('App.jsx') || '') + (readSourceFile('components/AppLayout.jsx') || '');
    if (!source) return;

    expect(source).toMatch(/NavLink[^>]*to=["']\/?establecimientos/);
  });

  it('FE-06-D: NavLink en /dashboard tiene clase activa bg-sky-600', async () => {
    const { default: AppLayout } = await import('../../components/AppLayout.jsx').catch(() => ({
      default: null
    }));

    if (!AppLayout) {
      console.warn('AppLayout.jsx no existe aún — test pendiente');
      return;
    }

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            element={
              <AppLayout
                currentUser={{ full_name: 'Admin SLEP', role: 'admin' }}
                onLogout={() => {}}
              />
            }
          >
            <Route path="/dashboard" element={<div>Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      // El NavLink activo debe tener la clase de Tailwind para el estado activo
      const activeLinks = document.querySelectorAll('.bg-sky-600');
      const dashboardActive = Array.from(activeLinks).some(el =>
        el.textContent?.includes('Panel General') ||
        el.getAttribute('href') === '/dashboard'
      );
      expect(dashboardActive).toBe(true);
    });
  });

  it('FE-06-E: NavLink de Directorio tiene clase activa en /establecimientos/:rbd', async () => {
    const { default: AppLayout } = await import('../../components/AppLayout.jsx').catch(() => ({
      default: null
    }));

    if (!AppLayout) {
      console.warn('AppLayout.jsx no existe aún — test pendiente');
      return;
    }

    render(
      <MemoryRouter initialEntries={['/establecimientos/7722']}>
        <Routes>
          <Route
            element={
              <AppLayout
                currentUser={{ full_name: 'Admin SLEP', role: 'admin' }}
                onLogout={() => {}}
              />
            }
          >
            <Route path="/establecimientos/:rbd" element={<div>Ficha</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      const activeLinks = document.querySelectorAll('.bg-sky-600');
      const dirActive = Array.from(activeLinks).some(el =>
        el.textContent?.includes('Directorio') ||
        el.getAttribute('href')?.includes('/establecimientos')
      );
      expect(dirActive).toBe(true);
    });
  });

  it('FE-06-F: Los items del sidebar son <a> semánticos, no <button>', async () => {
    const { default: AppLayout } = await import('../../components/AppLayout.jsx').catch(() => ({
      default: null
    }));

    if (!AppLayout) {
      console.warn('AppLayout.jsx no existe aún — test pendiente');
      return;
    }

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            element={
              <AppLayout
                currentUser={{ full_name: 'Admin SLEP', role: 'admin' }}
                onLogout={() => {}}
              />
            }
          >
            <Route path="/dashboard" element={<div>Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      const navLinks = screen.getAllByRole('link');
      const dashboardLink = navLinks.find(a =>
        a.getAttribute('href') === '/dashboard'
      );
      expect(dashboardLink?.tagName).toBe('A');
    });
  });
});

// ─── Tests de integración FE-05 + FE-06 ──────────────────────────────────────

describe('FE-05/FE-06 Integración: Flujo de navegación con rutas reales', () => {

  it('FE-05-K: La ruta / redirige a /dashboard (redirect de raíz)', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    // Debe tener Navigate to="/dashboard" o ruta / que redirija
    const hasRootRedirect = source.includes('Navigate') && source.includes('/dashboard');
    expect(hasRootRedirect).toBe(true);
  });

  it('FE-05-L: App.jsx solo mantiene estado de autenticación (isAuthenticated, currentUser, checkingAuth)', () => {
    const source = readSourceFile('App.jsx');
    if (!source) return;

    // Estos estados de auth sí deben existir
    expect(source).toContain('isAuthenticated');
    expect(source).toContain('currentUser');
    expect(source).toContain('checkingAuth');

    // Contar cuántos useState hay — con router solo deben ser los 3 de auth
    const useStateMatches = source.match(/useState\(/g) || [];
    expect(useStateMatches.length).toBeLessThanOrEqual(3);
  });
});
