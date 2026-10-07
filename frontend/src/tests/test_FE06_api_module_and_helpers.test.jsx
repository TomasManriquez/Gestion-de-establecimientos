/**
 * test_FE06_api_module_and_helpers.test.jsx
 * ─────────────────────────────────────────
 * Tarea: US-40 · Cliente API único `lib/api.js` (ADR-008) y helpers de la vista de usuarios
 *
 * Verifica que:
 *   - las rutas son relativas (/api/...) y usan el axios global (hereda token e interceptor 401)
 *   - parseApiError normaliza cada forma de error del backend (409 con campo, 422 de service,
 *     422 de Pydantic, 403, 404, red) para que el formulario marque el campo correcto
 *   - las fechas del servidor (UTC sin zona) se interpretan como UTC
 *   - ningún componente nuevo importa axios directamente
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import axios from 'axios';

vi.mock('axios');

import { usersApi, unitsApi, platformsApi, establishmentsApi, parseApiError } from '@/lib/api';
import { formatRelative, formatExact, parseServerDate, permissionChips, statusInfo } from '@/lib/format';
import { hasAccess, isIamAdmin } from '@/lib/access';
import { orderUnits } from '@/lib/units';

beforeEach(() => {
  vi.resetAllMocks();
  for (const m of ['get', 'post', 'put', 'patch', 'delete']) axios[m].mockResolvedValue({ data: { ok: true, items: [] } });
});

describe('FE06: lib/api.js — rutas relativas sobre el axios global', () => {
  it('FE06-A: cada función llama una ruta relativa /api/...', async () => {
    await usersApi.list({ page: 2 });
    await usersApi.get('u1');
    await usersApi.create({ a: 1 });
    await usersApi.update('u1', { b: 2 });
    await usersApi.disable('u1');
    await usersApi.enable('u1');
    await usersApi.grantAccess('u1', 'datos', 'editor');
    await usersApi.revokeAccess('u1', 'datos');
    await unitsApi.list();
    await unitsApi.tree();
    await platformsApi.list();
    await establishmentsApi.all();
    const urls = [...axios.get.mock.calls, ...axios.post.mock.calls, ...axios.put.mock.calls, ...axios.patch.mock.calls, ...axios.delete.mock.calls].map((c) => c[0]);
    expect(urls.length).toBe(12);
    for (const url of urls) expect(url).toMatch(/^\/api\//);
  });

  it('FE06-B: list pasa los parámetros y la señal de cancelación', async () => {
    const controller = new AbortController();
    await usersApi.list({ q: 'ana', page: 3 }, controller.signal);
    expect(axios.get).toHaveBeenCalledWith('/api/users', { params: { q: 'ana', page: 3 }, signal: controller.signal });
  });

  it('FE06-C: grantAccess envía solo {role}; revokeAccess usa DELETE', async () => {
    await usersApi.grantAccess('u1', 'iam', 'admin');
    expect(axios.put).toHaveBeenCalledWith('/api/users/u1/access/iam', { role: 'admin' });
    await usersApi.revokeAccess('u1', 'iam');
    expect(axios.delete).toHaveBeenCalledWith('/api/users/u1/access/iam');
  });

  it('FE06-D: el módulo no crea otra instancia de axios ni toca el token', () => {
    const raw = readFileSync(join(process.cwd(), 'src/lib/api.js'), 'utf-8');
    const src = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, ''); // sin comentarios
    expect(src).not.toMatch(/axios\.create/);
    expect(src).not.toMatch(/localStorage|Authorization/);
  });
});

describe('FE06: parseApiError', () => {
  const err = (status, detail) => ({ response: { status, data: { detail } } });

  it('FE06-E: 409 con {code, message, field} marca ese campo', () => {
    const r = parseApiError(err(409, { code: 'duplicate', message: 'Ya existe un usuario con ese correo', field: 'email' }));
    expect(r.status).toBe(409);
    expect(r.fields).toEqual({ email: 'Ya existe un usuario con ese correo' });
    expect(r.code).toBe('duplicate');
  });

  it('FE06-F: 422 del service ([{field, code, message}]) y de Pydantic ([{loc, msg}])', () => {
    expect(parseApiError(err(422, [{ field: 'unit_id', code: 'unit_not_found', message: 'La unidad no existe o está inactiva' }])).fields)
      .toEqual({ unit_id: 'La unidad no existe o está inactiva' });
    expect(parseApiError(err(422, [{ type: 'value_error', loc: ['body', 'personal_phone'], msg: 'Formato inválido' }])).fields)
      .toEqual({ personal_phone: 'Formato inválido' });
  });

  it('FE06-G: un error sin campo (campo "_") queda como mensaje general', () => {
    const r = parseApiError(err(422, [{ field: '_', code: 'invalid_combination', message: 'Un funcionario SLEP debe tener unit_id' }]));
    expect(r.fields).toEqual({});
    expect(r.message).toBe('Un funcionario SLEP debe tener unit_id');
  });

  it('FE06-H: 403, 404 y error de red dan un mensaje legible', () => {
    expect(parseApiError(err(403, 'Insufficient permissions')).message).toMatch(/No tienes permiso/);
    expect(parseApiError(err(404, 'User x not found')).message).toBe('User x not found');
    expect(parseApiError({}).message).toMatch(/No se pudo conectar/);
  });
});

describe('FE06: helpers de formato y acceso', () => {
  it('FE06-I: las fechas sin zona del servidor se leen como UTC', () => {
    expect(parseServerDate('2026-10-07T10:00:00').toISOString()).toBe('2026-10-07T10:00:00.000Z');
    expect(parseServerDate('2026-10-07T10:00:00Z').toISOString()).toBe('2026-10-07T10:00:00.000Z');
    expect(parseServerDate(null)).toBeNull();
    const now = new Date('2026-10-07T12:00:00Z');
    expect(formatRelative('2026-10-07T10:00:00', now)).toBe('hace 2 h');
    expect(formatRelative('2026-10-07T11:56:00', now)).toBe('hace 4 min');
    expect(formatRelative('2026-10-06T10:00:00', now)).toBe('ayer');
    expect(formatRelative('2026-10-03T12:00:00', now)).toBe('hace 4 d');
    expect(formatRelative('2026-08-04T09:10:00', now)).toBe('hace 2 meses');
    expect(formatRelative(null, now)).toBe('—');
    expect(formatExact(null)).toBe('Nunca ha ingresado');
    expect(formatExact('2026-10-07T10:42:00')).toMatch(/2026/);
  });

  it('FE06-J: permissionChips ordena iam primero y llama «Admin global» al admin de iam', () => {
    const chips = permissionChips([
      { platform_id: 'selloverde', role: 'viewer' }, { platform_id: 'datos', role: 'editor' }, { platform_id: 'iam', role: 'admin' },
    ]);
    expect(chips.map((c) => c.label)).toEqual(['Admin global', 'Datos · Editor', 'Sello Verde · Viewer']);
  });

  it('FE06-K: statusInfo distingue activo, sin enviar, invitado, fallida e inactivo', () => {
    expect(statusInfo({ status: 'active' }).tone).toBe('success');
    expect(statusInfo({ status: 'disabled' }).label).toBe('Inactivo');
    expect(statusInfo({ status: 'invited', invitation: { sent: true } }).label).toBe('Invitado');
    expect(statusInfo({ status: 'invited', invitation: { sent: false, last_error: 'mail_not_configured' } }).label).toBe('Sin enviar');
    expect(statusInfo({ status: 'invited', invitation: { sent: false, last_error: 'smtp_down' } }).label).toBe('Inv. fallida');
  });

  it('FE06-L: hasAccess / isIamAdmin leen currentUser.access', () => {
    const user = { access: [{ platform_id: 'iam', role: 'admin' }, { platform_id: 'datos', role: 'viewer' }] };
    expect(isIamAdmin(user)).toBe(true);
    expect(hasAccess(user, 'datos', ['admin', 'editor'])).toBe(false);
    expect(hasAccess(user, 'datos')).toBe(true);
    expect(hasAccess({}, 'iam')).toBe(false);
    expect(hasAccess(null, 'iam')).toBe(false);
  });

  it('FE06-M: orderUnits entrega padre antes que hijas con su profundidad', () => {
    const flat = [
      { _id: 'c', name: 'Hija', parent_id: 'b', order: 1 }, { _id: 'a', name: 'Raíz', parent_id: null, order: 1 },
      { _id: 'b', name: 'Media', parent_id: 'a', order: 1 },
    ];
    expect(orderUnits(flat).map((u) => [u._id, u.depth])).toEqual([['a', 0], ['b', 1], ['c', 2]]);
  });
});

describe('FE06: los componentes nuevos no importan axios directamente', () => {
  const dir = join(process.cwd(), 'src/components/users');
  const files = [...readdirSync(dir).filter((f) => f.endsWith('.jsx')).map((f) => join(dir, f)),
    join(process.cwd(), 'src/components/RequireAccess.jsx')];
  it.each(files)('FE06-N: %s', (file) => {
    expect(readFileSync(file, 'utf-8')).not.toMatch(/from ['"]axios['"]/);
  });
});
