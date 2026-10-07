/**
 * units.js — ordena la lista plana de unidades en recorrido de árbol (padre antes que hijas)
 * y agrega `depth`, para mostrarla con sangría en un Select.
 */
export function orderUnits(flat = []) {
  const byParent = new Map();
  for (const unit of flat) {
    const key = unit.parent_id ?? null;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(unit);
  }
  for (const list of byParent.values()) list.sort((a, b) => (a.order - b.order) || a.name.localeCompare(b.name, 'es'));
  const out = [];
  const walk = (parentId, depth) => {
    for (const unit of byParent.get(parentId) ?? []) {
      out.push({ ...unit, depth });
      walk(unit._id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}
