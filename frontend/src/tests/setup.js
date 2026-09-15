/**
 * setup.js — Configuración global de tests de frontend
 * Extiende los matchers de Vitest con @testing-library/jest-dom
 */
import '@testing-library/jest-dom';

// El entorno jsdom de vitest no deja localStorage/sessionStorage utilizables
// en esta versión (y Node 22+ además define su propio accessor experimental
// que pisa el de jsdom). Se define un polyfill en memoria simple y determinista.
function createMemoryStorage() {
  let store = new Map();
  return {
    getItem: (key) => (store.has(String(key)) ? store.get(String(key)) : null),
    setItem: (key, value) => { store.set(String(key), String(value)); },
    removeItem: (key) => { store.delete(String(key)); },
    clear: () => { store.clear(); },
    key: (index) => Array.from(store.keys())[index] ?? null,
    get length() { return store.size; },
  };
}

for (const target of [globalThis, typeof window !== 'undefined' ? window : null]) {
  if (!target) continue;
  Object.defineProperty(target, 'localStorage', { value: createMemoryStorage(), configurable: true, writable: true });
  Object.defineProperty(target, 'sessionStorage', { value: createMemoryStorage(), configurable: true, writable: true });
}

// jsdom no implementa ResizeObserver (lo usa recharts vía ResponsiveContainer).
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
