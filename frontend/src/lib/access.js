/**
 * access.js — ¿tiene el usuario autenticado un rol permitido en una plataforma?
 * `currentUser.access` viene de GET /api/auth/me: [{platform_id, role}].
 * Es solo experiencia de usuario: el backend es la frontera real (`require_access`).
 */
export function hasAccess(currentUser, platform, roles) {
  const entry = (currentUser?.access ?? []).find((a) => a.platform_id === platform);
  if (!entry) return false;
  return !roles || roles.includes(entry.role);
}

export const isIamAdmin = (currentUser) => hasAccess(currentUser, 'iam', ['admin']);
