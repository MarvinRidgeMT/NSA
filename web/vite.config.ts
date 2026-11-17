import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// v2 T2 "query any point -> compute now": the local solver API (python -m science.api.server --port 8767, POST /v1/solve)
// is reached through this same-origin proxy, so the viewer needs no CORS from it. Override with POLARIS_SOLVER_API.
const solverTarget = process.env.POLARIS_SOLVER_API ?? 'http://127.0.0.1:8767';
const solverProxy = { '/solver-api': { target: solverTarget, changeOrigin: true, rewrite: (p: string) => p.replace(/^\/solver-api/, '') || '/' } };

export default defineConfig({
  base: './',
  plugins: [react()],
  // Final Apex P1: bind IPv4 loopback explicitly. With host 'localhost', macOS resolves to ::1 first, so the server answered on
  // localhost but not on 127.0.0.1, and a tab on 127.0.0.1 could reach a different (stale) server on the same port. strictPort
  // makes a port clash fail loudly instead.
  server: { host: '127.0.0.1', port: 5174, strictPort: true, proxy: solverProxy },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy: solverProxy },
  build: { chunkSizeWarningLimit: 1500 },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx'],
  },
});
