import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// Gelistirmede API ayri portta (uvicorn :8000); /api ve /graphql oraya vekillenir.
// Uretimde `vite build` -> dist/, FastAPI bunu kokten servis eder (SPA geri donusu).
export default defineConfig({
  plugins: [vue()],
  // Statik dosyalar (logo vb.): src/public -> dist koku; /assests/img/logo/... ile erisilir
  publicDir: 'src/public',
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
      '/graphql': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
});
