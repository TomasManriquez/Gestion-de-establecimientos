/**
 * test_FE25_mobile_shell.test.jsx
 * ───────────────────────────────
 * Tarea: PWA fase 0 — la misma SPA se adapta al ancho (ADR-020)
 *
 * Verifica que:
 *   - bajo `lg` (1024 px) AppLayout muestra la barra inferior en vez del sidebar
 *   - el Directorio pasa de tabla a tarjetas y plega los filtros secundarios
 *   - desde 1024 px todo sigue como antes (sidebar y tabla)
 *   - nginx.conf no deja cachear sw.js/index.html y permite el worker en la CSP
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { readFileSync } from 'fs';
import { join } from 'path';
import axios from 'axios';
import AppLayout from '@/components/AppLayout';
import Directory from '@/components/Directory';
import { ADMIN } from './usersFixtures';

vi.mock('axios');

const setWidth = (w) => { window.innerWidth = w; };
afterEach(() => setWidth(1024));
beforeEach(() => {
  localStorage.clear();
  axios.get.mockResolvedValue({
    data: {
      items: [{ rbd: '7722', rbd_full: '7722-3', name: 'LICEO POLITÉCNICO PUERTO VARAS', comuna: 'PUERTO VARAS',
        area_type: 'URBANO', category: '7. LICEO POLITÉCNICO' }],
      total: 1, page: 1, page_size: 100, total_pages: 1,
    },
  });
});

const renderLayout = () => render(
  <MemoryRouter initialEntries={['/establecimientos']}>
    <Routes>
      <Route element={<AppLayout currentUser={ADMIN} onLogout={() => {}} />}>
        <Route path="/establecimientos" element={<p>Directorio</p>} />
      </Route>
    </Routes>
  </MemoryRouter>,
);

const renderDirectory = () => render(<MemoryRouter><Directory /></MemoryRouter>);

describe('FE25: AppLayout adaptativo', () => {
  it('FE25-A: en móvil hay barra inferior y no sidebar', () => {
    setWidth(375);
    renderLayout();
    expect(screen.getByRole('link', { name: 'Tableros' })).toHaveAttribute('href', '/tableros/matricula');
    expect(screen.getByRole('link', { name: 'Directorio' }).className).toContain('bg-white/10');
    expect(screen.getByRole('link', { name: 'Usuarios' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Salir' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /barra lateral/ })).not.toBeInTheDocument();
  });

  it('FE25-B: en escritorio sigue el sidebar y no hay barra inferior', () => {
    renderLayout();
    expect(screen.getByRole('button', { name: 'Contraer barra lateral' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Salir' })).not.toBeInTheDocument();
  });
});

describe('FE25: Directorio adaptativo', () => {
  it('FE25-C: en móvil son tarjetas enlazadas y los filtros secundarios se despliegan a pedido', async () => {
    setWidth(375);
    renderDirectory();
    const card = await screen.findByRole('link', { name: /LICEO POLITÉCNICO PUERTO VARAS/ });
    expect(card).toHaveAttribute('href', '/establecimientos/7722');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    const toggle = screen.getByRole('button', { name: 'Más filtros' });
    const comuna = screen.getByDisplayValue('Todas las comunas');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(comuna.closest('.hidden')).not.toBeNull();
    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Ocultar filtros' })).toHaveAttribute('aria-expanded', 'true');
    expect(comuna.closest('.hidden')).toBeNull();
  });

  it('FE25-D: en escritorio sigue la tabla y no hay botón de filtros', async () => {
    renderDirectory();
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Más filtros' })).not.toBeInTheDocument();
  });
});

describe('FE25: nginx para PWA', () => {
  const nginx = readFileSync(join(process.cwd(), 'nginx.conf'), 'utf-8');

  it('FE25-E: sw.js e index.html salen sin caché, antes de la regla de estáticos', () => {
    const sw = nginx.indexOf('sw\\.js');
    const statics = nginx.indexOf('(js|css|png');
    expect(sw).toBeGreaterThan(-1);
    expect(sw).toBeLessThan(statics); // nginx aplica la primera regex que calza
    expect(nginx).toMatch(/sw\\\.js[^{]*\{[^}]*expires -1;/);
  });

  it("FE25-F: la CSP permite el service worker desde 'self'", () => {
    expect(nginx).toContain("worker-src 'self' blob:");
  });
});
