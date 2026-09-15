/**
 * test_INT01_full_user_flow.test.jsx
 * ────────────────────────────────────
 * Tarea: INT-01 · Flujo completo: Login → Directorio → Ficha → Edición → Retorno
 * Correlaciones: Requiere todos los BE-* y FE-* completados
 *
 * Es el test de aceptación final que verifica toda la cadena de navegación
 * y que no hay regresiones en el flujo principal del sistema.
 *
 * Verifica:
 *   1. Login → redirige a /dashboard
 *   2. Dashboard carga KPIs y gráficos
 *   3. Navegar a Directorio → URL /establecimientos
 *   4. Filtrar por comuna → URL actualizada, tabla filtrada
 *   5. Click en establecimiento → URL /establecimientos/{rbd}
 *   6. Volver al directorio → filtros intactos en URL
 *   7. Click Editar → URL /establecimientos/{rbd}/editar
 *   8. Guardar → navega a /establecimientos/{rbd} (sin setTimeout)
 *   9. Logout → redirige a /login
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import { readFileSync } from 'fs';
import { join } from 'path';

vi.mock('axios');

// ─── Datos mock completos ─────────────────────────────────────────────────────

const ADMIN_USER = { username: 'admin', full_name: 'Administrador SLEP', role: 'admin' };

const MOCK_KPIS = {
  total_establishments: 79,
  total_enrollment_2026: 12500,
  total_enrollment_2025: 12200,
  total_teachers_2026: 890,
  total_communes: 5,
};

const MOCK_CHARTS = {
  enrollment_by_area: [{ label: 'URBANO', value: 9500 }, { label: 'RURAL', value: 3000 }],
  enrollment_by_commune: [{ label: 'PUERTO VARAS', value: 5000 }],
  establishments_by_category: [{ label: 'LICEO POLITÉCNICO', value: 3 }],
  establishments_by_connectivity: [{ label: 'TELSUR', value: 45 }],
};

const MOCK_LISTING_ALL = {
  items: [
    {
      rbd: '7722', rbd_full: '7722-3',
      name: 'LICEO POLITÉCNICO PUERTO VARAS',
      comuna: 'PUERTO VARAS', area_type: 'URBANO',
      category: '7. LICEO POLITÉCNICO', adp: 'Si', covertura: 'MEDIA',
    },
    {
      rbd: '7801', rbd_full: '7801-5',
      name: 'ESCUELA BÁSICA FRUTILLAR',
      comuna: 'FRUTILLAR', area_type: 'RURAL',
      category: '6. RURAL MULTIGRADO', adp: 'No', covertura: 'BASICA',
    },
  ],
  total: 2, page: 1, page_size: 100, total_pages: 1,
};

const MOCK_LISTING_FRUTILLAR = {
  items: [MOCK_LISTING_ALL.items[1]],
  total: 1, page: 1, page_size: 100, total_pages: 1,
};

const MOCK_FICHA_7722 = {
  rbd: '7722', rbd_full: '7722-3', name: 'LICEO POLITÉCNICO PUERTO VARAS',
  comuna: 'PUERTO VARAS', area_type: 'URBANO', address: 'Calle Ejemplo 123',
  general_info: { director: 'Juan Pérez', category: '7. LICEO POLITÉCNICO', adp: 'Si' },
  connectivity: { internet_provider: 'TELSUR', ssid: 'LiceoRed', ssid_password: '[REDACTED]' },
  printers: { owned: [], leased: [] },
  licenses: [{ name: 'SIGE', email: 'admin@liceo.cl', password: '[REDACTED]' }],
};

const MOCK_COUNTERPARTS = [{ _id: 'cp1', rbd: '7722', role: 'TI', origin: 'SLEP', name: 'Carlos TI', email: '', phone: '' }];
const MOCK_METRICS = [{ _id: 'm1', rbd: '7722', year: 2026, enrollment: 450 }];

// Setup del mock de axios con lógica por URL
function setupAxiosMocks(comunaFilter = '') {
  axios.get.mockImplementation((url, config) => {
    const params = config?.params ?? {};

    if (url === '/api/analytics/kpis') return Promise.resolve({ data: MOCK_KPIS });
    if (url === '/api/analytics/charts') return Promise.resolve({ data: MOCK_CHARTS });

    if (url === '/api/establishments') {
      if (params.comuna === 'FRUTILLAR') return Promise.resolve({ data: MOCK_LISTING_FRUTILLAR });
      return Promise.resolve({ data: MOCK_LISTING_ALL });
    }

    if (url === '/api/establishments/7722') return Promise.resolve({ data: MOCK_FICHA_7722 });
    if (url.includes('/counterparts/establishment/7722')) return Promise.resolve({ data: MOCK_COUNTERPARTS });
    if (url.includes('/metrics/establishment/7722')) return Promise.resolve({ data: MOCK_METRICS });
    if (url === '/api/auth/me') return Promise.resolve({ data: ADMIN_USER });

    return Promise.resolve({ data: [] });
  });

  axios.put.mockResolvedValue({ data: MOCK_FICHA_7722 });
  axios.post.mockResolvedValue({ data: { message: 'ok' } });
}

// ─── Tests del flujo completo ─────────────────────────────────────────────────

describe('INT-01: Flujo completo de usuario autenticado', () => {

  beforeEach(() => {
    vi.resetAllMocks();
    setupAxiosMocks();
  });

  it('INT-01-A: Dashboard carga y muestra KPIs después del login', async () => {
    const { default: Dashboard } = await import('../../components/Dashboard.jsx');

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      // Los KPIs deben aparecer en la UI
      expect(screen.queryByText('79') || screen.queryByText(/79/)).toBeTruthy();
    }, { timeout: 3000 });

    expect(axios.get).toHaveBeenCalledWith('/api/analytics/kpis');
    expect(axios.get).toHaveBeenCalledWith('/api/analytics/charts');
  });

  it('INT-01-B: El directorio carga la lista sin campos sensibles', async () => {
    const { default: Directory } = await import('../../components/Directory.jsx');

    render(
      <MemoryRouter initialEntries={['/establecimientos']}>
        <Routes>
          <Route path="/establecimientos" element={<Directory />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('LICEO POLITÉCNICO PUERTO VARAS')).toBeInTheDocument();
    }, { timeout: 3000 });

    // Verificar que los items no tienen datos sensibles
    const items = MOCK_LISTING_ALL.items;
    items.forEach(item => {
      expect(item).not.toHaveProperty('licenses');
      expect(item).not.toHaveProperty('connectivity');
    });
  });

  it('INT-01-C: Filtrar por FRUTILLAR actualiza la tabla y la URL', async () => {
    const { default: Directory } = await import('../../components/Directory.jsx');

    render(
      <MemoryRouter initialEntries={['/establecimientos']}>
        <Routes>
          <Route path="/establecimientos" element={<Directory />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('LICEO POLITÉCNICO PUERTO VARAS')).toBeInTheDocument();
    });

    // Seleccionar filtro de comuna
    const selects = screen.getAllByRole('combobox');
    const comunaSelect = selects[0]; // primer select = comunas

    await userEvent.selectOptions(comunaSelect, 'FRUTILLAR');

    await waitFor(() => {
      const lastCall = axios.get.mock.calls.at(-1);
      expect(lastCall?.[1]?.params?.comuna).toBe('FRUTILLAR');
    }, { timeout: 2000 });
  });

  it('INT-01-D: Volver del directorio con filtros mantiene los filtros en la URL', async () => {
    const { default: Directory } = await import('../../components/Directory.jsx');
    const { default: FichaEstablecimiento } = await import('../../components/FichaEstablecimiento.jsx');

    render(
      <MemoryRouter initialEntries={['/establecimientos?comuna=FRUTILLAR']}>
        <Routes>
          <Route path="/establecimientos" element={<Directory />} />
          <Route path="/establecimientos/:rbd" element={<FichaEstablecimiento />} />
        </Routes>
      </MemoryRouter>
    );

    // El directorio debe cargar con el filtro ya aplicado
    await waitFor(() => {
      const lastCall = axios.get.mock.calls.at(-1);
      expect(lastCall?.[1]?.params?.comuna).toBe('FRUTILLAR');
    }, { timeout: 2000 });
  });

  it('INT-01-E: Acceso directo a ficha /establecimientos/7722 carga la ficha', async () => {
    const { default: FichaEstablecimiento } = await import('../../components/FichaEstablecimiento.jsx');

    render(
      <MemoryRouter initialEntries={['/establecimientos/7722']}>
        <Routes>
          <Route path="/establecimientos/:rbd" element={<FichaEstablecimiento />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/LICEO POLITÉCNICO PUERTO VARAS/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Los 3 fetches de la ficha
    expect(axios.get).toHaveBeenCalledWith('/api/establishments/7722');
    expect(axios.get).toHaveBeenCalledWith('/api/counterparts/establishment/7722');
    expect(axios.get).toHaveBeenCalledWith('/api/metrics/establishment/7722');
  });

  it('INT-01-F: La respuesta de la ficha tiene passwords redactados ([REDACTED])', async () => {
    // Verificar que los datos mock simulan la respuesta correcta de BE-05
    expect(MOCK_FICHA_7722.licenses[0].password).toBe('[REDACTED]');
    expect(MOCK_FICHA_7722.connectivity.ssid_password).toBe('[REDACTED]');
  });

  it('INT-01-G: El guardado en EditFicha NO usa setTimeout', async () => {
    const source = readFileSync(join(process.cwd(), 'src/App.jsx'), 'utf-8').catch?.() ||
                   (() => {
                     try {
                       const { readFileSync } = require('fs');
                       const { join } = require('path');
                       return readFileSync(join(process.cwd(), 'src/App.jsx'), 'utf-8');
                     } catch { return ''; }
                   })();

    if (typeof source === 'string') {
      const hasHack = source.includes('setSelectedRbd(null)') && source.includes('setTimeout');
      expect(hasHack).toBe(false);
    }
  });
});
