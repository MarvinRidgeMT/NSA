import { useThree } from '@react-three/fiber';
import { useEffect, useLayoutEffect, useState } from 'react';
import * as THREE from 'three';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';

/**
 * A fat line whose material lives as long as the component. drei's <Line> disposes its material whenever `points` change; when
 * that happens to every line using a shader program in one commit, three.js frees the program and the next frame compiles it
 * again. On the Mac (ANGLE → Metal) that recompilation stalled the GPU ~1 s on every time step (measured 15 Nov 2026,
 * M5 Pro). Here only the vertex buffer is replaced when points change; the material and its program stay.
 */
export interface StableLineProps {
  points: THREE.Vector3[];
  color: string;
  lineWidth?: number;
  dashed?: boolean;
  dashSize?: number;
  gapSize?: number;
  transparent?: boolean;
  opacity?: number;
  depthTest?: boolean;
  depthWrite?: boolean;
  renderOrder?: number;
}

export function StableLine({ points, color, lineWidth = 1, dashed = false, dashSize = 1, gapSize = 1, transparent = false, opacity = 1, depthTest = true, depthWrite = true, renderOrder }: StableLineProps) {
  const size = useThree((s) => s.size);
  const [line] = useState(() => new Line2(new LineGeometry(), new LineMaterial()));
  useLayoutEffect(() => {
    // segments [x0,y0,z0,x1,y1,z1] and cumulative distances; written into the existing GPU buffers when the point count is
    // unchanged (the usual case on a time step), so no buffer is allocated per sample
    const nSeg = Math.max(points.length - 1, 0);
    const seg = new Float32Array(nSeg * 6);
    const dist = new Float32Array(nSeg * 2);
    let acc = 0;
    for (let i = 0; i < nSeg; i++) {
      const a = points[i];
      const b = points[i + 1];
      seg.set([a.x, a.y, a.z, b.x, b.y, b.z], i * 6);
      dist[i * 2] = acc;
      acc += a.distanceTo(b);
      dist[i * 2 + 1] = acc;
    }
    const g = line.geometry;
    const start = g.attributes.instanceStart as THREE.InterleavedBufferAttribute | undefined;
    const dStart = g.attributes.instanceDistanceStart as THREE.InterleavedBufferAttribute | undefined;
    if (start && start.data.array.length === seg.length && dStart && dStart.data.array.length === dist.length) {
      (start.data.array as Float32Array).set(seg);
      start.data.needsUpdate = true;
      (dStart.data.array as Float32Array).set(dist);
      dStart.data.needsUpdate = true;
      g.computeBoundingBox();
      g.computeBoundingSphere();
    } else {
      g.setPositions(seg);
      line.computeLineDistances();
    }
  }, [line, points]);
  useLayoutEffect(() => {
    const m = line.material;
    const hadDash = 'USE_DASH' in m.defines;
    if (dashed && !hadDash) {
      m.defines.USE_DASH = '';
      m.needsUpdate = true;
    } else if (!dashed && hadDash) {
      delete m.defines.USE_DASH;
      m.needsUpdate = true;
    }
    m.dashed = dashed;
    m.color.set(color);
    m.linewidth = lineWidth;
    m.dashSize = dashSize;
    m.gapSize = gapSize;
    m.opacity = opacity;
    if (m.transparent !== transparent || m.depthTest !== depthTest || m.depthWrite !== depthWrite) {
      m.transparent = transparent;
      m.depthTest = depthTest;
      m.depthWrite = depthWrite;
    }
    m.resolution.set(size.width, size.height);
    if (renderOrder !== undefined) line.renderOrder = renderOrder;
  }, [line, color, lineWidth, dashed, dashSize, gapSize, transparent, opacity, depthTest, depthWrite, size.width, size.height, renderOrder]);
  useEffect(
    () => () => {
      line.geometry.dispose();
      line.material.dispose();
    },
    [line],
  );
  return <primitive object={line} />;
}
