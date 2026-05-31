import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    restoreMocks: true,
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    // Review aus dem LAN/Mesh: beliebige Host-Header zulassen (kein "Blocked request").
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8071',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        configure: (proxy) => {
          // Dev-Modus: X-Forwarded-For setzen damit Backend die IP-Prüfung besteht
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('X-Forwarded-For', '192.168.50.10');
            proxyReq.setHeader('X-Real-IP', '192.168.50.10');
          });
        },
      },
      // Guardian-Watchdog-API (:8072). In Produktion macht nginx dasselbe unter /guardian/.
      '/guardian': {
        target: 'http://127.0.0.1:8072',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/guardian/, ''),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('X-Forwarded-For', '192.168.50.10');
            proxyReq.setHeader('X-Real-IP', '192.168.50.10');
          });
        },
      },
    },
  },
});
