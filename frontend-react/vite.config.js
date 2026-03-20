import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // SSS: Directiva CRÍTICA para el despliegue en subdirectorio.
  // Esto asegura que todas las rutas de assets (JS, CSS, etc.) se generen
  // con el prefijo /tareas/.
  base: '/tareas/',

  server: {
    host: '0.0.0.0', 
    port: 3000,
    watch: {
      usePolling: true,
    },
    hmr: {
      clientPort: 80,
      protocol: 'ws',
    },
  },
})