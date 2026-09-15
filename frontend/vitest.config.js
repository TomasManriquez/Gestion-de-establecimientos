/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '../../components': path.resolve(__dirname, './src/components'),
      '../components': path.resolve(__dirname, './src/components'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.js'],
    include: ['src/tests/**/*.test.{js,jsx}'],
    // El default de 5s se queda corto: los primeros tests que importan árboles
    // pesados (maplibre-gl, recharts) pagan el costo de transform de Vite.
    testTimeout: 20000,
    coverage: {
      reporter: ['text', 'json', 'html'],
      include: ['src/components/**/*.jsx'],
      exclude: ['src/tests/**'],
    },
  },
});
