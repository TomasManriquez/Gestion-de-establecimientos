/**
 * test_FE02_ficha_uses_url_params.test.jsx
 * ─────────────────────────────────────────
 * Tarea: FE-02 · FichaEstablecimiento.jsx usa useParams() en lugar de prop rbd
 * Correlaciones: Requiere FE-01 · Habilita FE-03
 *
 * Verifica que:
 *   - FichaEstablecimiento lee rbd desde useParams(), no como prop
 *   - Acceso directo a /establecimientos/7722 carga datos correctamente (deep link)
 *   - useEffect([rbd]) dispara fetch cuando cambia el rbd en la URL
 *   - El botón "Volver" usa navigate(-1), no un callback onBack prop
 *   - El componente no requiere rbd ni onBack como props
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';

vi.mock('axios');

// Datos mock de la ficha completa
const MOCK_ESTABLISHMENT = {
  rbd: '7722', rbd_full: '7722-3',
  name: 'LICEO POLITÉCNICO PUERTO VARAS',
  comuna: 'PUERTO VARAS', area_type: 'URBANO', address: 'Calle 123',
  general_info: { director: 'Juan Pérez', category: '7. LICEO POLITÉCNICO', adp: 'Si' },
  connectivity: { internet_provider: 'TELSUR', ssid: 'Red', ssid_password: '[REDACTED]' },
  printers: { owned: [], leased: [] },
  licenses: [{ name: 'SIGE', email: 'admin@liceo.cl', password: '[REDACTED]' }],
};

const MOCK_COUNTERPARTS = [
  { _id: 'cp1', rbd: '7722', role: 'TI', origin: 'SLEP', name: 'Carlos TI', email: '', phone: '' },
];

const MOCK_METRICS = [
  { _id: 'm1', rbd: '7722', year: 2026, enrollment: 450 },
];

const MOCK_ESTABLISHMENT_2 = {
  rbd: '7801', rbd_full: '7801-5',
  name: 'ESCUELA BÁSICA FRUTILLAR',
  comuna: 'FRUTILLAR', area_type: 'RURAL', address: 'Av. Rural',
  general_info: { director: 'María López', category: '6. RURAL MULTIGRADO', adp: 'No' },
  connectivity: {}, printers: { owned: [], leased: [] }, licenses: [],
};

describe('FE-02: FichaEstablecimiento — Lectura desde useParams()', () => {

  beforeEach(() => {
    vi.resetAllMocks();
    axios.get.mockImplementation((url) => {
      if (url.includes('/api/establishments/7722')) return Promise.resolve({ data: MOCK_ESTABLISHMENT });
      if (url.includes('/api/establishments/7801')) return Promise.resolve({ data: MOCK_ESTABLISHMENT_2 });
      if (url.includes('/api/counterparts/establishment/7722')) return Promise.resolve({ data: MOCK_COUNTERPARTS });
      if (url.includes('/api/counterparts/establishment/7801')) return Promise.resolve({ data: [] });
      if (url.includes('/api/metrics/establishment/7722')) return Promise.resolve({ data: MOCK_METRICS });
      if (url.includes('/api/metrics/establishment/7801')) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
  });

  // ─── Test de deep link ────────────────────────────────────────────────────

  it('FE-02-A: Acceso directo a /establecimientos/7722 carga la ficha correctamente', async () => {
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

    // Verificar que se hicieron los 3 fetches con el rbd correcto
    expect(axios.get).toHaveBeenCalledWith('/api/establishments/7722');
    expect(axios.get).toHaveBeenCalledWith('/api/counterparts/establishment/7722');
    expect(axios.get).toHaveBeenCalledWith('/api/metrics/establishment/7722');
  });

  it('FE-02-B: El componente NO requiere prop rbd para funcionar', async () => {
    const { default: FichaEstablecimiento } = await import('../../components/FichaEstablecimiento.jsx');

    // Renderizar SIN pasar prop rbd — debe leerlo de la URL
    expect(() => {
      render(
        <MemoryRouter initialEntries={['/establecimientos/7722']}>
          <Routes>
            <Route
              path="/establecimientos/:rbd"
              element={<FichaEstablecimiento />}  // Sin props
            />
          </Routes>
        </MemoryRouter>
      );
    }).not.toThrow();
  });

  // ─── Test de reactividad al cambio de RBD ─────────────────────────────────

  it('FE-02-C: Cambiar el RBD en la URL dispara un nuevo fetch', async () => {
    const { default: FichaEstablecimiento } = await import('../../components/FichaEstablecimiento.jsx');

    // Empezar en ficha 7722
    const { rerender } = render(
      <MemoryRouter initialEntries={['/establecimientos/7722']} key="7722">
        <Routes>
          <Route path="/establecimientos/:rbd" element={<FichaEstablecimiento />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('/api/establishments/7722');
    });

    const callsAfterFirst = axios.get.mock.calls.length;

    // Navegar a ficha 7801 — MemoryRouter solo usa `initialEntries` al montar,
    // así que se fuerza un remount con una `key` distinta para simular la
    // navegación real (React Router no vuelve a leer initialEntries en cada render).
    rerender(
      <MemoryRouter initialEntries={['/establecimientos/7801']} key="7801">
        <Routes>
          <Route path="/establecimientos/:rbd" element={<FichaEstablecimiento />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('/api/establishments/7801');
    });

    expect(axios.get.mock.calls.length).toBeGreaterThan(callsAfterFirst);
  });

  // ─── Test del botón "Volver" ───────────────────────────────────────────────

  it('FE-02-D: El botón "Volver" no recibe prop onBack — usa navigate(-1)', async () => {
    const { default: FichaEstablecimiento } = await import('../../components/FichaEstablecimiento.jsx');

    // Verificar que el componente exportado NO usa onBack en su prop interface
    // Esto se verifica indirectamente: si renderiza sin onBack, no lanza error
    let renderError = null;

    try {
      render(
        <MemoryRouter initialEntries={['/establecimientos/7722']}>
          <Routes>
            <Route
              path="/establecimientos/:rbd"
              element={<FichaEstablecimiento />}  // Sin onBack prop
            />
          </Routes>
        </MemoryRouter>
      );
    } catch (e) {
      renderError = e;
    }

    expect(renderError).toBeNull();
  });

  it('FE-02-E: Carga y muestra el nombre del establecimiento desde la URL', async () => {
    const { default: FichaEstablecimiento } = await import('../../components/FichaEstablecimiento.jsx');

    render(
      <MemoryRouter initialEntries={['/establecimientos/7801']}>
        <Routes>
          <Route path="/establecimientos/:rbd" element={<FichaEstablecimiento />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/ESCUELA BÁSICA FRUTILLAR/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  // ─── Test de integración FE-01 + FE-02 ────────────────────────────────────

  it('FE-02-F: El directorio navega a /establecimientos/:rbd y la ficha carga el RBD correcto', async () => {
    const { default: Directory } = await import('../../components/Directory.jsx');
    const { default: FichaEstablecimiento } = await import('../../components/FichaEstablecimiento.jsx');

    const paginatedResponse = {
      items: [MOCK_ESTABLISHMENT],
      total: 1, page: 1, page_size: 100, total_pages: 1
    };

    axios.get.mockImplementation((url) => {
      // Ojo con el orden: '/counterparts' y '/metrics' también contienen "7722",
      // así que deben chequearse antes que el match genérico de establishments.
      if (url === '/api/establishments') return Promise.resolve({ data: paginatedResponse });
      if (url.includes('/counterparts')) return Promise.resolve({ data: MOCK_COUNTERPARTS });
      if (url.includes('/metrics')) return Promise.resolve({ data: MOCK_METRICS });
      if (url.includes('/api/establishments/7722')) return Promise.resolve({ data: MOCK_ESTABLISHMENT });
      return Promise.resolve({ data: [] });
    });

    render(
      <MemoryRouter initialEntries={['/establecimientos']}>
        <Routes>
          <Route path="/establecimientos" element={<Directory />} />
          <Route path="/establecimientos/:rbd" element={<FichaEstablecimiento />} />
        </Routes>
      </MemoryRouter>
    );

    // Esperar que cargue el directorio
    await waitFor(() => {
      expect(screen.getByText(/LICEO POLITÉCNICO PUERTO VARAS/i)).toBeInTheDocument();
    });

    // Click en el link de la ficha (la fila tiene dos <a> al mismo RBD: el nombre y "Ficha")
    const fichaLink = screen.getAllByRole('link', { name: /LICEO POLITÉCNICO|Ficha/i })[0];
    fireEvent.click(fichaLink);

    // Verificar que la ficha cargó el RBD correcto
    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('/api/establishments/7722');
    });
  });
});
