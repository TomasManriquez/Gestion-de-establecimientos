import { useCallback, useSyncExternalStore } from 'react';

/**
 * Sigue una media query de CSS. Sin `matchMedia` (jsdom en los tests, render en servidor) devuelve
 * `fallback`: el escritorio, para que las pantallas se vean y se prueben como siempre.
 */
export function useMediaQuery(query, fallback = true) {
  const subscribe = useCallback((onChange) => {
    const mq = window.matchMedia?.(query);
    mq?.addEventListener('change', onChange);
    return () => mq?.removeEventListener('change', onChange);
  }, [query]);
  return useSyncExternalStore(subscribe, () => window.matchMedia?.(query).matches ?? fallback, () => fallback);
}

/** Mismo corte que el `lg` de Tailwind: desde aquí hay sidebar y tabla; debajo, barra inferior y tarjetas. */
export const useIsDesktop = () => useMediaQuery('(min-width: 1024px)');
