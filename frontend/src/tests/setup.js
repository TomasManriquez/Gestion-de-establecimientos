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

// Radix (Select, Popover, Dropdown, Dialog) usa APIs de puntero y de scroll que jsdom no implementa.
if (typeof window !== 'undefined') {
  const proto = window.HTMLElement.prototype;
  if (!proto.hasPointerCapture) proto.hasPointerCapture = () => false;
  if (!proto.setPointerCapture) proto.setPointerCapture = () => {};
  if (!proto.releasePointerCapture) proto.releasePointerCapture = () => {};
  if (!proto.scrollIntoView) proto.scrollIntoView = () => {};
  if (!window.matchMedia) {
    // `min-width` se evalúa contra window.innerWidth (jsdom: 1024 = escritorio). Un test móvil fija innerWidth antes de renderizar.
    const minWidth = (query) => {
      const m = /min-width:\s*(\d+)px/.exec(query);
      return m ? window.innerWidth >= Number(m[1]) : false;
    };
    window.matchMedia = (query) => ({
      get matches() { return minWidth(query); }, media: query, onchange: null,
      addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false; },
    });
  }
}
