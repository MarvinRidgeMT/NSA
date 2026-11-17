import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { existsSync, readdirSync } from 'node:fs';

// Moon models present in public/globe at build time (they are git-ignored NASA assets, so the set differs per machine).
// The Simple-mode globe picks from this list instead of probing with requests.
const globeFiles = existsSync('public/globe') ? readdirSync('public/globe').filter((f) => f.endsWith('.glb')) : [];

export default defineConfig({
  base: './',
  plugins: [react()],
  define: { __GLOBE_FILES__: JSON.stringify(globeFiles) },
  // Final Apex P1: bind IPv4 loopback explicitly. With host 'localhost', macOS resolves to ::1 first, so the server answered on
  // localhost but not on 127.0.0.1, and a tab on 127.0.0.1 could reach a different (stale) server on the same port. strictPort
  // makes a port clash fail loudly instead.
  server: { host: '127.0.0.1', port: 5174, strictPort: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
  build: { chunkSizeWarningLimit: 1500 },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx'],
  },
});
