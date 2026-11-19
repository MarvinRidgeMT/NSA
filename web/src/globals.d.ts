declare const __GLOBE_FILES__: string[];
/** S14 Part B: public/globe/globe_manifest.json at build time, limited to globes whose file matches its SHA-256 (vite.config.ts); null when there is none */
declare const __GLOBE_MANIFEST__: { schema?: string; globes: import('./simple/globeMath').GlobeManifestEntry[] } | null;
