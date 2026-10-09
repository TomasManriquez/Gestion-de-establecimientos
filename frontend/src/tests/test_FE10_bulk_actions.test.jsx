/**
 * test_FE10_bulk_actions.test.jsx
 * ───────────────────────────────
 * Tarea: US-40 · Selección múltiple y acciones masivas (cliente, hasta que exista POST /api/users/bulk)
 *
 * Verifica que:
 *   - la barra de selección aparece con el conteo y desaparece al cancelar
 *   - «seleccionar todos» marca solo la página; la selección se limpia al cambiar de filtro
 *   - desactivar pide confirmación y llama POST /disable por cada usuario, en orden
 *   - una falla por persona (409 último admin) se informa por nombre sin detener a las demás
 *   - dar/quitar acceso y asignar unidad llaman el endpoint individual correcto
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';

vi.mock('axios');

import UsersPage from '@/components/users/UsersPage';
import { ADMIN, apiError, installGets, makeUser } from './usersFixtures';

const renderPage = (entry = '/configuracion/usuarios') =>
  render(<MemoryRouter initialEntries={[entry]}><UsersPage currentUser={ADMIN} /></MemoryRouter>);

async function select(user, ...names) {
  for (const n of names) await user.click(screen.getByRole('checkbox', { name: `Seleccionar a ${n}` }));
}

beforeEach(() => {
  vi.resetAllMocks();
  installGets();
});

describe('FE10: selección', () => {
  it('FE10-A: sin selección no hay barra; con 1 y con 2 muestra el conteo', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    await select(user, 'Ana Pérez');
    expect(screen.getByRole('status')).toHaveTextContent('1 usuario seleccionado');
    await select(user, 'Carla Soto');
    expect(screen.getByRole('status')).toHaveTextContent('2 usuarios seleccionados');
  });

  it('FE10-B: «Cancelar selección» limpia las casillas y oculta la barra', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    await select(user, 'Ana Pérez');
    await user.click(screen.getByRole('button', { name: 'Cancelar selección' }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Seleccionar a Ana Pérez' })).not.toBeChecked();
  });

  it('FE10-C: el checkbox de cabecera marca toda la página (y vuelve a desmarcar)', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    const all = screen.getByRole('checkbox', { name: 'Seleccionar todos los usuarios de esta página' });
    await user.click(all);
    expect(screen.getByRole('status')).toHaveTextContent('5 usuarios seleccionados');
    await user.click(all);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('FE10-D: cambiar de filtro limpia la selección', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    await select(user, 'Ana Pérez');
    await user.click(screen.getByRole('combobox', { name: 'Estado' }));
    await user.click(await screen.findByRole('option', { name: 'Activo' }));
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  });
});

describe('FE10: acciones masivas', () => {
  it('FE10-E: desactivar pide confirmación y llama /disable por cada seleccionado, en orden', async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ data: {} });
    renderPage();
    await screen.findByText('Ana Pérez');
    await select(user, 'Ana Pérez', 'Carla Soto');
    await user.click(within(screen.getByRole('status')).getByRole('button', { name: 'Desactivar' }));
    const dialog = await screen.findByRole('alertdialog');
    expect(dialog).toHaveTextContent('¿Desactivar a 2 usuarios?');
    expect(axios.post).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole('button', { name: 'Desactivar' }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(2));
    expect(axios.post.mock.calls.map((c) => c[0])).toEqual(['/api/users/u1/disable', '/api/users/u2/disable']);
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
  });

  it('FE10-F: una falla (último admin global) se informa por nombre y no frena a los demás', async () => {
    const user = userEvent.setup();
    axios.post.mockImplementation((url) => (url === '/api/users/u2/disable'
      ? Promise.reject(apiError(409, { code: 'last_admin', message: 'No se puede dejar al sistema sin administrador global' }))
      : Promise.resolve({ data: {} })));
    renderPage();
    await screen.findByText('Ana Pérez');
    await select(user, 'Ana Pérez', 'Carla Soto', 'Darío Vera');
    await user.click(within(screen.getByRole('status')).getByRole('button', { name: 'Desactivar' }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Desactivar' }));
    expect(await within(dialog).findByText('1 de 3 no se pudieron procesar')).toBeInTheDocument();
    expect(within(dialog).getByText(/Carla Soto:/)).toBeInTheDocument();
    expect(within(dialog).getByText(/No se puede dejar al sistema sin administrador global/)).toBeInTheDocument();
    expect(axios.post).toHaveBeenCalledTimes(3);
  });

  it('FE10-G: dar acceso exige plataforma y rol, y llama PUT /access/{plataforma} por usuario', async () => {
    const user = userEvent.setup();
    axios.put.mockResolvedValue({ data: {} });
    renderPage();
    await screen.findByText('Ana Pérez');
    await select(user, 'Ana Pérez', 'Darío Vera');
    await user.click(within(screen.getByRole('status')).getByRole('button', { name: 'Dar acceso' }));
    const dialog = await screen.findByRole('dialog', { name: 'Dar acceso' });
    const submit = within(dialog).getByRole('button', { name: 'Dar acceso' });
    expect(submit).toBeDisabled();
    await user.click(within(dialog).getByRole('combobox', { name: 'Plataforma' }));
    await user.click(await screen.findByRole('option', { name: 'Sello Verde' }));
    expect(submit).toBeDisabled();
    await user.click(within(dialog).getByRole('combobox', { name: 'Rol' }));
    await user.click(await screen.findByRole('option', { name: 'Viewer' }));
    await user.click(submit);
    await waitFor(() => expect(axios.put).toHaveBeenCalledTimes(2));
    expect(axios.put.mock.calls).toEqual([
      ['/api/users/u1/access/selloverde', { role: 'viewer' }],
      ['/api/users/u3/access/selloverde', { role: 'viewer' }],
    ]);
  });

  it('FE10-H: quitar acceso llama DELETE por usuario (no pide rol)', async () => {
    const user = userEvent.setup();
    axios.delete.mockResolvedValue({ data: {} });
    renderPage();
    await screen.findByText('Ana Pérez');
    await select(user, 'Ana Pérez');
    await user.click(within(screen.getByRole('status')).getByRole('button', { name: 'Quitar acceso' }));
    const dialog = await screen.findByRole('dialog', { name: 'Quitar acceso' });
    expect(within(dialog).queryByRole('combobox', { name: 'Rol' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('combobox', { name: 'Plataforma' }));
    await user.click(await screen.findByRole('option', { name: 'Gestión de Establecimientos' }));
    await user.click(within(dialog).getByRole('button', { name: 'Quitar acceso' }));
    await waitFor(() => expect(axios.delete).toHaveBeenCalledWith('/api/users/u1/access/datos'));
  });

  it('FE10-I: asignar unidad hace PATCH {unit_id} por usuario', async () => {
    const user = userEvent.setup();
    axios.patch.mockResolvedValue({ data: makeUser() });
    renderPage();
    await screen.findByText('Ana Pérez');
    await select(user, 'Ana Pérez', 'Carla Soto');
    await user.click(within(screen.getByRole('status')).getByRole('button', { name: 'Asignar unidad' }));
    const dialog = await screen.findByRole('dialog', { name: 'Asignar unidad' });
    expect(within(dialog).getByRole('button', { name: 'Asignar unidad' })).toBeDisabled();
    await user.click(within(dialog).getByRole('combobox', { name: 'Unidad' }));
    await user.click(await screen.findByRole('option', { name: 'Dirección Ejecutiva' }));
    await user.click(within(dialog).getByRole('button', { name: 'Asignar unidad' }));
    await waitFor(() => expect(axios.patch).toHaveBeenCalledTimes(2));
    expect(axios.patch.mock.calls).toEqual([
      ['/api/users/u1', { unit_id: 'u-de' }],
      ['/api/users/u2', { unit_id: 'u-de' }],
    ]);
  });
});
