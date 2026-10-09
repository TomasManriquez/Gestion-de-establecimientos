/**
 * test_FE12_row_actions_and_access.test.jsx
 * ─────────────────────────────────────────
 * Tarea: US-40 · Menú de fila, desactivar/reactivar y diálogo de accesos
 *
 * Verifica que:
 *   - el menú de fila ofrece Editar, Gestionar accesos y Desactivar/Reactivar según el estado
 *   - «Reenviar invitación» y «Restablecer contraseña» están deshabilitadas (dependen de F4)
 *   - nadie puede desactivarse a sí mismo desde la UI
 *   - desactivar pide confirmación, llama POST /disable, avisa y recarga
 *   - reactivar llama POST /enable
 *   - el diálogo de accesos guarda solo diferencias y muestra el 409 dentro del diálogo
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';

vi.mock('axios');

import UsersPage from '@/components/users/UsersPage';
import { ADMIN, apiError, installGets, makeUser, usersListCalls } from './usersFixtures';

const renderPage = (currentUser = ADMIN) =>
  render(<MemoryRouter initialEntries={['/configuracion/usuarios']}><UsersPage currentUser={currentUser} /></MemoryRouter>);

const openMenu = async (user, fullName) => {
  await user.click(screen.getByRole('button', { name: `Acciones de ${fullName}` }));
  return screen.findByRole('menu');
};

beforeEach(() => {
  vi.resetAllMocks();
  installGets();
});

describe('FE12: menú de fila', () => {
  it('FE12-A: usuario activo ofrece Desactivar; inactivo ofrece Reactivar', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    let menu = await openMenu(user, 'Ana Pérez');
    expect(within(menu).getByRole('menuitem', { name: /^Desactivar/ })).toBeInTheDocument();
    expect(within(menu).queryByRole('menuitem', { name: 'Reactivar' })).not.toBeInTheDocument();
    await user.keyboard('{Escape}');
    menu = await openMenu(user, 'Gabriela Ríos');
    expect(within(menu).getByRole('menuitem', { name: 'Reactivar' })).toBeInTheDocument();
    expect(within(menu).queryByRole('menuitem', { name: /^Desactivar/ })).not.toBeInTheDocument();
  });

  it('FE12-B: reenviar invitación y restablecer contraseña están deshabilitadas', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Elena Mora');
    const menu = await openMenu(user, 'Elena Mora');
    expect(within(menu).getByRole('menuitem', { name: /Reenviar invitación/ })).toHaveAttribute('aria-disabled', 'true');
    expect(within(menu).getByRole('menuitem', { name: /Restablecer contraseña/ })).toHaveAttribute('aria-disabled', 'true');
  });

  it('FE12-C: el propio usuario no puede desactivarse', async () => {
    const user = userEvent.setup();
    installGets({ '/api/users': () => ({ items: [makeUser({ _id: ADMIN.id, first_name: 'Administrador', last_name: 'SLEP', email: ADMIN.email })], total: 1, page: 1, page_size: 25, total_pages: 1 }) });
    renderPage();
    await screen.findByText('Administrador SLEP');
    const menu = await openMenu(user, 'Administrador SLEP');
    expect(within(menu).getByRole('menuitem', { name: 'Desactivar (eres tú)' })).toHaveAttribute('aria-disabled', 'true');
  });
});

describe('FE12: desactivar y reactivar', () => {
  it('FE12-D: desactivar pide confirmación, llama /disable y recarga la lista', async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ data: {} });
    renderPage();
    await screen.findByText('Ana Pérez');
    const menu = await openMenu(user, 'Ana Pérez');
    await user.click(within(menu).getByRole('menuitem', { name: 'Desactivar' }));
    const dialog = await screen.findByRole('alertdialog');
    expect(dialog).toHaveTextContent('¿Desactivar a Ana Pérez?');
    expect(axios.post).not.toHaveBeenCalled();
    const before = usersListCalls().length;
    await user.click(within(dialog).getByRole('button', { name: 'Desactivar' }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/users/u1/disable'));
    await waitFor(() => expect(usersListCalls().length).toBeGreaterThan(before));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
  });

  it('FE12-E: «Cancelar» en la confirmación no llama al API', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    await user.click(within(await openMenu(user, 'Ana Pérez')).getByRole('menuitem', { name: 'Desactivar' }));
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Cancelar' }));
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('FE12-F: reactivar llama POST /enable sin confirmación', async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ data: {} });
    renderPage();
    await screen.findByText('Gabriela Ríos');
    await user.click(within(await openMenu(user, 'Gabriela Ríos')).getByRole('menuitem', { name: 'Reactivar' }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/users/u5/enable'));
  });
});

describe('FE12: diálogo de accesos', () => {
  const openAccess = async (user, fullName) => {
    await user.click(within(await openMenu(user, fullName)).getByRole('menuitem', { name: 'Gestionar accesos' }));
    return screen.findByRole('dialog', { name: `Accesos de ${fullName}` });
  };

  it('FE12-G: lista cada plataforma con el rol actual y «Guardar» está deshabilitado sin cambios', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    const dialog = await openAccess(user, 'Ana Pérez');
    expect(within(dialog).getByRole('combobox', { name: 'Rol en Gestión de Establecimientos' })).toHaveTextContent('Editor');
    expect(within(dialog).getByRole('combobox', { name: 'Rol en Administración de usuarios' })).toHaveTextContent('Sin acceso');
    expect(within(dialog).getByRole('button', { name: 'Guardar accesos' })).toBeDisabled();
  });

  it('FE12-H: guarda solo lo que cambió (un PUT para el nuevo, un DELETE para el retirado)', async () => {
    const user = userEvent.setup();
    axios.put.mockResolvedValue({ data: makeUser() });
    axios.delete.mockResolvedValue({ data: makeUser() });
    renderPage();
    await screen.findByText('Ana Pérez');
    const dialog = await openAccess(user, 'Ana Pérez');
    await user.click(within(dialog).getByRole('combobox', { name: 'Rol en Sello Verde' }));
    await user.click(await screen.findByRole('option', { name: 'Viewer' }));
    await user.click(within(dialog).getByRole('combobox', { name: 'Rol en Gestión de Establecimientos' }));
    await user.click(await screen.findByRole('option', { name: 'Sin acceso' }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar accesos' }));
    await waitFor(() => expect(axios.put).toHaveBeenCalledTimes(1));
    expect(axios.put).toHaveBeenCalledWith('/api/users/u1/access/selloverde', { role: 'viewer' });
    expect(axios.delete).toHaveBeenCalledTimes(1);
    expect(axios.delete).toHaveBeenCalledWith('/api/users/u1/access/datos');
  });

  it('FE12-I: el admin de «Administración de usuarios» se llama «Admin global»', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Carla Soto');
    const dialog = await openAccess(user, 'Carla Soto');
    expect(within(dialog).getByRole('combobox', { name: 'Rol en Administración de usuarios' })).toHaveTextContent('Admin global');
  });

  it('FE12-J: un 409 (último admin global) se muestra dentro del diálogo y no lo cierra', async () => {
    const user = userEvent.setup();
    axios.delete.mockRejectedValue(apiError(409, { code: 'last_admin', message: 'No se puede quitar al último administrador global' }));
    renderPage();
    await screen.findByText('Carla Soto');
    const dialog = await openAccess(user, 'Carla Soto');
    await user.click(within(dialog).getByRole('combobox', { name: 'Rol en Administración de usuarios' }));
    await user.click(await screen.findByRole('option', { name: 'Sin acceso' }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar accesos' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('último administrador global');
    expect(screen.getByRole('dialog', { name: 'Accesos de Carla Soto' })).toBeInTheDocument();
  });
});
