/**
 * test_FE26_vault_tab.test.jsx — ADR-021, fase 2: pestaña Bóveda de la ficha y pantalla de accesos.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import FichaEstablecimiento from '@/components/FichaEstablecimiento';
import AccessGrantsPage from '@/components/access/AccessGrantsPage';

vi.mock('axios');

const EST = { rbd: '7722', rbd_full: '7722-3', name: 'LICEO PV', comuna: 'PUERTO VARAS', area_type: 'URBANO', address: 'x',
  general_info: { director: 'Juan' }, connectivity: {}, printers: { owned: [], leased: [] } };
const CRED = { _id: 'c1', rbd: '7722', name: 'SIGE', username: 'director', url: 'https://sige.mineduc.cl', has_password: true };

const mockApi = ({ vault, reveal }) => {
  axios.get.mockImplementation((url) => {
    if (url === '/api/v1/establishments/7722/vault') return vault();
    if (url === '/api/establishments/7722') return Promise.resolve({ data: EST });
    return Promise.resolve({ data: [] });
  });
  axios.post.mockImplementation((url) => (url.endsWith('/reveal') ? reveal() : Promise.reject(new Error('inesperado'))));
};

const renderFicha = () => render(
  <MemoryRouter initialEntries={['/establecimientos/7722']}>
    <Routes><Route path="/establecimientos/:rbd" element={<FichaEstablecimiento currentUser={{ access: [] }} />} /></Routes>
  </MemoryRouter>,
);

describe('FE26: bóveda en la ficha', () => {
  beforeEach(() => { vi.resetAllMocks(); });

  it('FE26-A: con 403 la pestaña no existe', async () => {
    mockApi({ vault: () => Promise.reject({ response: { status: 403 } }) });
    renderFicha();
    await screen.findByText('LICEO PV');
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/v1/establishments/7722/vault'));
    expect(screen.queryByRole('button', { name: 'Bóveda' })).toBeNull();
  });

  it('FE26-B: con 200 aparece, la lista no trae contraseña y «Mostrar» la pide al servidor', async () => {
    mockApi({ vault: () => Promise.resolve({ data: [CRED] }), reveal: () => Promise.resolve({ data: { password: 'Clave-Secreta-1' } }) });
    renderFicha();
    fireEvent.click(await screen.findByRole('button', { name: 'Bóveda' }));
    await screen.findByText('SIGE');
    expect(screen.queryByText('Clave-Secreta-1')).toBeNull();
    expect(axios.post).not.toHaveBeenCalled();                      // abrir la pestaña no revela nada
    fireEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña de SIGE' }));
    expect(await screen.findByText('Clave-Secreta-1')).toBeTruthy();
    expect(axios.post).toHaveBeenCalledWith('/api/v1/establishments/7722/vault/c1/reveal');
    fireEvent.click(screen.getByRole('button', { name: 'Ocultar contraseña de SIGE' }));
    expect(screen.queryByText('Clave-Secreta-1')).toBeNull();
  });

  it('FE26-C: un 429 muestra el límite de revelaciones y no la contraseña', async () => {
    const err = { response: { status: 429, headers: { 'retry-after': '1800' }, data: { detail: { code: 'rate_limited', message: 'x' } } } };
    mockApi({ vault: () => Promise.resolve({ data: [CRED] }), reveal: () => Promise.reject(err) });
    const { toast } = await import('sonner');
    const spy = vi.spyOn(toast, 'error').mockImplementation(() => {});
    renderFicha();
    fireEvent.click(await screen.findByRole('button', { name: 'Bóveda' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mostrar contraseña de SIGE' }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith('Alcanzaste el límite de revelaciones; vuelve en 30 min.'));
  });
});

describe('FE26: pantalla de accesos', () => {
  beforeEach(() => { vi.resetAllMocks(); });

  it('FE26-D: lista las concesiones con nombre de persona y establecimiento, y revoca con confirmación', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/v1/access/grants') return Promise.resolve({ data: [{ _id: 'g1', resource_type: 'vault', resource_id: '7722', subject_id: 'u1' }] });
      if (url === '/api/users/u1') return Promise.resolve({ data: { _id: 'u1', first_name: 'Vera', last_name: 'Lectura', email: 'v@slepllanquihue.cl' } });
      if (url === '/api/establishments') return Promise.resolve({ data: { items: [{ rbd: '7722', name: 'LICEO PV', comuna: 'PV' }] } });
      return Promise.resolve({ data: [] });
    });
    axios.delete.mockResolvedValue({});
    render(<MemoryRouter><AccessGrantsPage /></MemoryRouter>);
    await screen.findByText('Vera Lectura');
    await screen.findByText('Bóveda · LICEO PV · RBD 7722');
    fireEvent.click(screen.getByRole('button', { name: /Revocar acceso de Vera Lectura/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Revocar' }));
    await waitFor(() => expect(axios.delete).toHaveBeenCalledWith('/api/v1/access/grants/g1'));
  });
});
