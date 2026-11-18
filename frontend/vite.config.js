import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Proxy de desarrollo: el navegador llama a /api/... y Vite reenvía
// a cada microservicio, quitando el prefijo para evitar CORS.
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api/usuarios': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api\/usuarios/, ''),
      },
      '/api/foro': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api\/foro/, ''),
      },
      '/api/interacciones': {
        target: 'http://localhost:5002',
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api\/interacciones/, ''),
      },
    },
  },
})
