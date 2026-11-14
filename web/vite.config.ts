/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  server: { port: 5174, strictPort: true },
  preview: { port: 4173, strictPort: true },
  build: { chunkSizeWarningLimit: 1500 },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx'],
  },
});
