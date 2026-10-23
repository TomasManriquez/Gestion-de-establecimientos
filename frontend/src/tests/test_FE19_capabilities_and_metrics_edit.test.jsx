/**
 * test_FE19_capabilities_and_metrics_edit.test.jsx
 * ────────────────────────────────────────────────
 * Tarea: capacidades por rol en la interfaz y edición de estadísticas desde la ficha
 *
 * Verifica que:
 *   - `can()` lee las capacidades que entrega /me (sin repetir la matriz de roles)
 *   - un viewer no ve «Editar Ficha» ni «Editar estadísticas», y la ruta /editar le muestra «Sin acceso»
 *   - un editor sí ve los botones
 *   - las conversiones de metricFields (porcentajes ↔ proporciones, rangos) y que solo viaja lo cambiado
 *   - guardar la pestaña «Estadísticas» hace un PUT por año con solo los campos cambiados
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import { can } from '@/lib/access';
import { buildMetricPayloads, fromInput, toInput, METRIC_FIELDS } from '@/lib/metricFields';
import RequireAccess from '@/components/RequireAccess';

vi.mock('axios');

const VIEWER = { role: 'viewer', access: [{ platform_id: 'datos', role: 'viewer', capabilities: ['read'] }] };
const EDITOR = { role: 'editor', access: [{ platform_id: 'datos', role: 'editor', capabilities: ['read', 'write'] }] };

const MOCK_ESTABLISHMENT = {
  rbd: '7722', rbd_full: '7722-3', name: 'LICEO POLITÉCNICO PUERTO VARAS',
  comuna: 'PUERTO VARAS', area_type: 'URBANO', address: 'Calle 123',
  general_info: { director: 'Juan Pérez', category: '7. LICEO POLITÉCNICO', adp: 'Si' },
  connectivity: { internet_provider: 'TELSUR', ssid: '', ssid_password: '' },
  printers: { owned: [], leased: [] },
};
const MOCK_METRICS = [
  { _id: 'm0', rbd: '7722', year: 2025, enrollment: 470 },
  { _id: 'm1', rbd: '7722', year: 2026, enrollment: 450, attendance_avg: '0.865', tasa_retencion: 100.3 },
];

const field = (key) => METRIC_FIELDS.find((f) => f.key === key);

beforeEach(() => {
  vi.resetAllMocks();
  axios.get.mockImplementation((url) => {
    if (url.includes('/api/establishments/7722')) return Promise.resolve({ data: MOCK_ESTABLISHMENT });
    if (url.includes('/api/metrics/establishment/7722')) return Promise.resolve({ data: MOCK_METRICS });
    return Promise.resolve({ data: [] });
  });
  axios.put.mockResolvedValue({ data: {} });
});

describe('FE19: capacidades', () => {
  it('FE19-A: can() usa las capacidades de /me y niega lo desconocido', () => {
    expect(can(EDITOR, 'datos', 'write')).toBe(true);
    expect(can(VIEWER, 'datos', 'write')).toBe(false);
    expect(can(VIEWER, 'datos', 'read')).toBe(true);
    expect(can(EDITOR, 'selloverde', 'read')).toBe(false);
    expect(can(null, 'datos', 'read')).toBe(false);
    expect(can({ access: [{ platform_id: 'datos', role: 'editor' }] }, 'datos', 'write')).toBe(false); // sin capabilities: nada
  });

  it('FE19-B: un viewer no ve los botones de edición en la ficha', async () => {
    const { default: Ficha } = await import('../../components/FichaEstablecimiento.jsx');
    render(
      <MemoryRouter initialEntries={['/establecimientos/7722']}>
        <Routes><Route path="/establecimientos/:rbd" element={<Ficha currentUser={VIEWER} />} /></Routes>
      </MemoryRouter>,
    );
    await screen.findByText(/LICEO POLITÉCNICO PUERTO VARAS/i);
    expect(screen.queryByRole('button', { name: /editar ficha/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /estadísticas e historial/i }));
    expect(screen.queryByRole('button', { name: /editar estadísticas/i })).not.toBeInTheDocument();
  });

  it('FE19-C: un editor ve «Editar Ficha» y «Editar estadísticas»', async () => {
    const { default: Ficha } = await import('../../components/FichaEstablecimiento.jsx');
    render(
      <MemoryRouter initialEntries={['/establecimientos/7722']}>
        <Routes><Route path="/establecimientos/:rbd" element={<Ficha currentUser={EDITOR} />} /></Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByRole('button', { name: /editar ficha/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /estadísticas e historial/i }));
    expect(screen.getByRole('button', { name: /editar estadísticas/i })).toBeInTheDocument();
    expect(screen.getByText(/rendimiento \(2026\)/i)).toBeInTheDocument();                     // último año, no fijo
  });

  it('FE19-D: la ruta de edición exige la capacidad write', () => {
    render(
      <MemoryRouter initialEntries={['/establecimientos/7722/editar']}>
        <Routes>
          <Route element={<RequireAccess currentUser={VIEWER} platform="datos" capability="write" message="Solo lectura" />}>
            <Route path="/establecimientos/:rbd/editar" element={<p>Editor</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Sin acceso a esta sección')).toBeInTheDocument();
    expect(screen.getByText('Solo lectura')).toBeInTheDocument();
    expect(screen.queryByText('Editor')).not.toBeInTheDocument();
  });
});

describe('FE19: metricFields', () => {
  it('FE19-E: porcentajes en pantalla, proporciones al guardar', () => {
    expect(toInput(field('attendance_avg'), '0.865')).toBe('86.5');
    expect(fromInput(field('attendance_avg'), '91,2')).toEqual({ value: '0.912' });
    expect(fromInput(field('ive_basica'), '80')).toEqual({ value: 0.8 });
    expect(toInput(field('tasa_retencion'), 0)).toBe('');                                       // 0 = sin dato
    expect(toInput(field('enrollment'), 0)).toBe('0');                                          // matrícula 0 es real
  });

  it('FE19-F: rangos y enteros', () => {
    expect(fromInput(field('enrollment'), '-3').error).toBeTruthy();
    expect(fromInput(field('enrollment'), '12.5').error).toMatch(/entero/);
    expect(fromInput(field('tasa_retencion'), '100.3').error).toMatch(/entre 0 y 100/);
    expect(fromInput(field('grade_avg'), '7.2').error).toBeTruthy();
    expect(fromInput(field('desempeno_media'), 'ALTO')).toEqual({ value: 'ALTO' });
    expect(fromInput(field('enrollment'), '')).toEqual({});
  });

  it('FE19-G: solo viaja lo que cambió, un payload por año', () => {
    const { payloads, errors } = buildMetricPayloads(MOCK_METRICS, {
      2026: { enrollment: '460', attendance_avg: '86.5' },                                     // asistencia sin cambio
      2027: { enrollment: '440' },
      2025: { enrollment: '470' },                                                             // sin cambio: no viaja
    });
    expect(errors).toEqual({});
    expect(payloads).toEqual([{ year: 2026, body: { enrollment: 460 } }, { year: 2027, body: { enrollment: 440 } }]);
  });

  it('FE19-H: un error se reporta por año y campo', () => {
    const { payloads, errors } = buildMetricPayloads(MOCK_METRICS, { 2026: { tasa_promocion: '120' } });
    expect(payloads).toEqual([]);
    expect(errors[2026].tasa_promocion).toBeTruthy();
  });
});

describe('FE19: editar estadísticas en EditFicha', () => {
  const renderEditor = (EditFicha) => render(
    <MemoryRouter initialEntries={[{
      pathname: '/establecimientos/7722/editar',
      state: { initialEst: MOCK_ESTABLISHMENT, initialCps: [], initialMetrics: MOCK_METRICS, initialTab: 'statistics' },
    }]}>
      <Routes>
        <Route path="/establecimientos/:rbd/editar" element={<EditFicha />} />
        <Route path="/establecimientos/:rbd" element={<div>Ficha</div>} />
      </Routes>
    </MemoryRouter>,
  );

  it('FE19-I: cambiar la matrícula 2026 envía solo ese campo a ese año', async () => {
    const { default: EditFicha } = await import('../../components/EditFicha.jsx');
    renderEditor(EditFicha);
    const input = await screen.findByLabelText('Matrícula');
    expect(input).toHaveValue('450');                                                          // abre en el último año
    expect(screen.getByText(/valor cargado fuera de rango/i)).toBeInTheDocument();             // retención 100,3
    fireEvent.change(input, { target: { value: '462' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }));
    await screen.findByText('Ficha');
    expect(axios.put).toHaveBeenCalledWith('/api/metrics/establishment/7722/2026', { enrollment: 462 });
    expect(axios.put).not.toHaveBeenCalledWith(expect.stringContaining('/2025'), expect.anything());
  });

  it('FE19-J: un valor inválido bloquea el guardado completo', async () => {
    const { default: EditFicha } = await import('../../components/EditFicha.jsx');
    renderEditor(EditFicha);
    fireEvent.change(await screen.findByLabelText('Matrícula'), { target: { value: '-5' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/fuera de rango/i);
    expect(axios.put).not.toHaveBeenCalled();                                                  // ni la ficha se escribió
  });

  it('FE19-K: «Agregar año» abre un año vacío y lo guarda', async () => {
    const { default: EditFicha } = await import('../../components/EditFicha.jsx');
    renderEditor(EditFicha);
    fireEvent.click(await screen.findByRole('button', { name: /agregar 2027/i }));
    fireEvent.change(screen.getByLabelText('Matrícula'), { target: { value: '455' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }));
    await waitFor(() => expect(axios.put).toHaveBeenCalledWith('/api/metrics/establishment/7722/2027', { enrollment: 455 }));
  });
});
