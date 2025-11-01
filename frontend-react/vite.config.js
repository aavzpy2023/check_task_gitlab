// /frontend-react/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', 
    port: 3000,
    
    // SSS: Corrección Crítica para Hot Reloading a través de un proxy Docker.
    // Esto le dice al cliente de Vite que use WebSockets para comunicarse
    // con el servidor, lo cual es más robusto detrás de Nginx.
    hmr: {
      clientPort: 8503, // El puerto que el NAVEGADOR ve
      protocol: 'ws',
    },
  },
})