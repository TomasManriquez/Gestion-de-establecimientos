/**
 * format.js — fechas y textos de las pantallas de usuarios.
 */

/** El backend serializa datetimes UTC sin zona ("2026-10-07T12:37:00"): hay que leerlos como UTC. */
export function parseServerDate(value) {
  if (!value) return null;
  const hasZone = /([zZ]|[+-]\d\d:?\d\d)$/.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "hace 2 h", "ayer", "hace 3 d"; "—" si nunca hubo actividad. Compacto para que no ocupe ancho. */
export function formatRelative(value, now = new Date()) {
  const date = parseServerDate(value);
  if (!date) return '—';
  const minutes = Math.floor((now.getTime() - date.getTime()) / 60000);
  if (minutes < 1) return 'ahora';
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'ayer';
  if (days < 7) return `hace ${days} d`;
  if (days < 30) return `hace ${Math.floor(days / 7)} sem`;
  if (days < 365) return `hace ${Math.floor(days / 30)} mes${Math.floor(days / 30) === 1 ? '' : 'es'}`;
  return `hace ${Math.floor(days / 365)} a`;
}

/** Fecha exacta para el tooltip: "7 oct 2026, 10:42". */
export function formatExact(value) {
  const date = parseServerDate(value);
  if (!date) return 'Nunca ha ingresado';
  return date.toLocaleString('es-CL', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export const initialsOf = (user) =>
  `${(user.first_name ?? '')[0] ?? ''}${(user.last_name ?? '')[0] ?? ''}`.toUpperCase() || '?';

export const fullNameOf = (user) => `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();

export const PLATFORM_LABELS = { iam: 'Usuarios', datos: 'Datos', selloverde: 'Sello Verde' };
export const ROLE_LABELS = { admin: 'Admin', editor: 'Editor', viewer: 'Viewer' };

export const POSITION_LABELS = {
  DIRECTOR: 'Director', UTP_JEFE: 'Jefe UTP', PIE_ENCARGADO: 'Encargado PIE',
  CONVIVENCIA_ESCOLAR: 'Convivencia escolar', INSPECTOR_GENERAL: 'Inspector general',
  SIGE_ENCARGADO: 'Encargado SIGE', SECRETARIO: 'Secretario', ADMINISTRADOR: 'Administrador',
  DOCENTE: 'Docente', ASISTENTE_EDUCACION: 'Asistente de la educación',
};

/**
 * Permisos de un usuario como chips ordenados (iam primero). El chip de `iam/admin` se llama
 * "Admin global" para no confundirlo con el admin de `datos`.
 */
export function permissionChips(access = []) {
  const order = { iam: 0, datos: 1, selloverde: 2 };
  return [...access]
    .sort((a, b) => (order[a.platform_id] ?? 9) - (order[b.platform_id] ?? 9))
    .map((a) => ({
      platformId: a.platform_id,
      platform: a.platform_id === 'iam' ? 'Administración de usuarios' : (PLATFORM_LABELS[a.platform_id] ?? a.platform_id),
      role: a.platform_id === 'iam' && a.role === 'admin' ? 'Admin global' : (ROLE_LABELS[a.role] ?? a.role),
      label: a.platform_id === 'iam' && a.role === 'admin'
        ? 'Admin global'
        : `${PLATFORM_LABELS[a.platform_id] ?? a.platform_id} · ${ROLE_LABELS[a.role] ?? a.role}`,
      variant: a.role === 'admin' ? 'default' : a.role === 'editor' ? 'secondary' : 'outline',
    }));
}

/** Estado visible: punto + etiqueta corta + detalle para el tooltip. */
export function statusInfo(user) {
  if (user.status === 'disabled') return { label: 'Inactivo', tone: 'muted', title: 'Usuario desactivado' };
  if (user.status === 'active') return { label: 'Activo', tone: 'success', title: 'Usuario activo' };
  const invitation = user.invitation ?? {};
  if (invitation.sent) return { label: 'Invitado', tone: 'primary', title: 'Invitación enviada: aún no ingresa' };
  if (invitation.last_error === 'mail_not_configured') {
    return { label: 'Sin enviar', tone: 'warning', title: 'La invitación por correo aún no se envía (el correo no está configurado)' };
  }
  return { label: 'Inv. fallida', tone: 'warning', title: `No se pudo enviar la invitación${invitation.last_error ? ` (${invitation.last_error})` : ''}` };
}
