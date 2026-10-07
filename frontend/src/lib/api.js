/**
 * api.js — cliente API único de las pantallas de gestión de usuarios (ADR-008).
 *
 * Usa el `axios` global a propósito: así hereda la cabecera `Authorization` que instala
 * `App.jsx` y su interceptor de 401. No crea otra instancia ni toca el token.
 * Todas las rutas son relativas (`/api/...`): el proxy de Vite o el de Nginx las resuelve.
 * Los componentes antiguos siguen llamando a `axios` directo (D19); no se migran aquí.
 */
import axios from 'axios';

const data = (response) => response.data;

export const usersApi = {
  list: (params, signal) => axios.get('/api/users', { params, signal }).then(data),
  get: (id) => axios.get(`/api/users/${id}`).then(data),
  create: (body) => axios.post('/api/users', body).then(data),
  update: (id, body) => axios.patch(`/api/users/${id}`, body).then(data),
  disable: (id) => axios.post(`/api/users/${id}/disable`).then(data),
  enable: (id) => axios.post(`/api/users/${id}/enable`).then(data),
  grantAccess: (id, platformId, role) => axios.put(`/api/users/${id}/access/${platformId}`, { role }).then(data),
  revokeAccess: (id, platformId) => axios.delete(`/api/users/${id}/access/${platformId}`).then(data),
};

export const unitsApi = {
  list: (params) => axios.get('/api/units', { params }).then(data),
  tree: () => axios.get('/api/units/tree').then(data),
};

export const platformsApi = {
  list: () => axios.get('/api/platforms').then(data),
};

export const establishmentsApi = {
  /** Directorio completo (78 registros, sin campos sensibles) para resolver rbd → nombre. */
  all: () => axios.get('/api/establishments', { params: { page_size: 200 } }).then((r) => r.data.items),
};

/**
 * Normaliza un error de axios al formato que usan los formularios.
 *   - 409 del backend:   detail = {code, message, field}
 *   - 422 del service:   detail = [{field, code, message}]
 *   - 422 de Pydantic:   detail = [{loc: ['body', 'email'], msg, type}]
 *   - 403 / 404 / red:   mensaje genérico
 * Devuelve {status, message, fields: {campo: mensaje}}.
 */
export function parseApiError(error) {
  const status = error?.response?.status ?? 0;
  const detail = error?.response?.data?.detail;
  const fields = {};
  let message = '';

  if (status === 0) {
    message = 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.';
  } else if (status === 403) {
    message = 'No tienes permiso para realizar esta acción.';
  } else if (status === 404) {
    message = typeof detail === 'string' ? detail : 'No se encontró el recurso solicitado.';
  } else if (Array.isArray(detail)) {
    for (const item of detail) {
      const field = item.field ?? (Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null);
      const text = item.message ?? item.msg ?? 'Valor no válido';
      if (field && field !== '_' && typeof field === 'string') {
        if (!fields[field]) fields[field] = text;
      } else if (!message) {
        message = text;
      }
    }
    if (!message && Object.keys(fields).length === 0) message = 'Los datos enviados no son válidos.';
  } else if (detail && typeof detail === 'object') {
    message = detail.message ?? 'No se pudo completar la acción.';
    if (detail.field) fields[detail.field] = message;
  } else if (typeof detail === 'string') {
    message = detail;
  } else {
    message = 'Ocurrió un error inesperado.';
  }
  return { status, message, fields, code: detail && !Array.isArray(detail) && typeof detail === 'object' ? detail.code : undefined };
}
