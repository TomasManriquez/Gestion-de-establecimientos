/**
 * usersFixtures.js — datos y simulación de la API para las pruebas de la vista de usuarios.
 * (No es un test: el include de vitest solo toma *.test.jsx.)
 */
import axios from 'axios';
import { vi } from 'vitest';

export const UNITS = [
  { _id: 'u-de', code: 'DE', name: 'Dirección Ejecutiva', level: 1, parent_id: null, ancestors: [], order: 1, status: 'active' },
  { _id: 'u-af', code: 'SD-AF', name: 'Subdirección de Administración y Finanzas', level: 3, parent_id: 'u-de', ancestors: ['u-de'], order: 6, status: 'active' },
  { _id: 'u-ti', code: 'AF-TI', name: 'Tecnologías de la Información', level: 4, parent_id: 'u-af', ancestors: ['u-de', 'u-af'], order: 2, status: 'active' },
];

export const PLATFORMS = [
  { _id: 'datos', name: 'Gestión de Establecimientos', roles: ['admin', 'editor', 'viewer'], status: 'active' },
  { _id: 'iam', name: 'Administración de usuarios', roles: ['admin'], status: 'active' },
  { _id: 'selloverde', name: 'Sello Verde', roles: ['admin', 'editor', 'viewer'], status: 'active' },
];

export const ESTABLISHMENTS = [
  { rbd: '7722', name: 'LICEO LOS ALERCES', comuna: 'PUERTO VARAS' },
  { rbd: '7801', name: 'ESCUELA RURAL EL ROBLE', comuna: 'FRUTILLAR' },
];

export const ADMIN = {
  id: 'u-admin', username: 'admin@slepllanquihue.cl', full_name: 'Administrador SLEP', role: 'admin',
  email: 'admin@slepllanquihue.cl',
  access: [{ platform_id: 'iam', role: 'admin' }, { platform_id: 'datos', role: 'admin' }],
};

export function makeUser(overrides = {}) {
  return {
    _id: 'u1', email: 'ana.perez@slepllanquihue.cl', first_name: 'Ana', last_name: 'Pérez', work_extension: '4521',
    is_slep_staff: true, unit_id: 'u-ti', rbd: null, positions: [], status: 'active',
    access: [{ platform_id: 'datos', role: 'editor', granted_at: null, granted_by: null }],
    invitation: null, last_login_at: null, last_activity_at: '2026-10-07T10:42:00', ...overrides,
  };
}

export const ANA = makeUser();
export const CARLA = makeUser({
  _id: 'u2', email: 'carla.soto@slepllanquihue.cl', first_name: 'Carla', last_name: 'Soto', unit_id: 'u-de',
  access: [
    { platform_id: 'datos', role: 'admin' }, { platform_id: 'iam', role: 'admin' }, { platform_id: 'selloverde', role: 'editor' },
  ],
});
export const DARIO = makeUser({
  _id: 'u3', email: 'dario.vera@slepllanquihue.cl', first_name: 'Darío', last_name: 'Vera', is_slep_staff: false, unit_id: null,
  rbd: '7801', positions: ['DOCENTE', 'PIE_ENCARGADO'], access: [{ platform_id: 'datos', role: 'viewer' }],
  last_activity_at: null, personal_phone: '+56999999999',
});
export const ELENA = makeUser({
  _id: 'u4', email: 'elena.mora@slepllanquihue.cl', first_name: 'Elena', last_name: 'Mora', status: 'invited', access: [],
  last_activity_at: null,
  invitation: { sent_at: null, expires_at: null, last_error: 'mail_not_configured', sent: false },
});
export const GABRIELA = makeUser({
  _id: 'u5', email: 'gabriela.rios@slepllanquihue.cl', first_name: 'Gabriela', last_name: 'Ríos', status: 'disabled',
  last_activity_at: '2026-08-04T09:10:00',
});
export const USERS = [ANA, CARLA, DARIO, ELENA, GABRIELA];

export const page = (items, extra = {}) => ({ items, total: items.length, page: 1, page_size: 25, total_pages: 1, ...extra });

/**
 * Instala un enrutador de GET sobre el `axios` mockeado (vi.mock('axios') en el test).
 * `overrides` permite sustituir la respuesta de una ruta por una función (url, config) => data | Promise.
 */
export function installGets(overrides = {}) {
  axios.get.mockImplementation((url, config) => {
    if (overrides[url]) return Promise.resolve().then(() => overrides[url](url, config)).then((data) => ({ data }));
    if (url === '/api/users') return Promise.resolve({ data: page(USERS) });
    if (url === '/api/units') return Promise.resolve({ data: UNITS });
    if (url === '/api/platforms') return Promise.resolve({ data: PLATFORMS });
    if (url === '/api/establishments') return Promise.resolve({ data: page(ESTABLISHMENTS) });
    return Promise.reject(new Error(`GET sin simular: ${url}`));
  });
}

export const apiError = (status, detail) => Object.assign(new Error(`HTTP ${status}`), { response: { status, data: { detail } } });

export const usersListCalls = () => axios.get.mock.calls.filter(([url]) => url === '/api/users');
