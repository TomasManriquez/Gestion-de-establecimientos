/**
 * test_FE21_status_and_cutoffs.test.jsx
 * ─────────────────────────────────────
 * Tarea: estado activo/cerrado del establecimiento y corte de los datos parciales
 *
 * Verifica que:
 *   - cerrar exige el año de cierre antes de guardar, y el PUT lleva estado y año
 *   - la ficha marca «Cerrado en …»
 *   - el corte AAAA-MM se valida y se puede vaciar (año completo)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import { fromInput, buildMetricPayloads, METRIC_FIELDS } from '@/lib/metricFields';

vi.mock('axios');

const EST = {
  rbd: '7722', rbd_full: '7722-3', name: 'LICEO', comuna: 'PUERTO VARAS', area_type: 'URBANO', address: 'Calle 1',
  general_info: { category: '7. LICEO POLITÉCNICO', covertura: '' }, printers: { owned: [], leased: [] }, connectivity: {},
};

const renderEditor = async (est = EST) => {
  const { default: EditFicha } = await import('../../components/EditFicha.jsx');
  render(
    <MemoryRouter initialEntries={[{ pathname: '/establecimientos/7722/editar', state: { initialEst: est, initialCps: [], initialMetrics: [] } }]}>
      <Routes>
        <Route path="/establecimientos/:rbd/editar" element={<EditFicha />} />
        <Route path="/establecimientos/:rbd" element={<div>Ficha</div>} />
      </Routes>
    </MemoryRouter>,
  );
};

beforeEach(() => {
  vi.resetAllMocks();
  axios.put.mockResolvedValue({ data: {} });
});

describe('FE21: estado del establecimiento', () => {
  it('FE21-A: cerrar sin año no guarda', async () => {
    await renderEditor();
    fireEvent.change(await screen.findByLabelText('Estado'), { target: { value: 'closed' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }));
    expect(await screen.findByText('Indica el año de cierre.')).toBeInTheDocument();
    expect(axios.put).not.toHaveBeenCalled();
  });

  it('FE21-B: cerrar con año envía estado y año', async () => {
    await renderEditor();
    fireEvent.change(await screen.findByLabelText('Estado'), { target: { value: 'closed' } });
    fireEvent.change(screen.getByLabelText('Año de cierre'), { target: { value: '2027' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }));
    await waitFor(() => expect(axios.put).toHaveBeenCalledWith('/api/establishments/7722',
      expect.objectContaining({ status: 'closed', closed_year: 2027 })));
  });

  it('FE21-C: un establecimiento activo no manda año de cierre', async () => {
    await renderEditor({ ...EST, status: 'closed', closed_year: 2026 });
    fireEvent.change(await screen.findByLabelText('Estado'), { target: { value: 'active' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }));
    await waitFor(() => expect(axios.put).toHaveBeenCalled());
    const body = axios.put.mock.calls.find(([url]) => url === '/api/establishments/7722')[1];
    expect(body.status).toBe('active');
    expect(body.closed_year).toBeUndefined();
  });

  it('FE21-D: la ficha marca «Cerrado en …»', async () => {
    axios.get.mockImplementation((url) => Promise.resolve({
      data: url.includes('/api/establishments/7722') ? { ...EST, status: 'closed', closed_year: 2026 } : [],
    }));
    const { default: Ficha } = await import('../../components/FichaEstablecimiento.jsx');
    render(
      <MemoryRouter initialEntries={['/establecimientos/7722']}>
        <Routes><Route path="/establecimientos/:rbd" element={<Ficha currentUser={null} />} /></Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText('Cerrado en 2026')).toBeInTheDocument();
  });
});

describe('FE21: corte de datos parciales', () => {
  const asOf = METRIC_FIELDS.find((f) => f.key === 'attendance_as_of');

  it('FE21-E: formato AAAA-MM y vacío permitido', () => {
    expect(fromInput(asOf, '2026-06')).toEqual({ value: '2026-06' });
    expect(fromInput(asOf, '')).toEqual({ value: '' });
    expect(fromInput(asOf, 'junio').error).toMatch(/AAAA-MM/);
    expect(fromInput(asOf, '2026-13').error).toBeTruthy();
  });

  it('FE21-F: vaciar el corte viaja como «año completo»', () => {
    const metrics = [{ year: 2026, attendance_as_of: '2026-06', enrollment_as_of: '2026-03' }];
    const { payloads } = buildMetricPayloads(metrics, { 2026: { attendance_as_of: '', enrollment_as_of: '2026-03' } });
    expect(payloads).toEqual([{ year: 2026, body: { attendance_as_of: '' } }]);
  });
});
