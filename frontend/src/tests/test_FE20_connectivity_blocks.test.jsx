/**
 * test_FE20_connectivity_blocks.test.jsx
 * ──────────────────────────────────────
 * Tarea: conectividad en tres bloques (2030, BAM, otro tipo)
 *
 * Verifica que:
 *   - la ficha muestra solo los bloques con datos y avisa «Sin internet» con su motivo
 *   - ya no existe «Antena Starlink instalada»
 *   - el editor muestra los tres bloques siempre y guarda el modelo nuevo
 *   - las reglas compartidas (sin internet, vencido, WhatsApp) coinciden con el backend
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import ConectividadFicha from '@/components/ConectividadFicha';
import { withDefaults, withoutInternet, hasOther, isExpired, whatsappLink } from '@/lib/connectivity';

vi.mock('axios');

const ONLY_2030 = withDefaults({ program_2030: { enabled: true, status: 'fibra_optica', download_speed: '60' }, ssid: 'Liceo' });
const ALL_THREE = withDefaults({
  program_2030: { enabled: true, status: 'microondas', download_speed: '8' },
  bam: [{ carrier: 'Movistar', qty: 15, oc: '1394-AG23', end: '2024-05-31' }],
  other: { provider: 'Enseña Chile', type: 'starlink', expiry_date: '2099-12-01', support_whatsapp: '+56 9 1111 2222' },
});

describe('FE20: reglas de conectividad', () => {
  it('FE20-A: «sin internet» tiene dos causas', () => {
    expect(withoutInternet(ONLY_2030)).toBeNull();
    expect(withoutInternet(withDefaults({ program_2030: { enabled: true, status: 'sin_internet' } }))).toMatch(/2030/);
    expect(withoutInternet(withDefaults({}))).toMatch(/sin 2030, bam ni otro/i);
    expect(withoutInternet(withDefaults({ bam: [{ carrier: 'Entel' }] }))).toBeNull();
  });

  it('FE20-B: otro tipo vacío no cuenta, vencimientos y WhatsApp', () => {
    expect(hasOther(withDefaults({}).other)).toBe(false);
    expect(hasOther({ provider: 'Patagonia IP' })).toBe(true);
    expect(isExpired('2024-05-31', new Date('2026-10-22'))).toBe(true);
    expect(isExpired('2099-01-01', new Date('2026-10-22'))).toBe(false);
    expect(whatsappLink('+56 9 1111 2222')).toBe('https://wa.me/56911112222');
    expect(whatsappLink('')).toBeNull();
  });
});

describe('FE20: ficha', () => {
  it('FE20-C: solo 2030 → sin bloques BAM ni otro tipo, sin aviso', () => {
    render(<ConectividadFicha connectivity={ONLY_2030} />);
    expect(screen.getByText('Conectividad 2030 (Telsur)')).toBeInTheDocument();
    expect(screen.getByText('Fibra óptica')).toBeInTheDocument();
    expect(screen.queryByText(/banda ancha móvil/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/otro tipo de conexión/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Sin internet')).not.toBeInTheDocument();
    expect(screen.queryByText(/antena starlink/i)).not.toBeInTheDocument();
  });

  it('FE20-D: los tres bloques, con vencido y enlace de soporte', () => {
    render(<ConectividadFicha connectivity={ALL_THREE} />);
    expect(screen.getByText(/banda ancha móvil/i)).toBeInTheDocument();
    expect(screen.getByText('15 equipos')).toBeInTheDocument();
    expect(screen.getByText('vencido')).toBeInTheDocument();                       // la BAM de 2024
    expect(screen.getByText('Otro tipo de conexión')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /\+56 9 1111 2222/ })).toHaveAttribute('href', 'https://wa.me/56911112222');
  });

  it('FE20-E: sin ningún bloque → aviso «Sin internet»', () => {
    render(<ConectividadFicha connectivity={withDefaults({})} />);
    expect(screen.getByRole('status')).toHaveTextContent(/sin internet/i);
    expect(screen.queryByText('Conectividad 2030 (Telsur)')).not.toBeInTheDocument();
  });
});

describe('FE20: editor', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    axios.put.mockResolvedValue({ data: {} });
  });

  it('FE20-F: muestra los tres bloques aunque estén vacíos y guarda el modelo nuevo', async () => {
    const { default: EditFicha } = await import('../../components/EditFicha.jsx');
    const est = {
      rbd: '7722', rbd_full: '7722-3', name: 'LICEO', comuna: 'PUERTO VARAS', area_type: 'URBANO', address: 'Calle 1',
      general_info: {}, printers: { owned: [], leased: [] }, connectivity: { program_2030: { enabled: true, status: 'fibra_optica' } },
    };
    render(
      <MemoryRouter initialEntries={[{ pathname: '/establecimientos/7722/editar', state: { initialEst: est, initialCps: [], initialMetrics: [] } }]}>
        <Routes>
          <Route path="/establecimientos/:rbd/editar" element={<EditFicha />} />
          <Route path="/establecimientos/:rbd" element={<div>Ficha</div>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Conectividad' }));
    expect(screen.getByText('Banda ancha móvil (BAM)')).toBeInTheDocument();
    expect(screen.getByText('Otro tipo de conexión')).toBeInTheDocument();
    expect(screen.queryByText(/antena starlink/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Proveedor'), { target: { value: 'Patagonia IP' } });
    fireEvent.change(screen.getByLabelText('Tipo de conexión'), { target: { value: 'fibra_optica' } });
    fireEvent.click(screen.getByRole('button', { name: /agregar bam/i }));
    fireEvent.change(screen.getByLabelText('Operador'), { target: { value: 'Entel' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }));

    await waitFor(() => expect(axios.put).toHaveBeenCalledWith('/api/establishments/7722', expect.anything()));
    const sent = axios.put.mock.calls.find(([url]) => url === '/api/establishments/7722')[1].connectivity;
    expect(sent.program_2030).toMatchObject({ enabled: true, status: 'fibra_optica' });
    expect(sent.other).toMatchObject({ provider: 'Patagonia IP', type: 'fibra_optica' });
    expect(sent.bam).toEqual([expect.objectContaining({ carrier: 'Entel' })]);
    expect(sent).not.toHaveProperty('starlink');
  });
});
