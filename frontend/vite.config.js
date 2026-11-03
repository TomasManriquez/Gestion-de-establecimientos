import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { VitePWA } from 'vite-plugin-pwa'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // 'prompt': la versión nueva espera a que la persona acepte; recargar solo podría perder una edición a medias.
      registerType: 'prompt',
      includeAssets: ['icons/apple-touch-icon.png', 'slep-llanquihue.png'],
      manifest: {
        id: '/',
        name: 'SLEP Llanquihue · Gestión de Establecimientos',
        short_name: 'SLEP Datos',
        lang: 'es-CL',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: '#0b3a66',
        background_color: '#f3f9fd',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Solo se precachea el shell de la app. /api nunca pasa por el service worker: los datos offline
        // viven en IndexedDB (fase 1) y así ninguna respuesta autenticada queda en la caché del navegador.
        globPatterns: ['**/*.{js,css,html,png,svg,webmanifest}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true, // Needed for Docker container mapping
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
