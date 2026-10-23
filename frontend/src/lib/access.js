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

/**
 * ¿Puede el usuario `capability` ('read' | 'write' | 'delete') en la plataforma? Las capacidades
 * las calcula el backend a partir del rol (ROLE_CAPABILITIES) y llegan una sola vez en /me, así que
 * ninguna vista repite la matriz de roles. Solo decide qué se muestra: el backend vuelve a exigirlas.
 */
export function can(currentUser, platform, capability) {
  const entry = (currentUser?.access ?? []).find((a) => a.platform_id === platform);
  return Boolean(entry?.capabilities?.includes(capability));
}

export const isIamAdmin = (currentUser) => hasAccess(currentUser, 'iam', ['admin']);
