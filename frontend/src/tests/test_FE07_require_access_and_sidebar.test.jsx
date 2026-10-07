/**
 * test_FE07_require_access_and_sidebar.test.jsx
 * ─────────────────────────────────────────────
 * Tarea: US-40 · Guard de rol y menú lateral colapsable con «Configuración › Usuarios»
 *
 * Verifica que:
 *   - RequireAccess muestra la ruta hija solo con el rol exigido; si no, «Sin acceso» (sin redirigir)
 *   - «Configuración › Usuarios» aparece solo para el admin global (iam/admin)
 *   - el sidebar se colapsa a íconos accionables, recuerda el estado y mantiene el nombre accesible
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import RequireAccess from '@/components/RequireAccess';
import AppLayout from '@/components/AppLayout';
import { ADMIN } from './usersFixtures';

const VIEWER = { ...ADMIN, id: 'u9', role: 'viewer', access: [{ platform_id: 'datos', role: 'viewer' }] };

function renderGuard(currentUser) {
  return render(
    <MemoryRouter initialEntries={['/configuracion/usuarios']}>
      <Routes>
        <Route element={<RequireAccess currentUser={currentUser} platform="iam" roles={['admin']} />}>
          <Route path="/configuracion/usuarios" element={<p>Contenido protegido</p>} />
        </Route>
        <Route path="/dashboard" element={<p>Panel</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderLayout(currentUser) {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route element={<AppLayout currentUser={currentUser} onLogout={() => {}} />}>
          <Route path="/dashboard" element={<p>Panel</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => { localStorage.clear(); });

describe('FE07: RequireAccess', () => {
  it('FE07-A: el admin global ve el contenido', () => {
    renderGuard(ADMIN);
    expect(screen.getByText('Contenido protegido')).toBeInTheDocument();
  });

  it('FE07-B: sin el rol exigido muestra «Sin acceso a esta sección» y no el contenido', () => {
    renderGuard(VIEWER);
    expect(screen.getByText('Sin acceso a esta sección')).toBeInTheDocument();
    expect(screen.queryByText('Contenido protegido')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver al panel' })).toHaveAttribute('href', '/dashboard');
  });

  it('FE07-C: un editor de Datos tampoco entra (el rol debe ser el de iam)', () => {
    renderGuard({ ...VIEWER, access: [{ platform_id: 'datos', role: 'admin' }] });
    expect(screen.getByText('Sin acceso a esta sección')).toBeInTheDocument();
  });

  it('FE07-D: sin currentUser no revienta y niega el acceso', () => {
    renderGuard(null);
    expect(screen.getByText('Sin acceso a esta sección')).toBeInTheDocument();
  });
});

describe('FE07: AppLayout — menú lateral', () => {
  it('FE07-E: «Usuarios» solo aparece para el admin global', () => {
    const { unmount } = renderLayout(ADMIN);
    expect(screen.getByText('Configuración')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Usuarios' })).toHaveAttribute('href', '/configuracion/usuarios');
    unmount();
    renderLayout(VIEWER);
    expect(screen.queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
    expect(screen.queryByText('Configuración')).not.toBeInTheDocument();
  });

  it('FE07-F: el botón alterna el colapso, cambia aria-expanded y persiste en localStorage', async () => {
    const user = userEvent.setup();
    const { container } = renderLayout(ADMIN);
    const aside = container.querySelector('aside');
    expect(aside).toHaveAttribute('data-collapsed', 'false');
    const toggle = screen.getByRole('button', { name: 'Contraer barra lateral' });
    expect(toggle).toHaveAttribute('aria-expanded', 'true');

    await user.click(toggle);
    expect(aside).toHaveAttribute('data-collapsed', 'true');
    expect(localStorage.getItem('sidebar-collapsed')).toBe('1');
    expect(screen.getByRole('button', { name: 'Expandir barra lateral' })).toHaveAttribute('aria-expanded', 'false');

    await user.click(screen.getByRole('button', { name: 'Expandir barra lateral' }));
    expect(aside).toHaveAttribute('data-collapsed', 'false');
    expect(localStorage.getItem('sidebar-collapsed')).toBe('0');
  });

  it('FE07-G: colapsado, los enlaces siguen siendo enlaces con nombre accesible y sin texto visible', async () => {
    localStorage.setItem('sidebar-collapsed', '1');
    renderLayout(ADMIN);
    for (const name of ['Panel General', 'Directorio de Recintos', 'Usuarios']) {
      const link = screen.getByRole('link', { name });
      expect(link.tagName).toBe('A');
      expect(link).toHaveTextContent('');
      expect(link.className).toMatch(/w-12 h-12/);
    }
    expect(screen.getByRole('button', { name: 'Cerrar Sesión' })).toBeInTheDocument();
    expect(screen.queryByText('Llanquihue')).not.toBeInTheDocument();
  });

  it('FE07-H: expandido muestra los textos', () => {
    renderLayout(ADMIN);
    expect(screen.getByText('Panel General')).toBeInTheDocument();
    expect(screen.getByText('Llanquihue')).toBeInTheDocument();
  });
});
