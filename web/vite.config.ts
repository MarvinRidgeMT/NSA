import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Plugin } from 'vite';

// Moon models present in public/globe at build time (they are git-ignored NASA assets, so the set differs per machine).
// The Simple-mode globe picks from this list instead of probing with requests.
const globeFiles = existsSync('public/globe') ? readdirSync('public/globe').filter((f) => f.endsWith('.glb')) : [];

// S14 Part B: the POLARIS v2 globe (polaris_moon_globe.glb) comes with public/globe/globe_manifest.json, which states its axes,
// labels and credit. The manifest reaches the app only for globes whose file on disk has the SHA-256 the manifest gives, so
// the labels shown are the labels of the file drawn; a v2 file without a matching manifest entry is not offered at all.
const V2_GLOBE = 'polaris_moon_globe.glb';
const manifestPath = 'public/globe/globe_manifest.json';
const globeManifest = (() => {
  if (!existsSync(manifestPath)) return null;
  try {
    const m = JSON.parse(readFileSync(manifestPath, 'utf8')) as { schema?: string; globes?: { url: string; sha256: string }[] };
    const ok = (m.globes ?? []).filter((g) => {
      const f = join('public', g.url);
      return existsSync(f) && createHash('sha256').update(readFileSync(f)).digest('hex') === g.sha256;
    });
    return { schema: m.schema, globes: ok };
  } catch {
    return null;
  }
})();
const v2Ready = globeFiles.includes(V2_GLOBE) && !!globeManifest?.globes.some((g) => g.url === `globe/${V2_GLOBE}`);

// The v2 globe's mesh is Draco-compressed. three.js ships the decoder (no new package): it is served from node_modules in
// development and copied into the build as draco/*, only when the v2 globe is there to need it.
const dracoDir = 'node_modules/three/examples/jsm/libs/draco/gltf';
const dracoFiles = ['draco_wasm_wrapper.js', 'draco_decoder.wasm', 'draco_decoder.js'];
const draco = (): Plugin => ({
  name: 'polaris-draco-decoder',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const f = /\/draco\/([a-z_]+\.(?:js|wasm))(?:\?.*)?$/.exec(req.url ?? '')?.[1];
      if (!f || !dracoFiles.includes(f) || !existsSync(join(dracoDir, f))) return next();
      res.setHeader('Content-Type', f.endsWith('.wasm') ? 'application/wasm' : 'text/javascript');
      res.end(readFileSync(join(dracoDir, f)));
    });
  },
  generateBundle() {
    if (!v2Ready) return;
    for (const f of dracoFiles) if (existsSync(join(dracoDir, f))) this.emitFile({ type: 'asset', fileName: `draco/${f}`, source: readFileSync(join(dracoDir, f)) });
  },
});

export default defineConfig({
  base: './',
  plugins: [react(), draco()],
  define: { __GLOBE_FILES__: JSON.stringify(globeFiles.filter((f) => f !== V2_GLOBE || v2Ready)), __GLOBE_MANIFEST__: JSON.stringify(globeManifest) },
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
