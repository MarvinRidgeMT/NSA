import { useThree } from '@react-three/fiber';
import { useEffect } from 'react';
import type * as THREE from 'three';

type ProgramLike = { isReady?: () => boolean; getUniforms?: () => unknown };
type Renderer = THREE.WebGLRenderer & { compile: (s: THREE.Object3D, c: THREE.Camera) => Set<THREE.Material> | undefined };

const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));
const sleep = (ms: number) => new Promise<void>((r) => window.setTimeout(r, ms));

/**
 * Prepare every material in the scene ahead of use (display performance only; draws nothing).
 *
 * three.js links a material's shader program on the first frame that draws it, and its first use queries the program
 * (`getProgramInfoLog`, uniform lookup). Objects that start outside the view (sprites, ray lines, markers) reached that
 * point in the middle of an orbit drag; on Chrome's Metal backend (ANGLE) the query waits for the real compile, and a
 * stall trace measured single frames of 0.4–1.0 s there (docs/v2/GATES.md §9). Here, whenever the scene content changes,
 * every material is compiled (`renderer.compile`, which ignores the view frustum), and each program's first use is
 * triggered one per frame once it reports ready, so the cost lands while the scene loads instead of during interaction.
 * A second pass a moment later catches children that mount after their data loads.
 */
export function Precompile({ deps }: { deps: unknown[] }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    let live = true;
    const r = gl as Renderer;
    const run = async () => {
      if (!live) return;
      let mats: Set<THREE.Material> | undefined;
      try {
        mats = r.compile(scene, camera);
      } catch {
        return; // display optimisation only: on failure the first draw compiles, as before
      }
      for (const m of mats ?? []) {
        await nextFrame();
        if (!live) return;
        const prog = (r.properties.get(m) as { currentProgram?: ProgramLike } | undefined)?.currentProgram;
        for (let i = 0; i < 300 && prog?.isReady && !prog.isReady(); i++) await sleep(10);
        try {
          prog?.getUniforms?.();
        } catch {
          /* as above */
        }
      }
    };
    const a = requestAnimationFrame(() => void run());
    const b = window.setTimeout(() => void run(), 800);
    return () => {
      live = false;
      cancelAnimationFrame(a);
      window.clearTimeout(b);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gl, scene, camera, ...deps]);
  return null;
}
