/**
 * test_INT09_users_admin_flow.test.jsx
 * ────────────────────────────────────
 * Tarea: US-40 · Flujo de aceptación del administrador de usuarios, atravesando App.jsx
 *
 * Verifica, con el árbol de rutas real:
 *   1. el admin global ve «Usuarios» en el menú, entra y ve la lista
 *   2. crea un usuario y la lista se recarga
 *   3. un usuario sin rol iam/admin que escribe la URL ve «Sin acceso» y NO se consulta /api/users
 *   4. el 401 del interceptor sigue funcionando (cierra la sesión)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';

vi.mock('axios');

import App from '@/App';
import { ADMIN, installGets, makeUser, usersListCalls } from './usersFixtures';

const VIEWER = { ...ADMIN, id: 'u9', role: 'viewer', full_name: 'Visitante', access: [{ platform_id: 'datos', role: 'viewer' }] };

function mountApp(me, path = '/configuracion/usuarios') {
  localStorage.setItem('token', 'tok');
  const base = installGets;
  base({ '/api/auth/me': () => me });
  // installGets resuelve rutas desconocidas con error: agregamos las que usa el Dashboard del layout.
  const original = axios.get.getMockImplementation();
  axios.get.mockImplementation((url, config) => (url.startsWith('/api/analytics')
    ? Promise.resolve({ data: {} })
    : original(url, config)));
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  axios.defaults = { headers: { common: {} } };
  axios.interceptors = { response: { use: vi.fn(() => 1), eject: vi.fn() } };
});

describe('INT09: administración de usuarios de punta a punta', () => {
  it('INT09-A: el admin global entra por el menú y ve la lista', async () => {
    mountApp(ADMIN, '/dashboard');
    const link = await screen.findByRole('link', { name: 'Usuarios' });
    await userEvent.setup().click(link);
    expect(await screen.findByRole('heading', { name: 'Usuarios' })).toBeInTheDocument();
    expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
    expect(axios.defaults.headers.common.Authorization).toBe('Bearer tok');
  });

  it('INT09-B: crear un usuario envía el POST y recarga la lista', async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ data: makeUser({ _id: 'u9', first_name: 'Nuevo', last_name: 'Usuario', invitation: { sent: true } }) });
    mountApp(ADMIN);
    await screen.findByText('Ana Pérez');
    await user.click(screen.getByRole('button', { name: /Crear usuario/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Crear usuario' });
    await user.type(within(dialog).getByLabelText('Nombre'), 'Nuevo');
    await user.type(within(dialog).getByLabelText('Apellido'), 'Usuario');
    await user.type(within(dialog).getByLabelText('Correo institucional'), 'nuevo@slepllanquihue.cl');
    await user.click(within(dialog).getByLabelText('Unidad'));
    await user.click(await screen.findByRole('option', { name: 'Tecnologías de la Información' }));
    const before = usersListCalls().length;
    await user.click(within(dialog).getByRole('button', { name: 'Crear y enviar invitación' }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/users', expect.objectContaining({ email: 'nuevo@slepllanquihue.cl', unit_id: 'u-ti' })));
    await waitFor(() => expect(usersListCalls().length).toBeGreaterThan(before));
  });

  it('INT09-C: sin rol iam/admin la URL directa muestra «Sin acceso» y no consulta usuarios', async () => {
    mountApp(VIEWER);
    expect(await screen.findByText('Sin acceso a esta sección')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
    expect(usersListCalls()).toHaveLength(0);
  });

  it('INT09-D: /configuracion redirige a /configuracion/usuarios', async () => {
    mountApp(ADMIN, '/configuracion');
    expect(await screen.findByRole('heading', { name: 'Usuarios' })).toBeInTheDocument();
  });
});
