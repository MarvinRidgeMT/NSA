import { describe, expect, it } from 'vitest';
import { isSoftwareDevice, isSoftwareRenderer, pickQuality, tierFor, type DeviceFacts } from '../../src/simple/quality';

const desk = (renderer: string): DeviceFacts => ({ renderer, coarsePointer: false, shortSidePx: 982, floatTargets: true });

describe('Simple-mode quality tier (display only)', () => {
  it('Mac and discrete GPUs get the high tier', () => {
    expect(tierFor(desk('ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)'))).toBe('high');
    expect(tierFor(desk('ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)'))).toBe('high');
  });
  it('other hardware GPUs and tablets get the medium tier', () => {
    expect(tierFor(desk('ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)'))).toBe('medium');
    expect(tierFor({ renderer: 'Apple GPU', coarsePointer: true, shortSidePx: 820, floatTargets: true })).toBe('medium');
  });
  it('phones, software rendering and no WebGL get the low tier (post off)', () => {
    expect(tierFor({ renderer: 'Apple GPU', coarsePointer: true, shortSidePx: 390 })).toBe('low');
    expect(tierFor(desk('ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)'))).toBe('low');
    expect(tierFor(desk('llvmpipe (LLVM 15.0.7, 256 bits)'))).toBe('low');
    expect(tierFor(desk(''))).toBe('low');
  });
  it('?quality= overrides the device choice; anything else is ignored', () => {
    const phone = () => ({ renderer: 'Apple GPU', coarsePointer: true, shortSidePx: 390, floatTargets: true });
    expect(pickQuality('?quality=high', phone)).toEqual({ tier: 'high', source: 'link' });
    expect(pickQuality('?mode=simple&quality=low', () => desk('Apple M4 Pro'))).toEqual({ tier: 'low', source: 'link' });
    expect(pickQuality('?quality=ultra', phone)).toEqual({ tier: 'low', source: 'device' });
    expect(pickQuality('', () => desk('Apple M4 Pro'))).toEqual({ tier: 'high', source: 'device' });
  });
  it('a GPU that cannot render into a half-float buffer (no WebGL2 float colour buffer) gets the low tier', () => {
    expect(tierFor({ ...desk('ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)'), floatTargets: false })).toBe('low');
    expect(tierFor({ renderer: 'Apple GPU', coarsePointer: true, shortSidePx: 820 })).toBe('low');
    expect(pickQuality('', () => ({ ...desk('Apple M4 Pro'), floatTargets: false }))).toEqual({ tier: 'low', source: 'device' });
  });
  it('?quality=high or medium never forces the post chain onto a device that cannot run it', () => {
    const noFloat = () => ({ ...desk('Apple M4 Pro'), floatTargets: false });
    const noGl = () => ({ renderer: '', coarsePointer: false, shortSidePx: 982 });
    for (const q of ['?quality=high', '?quality=medium']) {
      expect(pickQuality(q, noFloat)).toEqual({ tier: 'low', source: 'device' });
      expect(pickQuality(q, noGl)).toEqual({ tier: 'low', source: 'device' });
    }
    expect(pickQuality('?quality=low', noGl)).toEqual({ tier: 'low', source: 'link' });
  });
});

describe('software rendering, for the Moon model choice (S14 Part B)', () => {
  it('SwiftShader and llvmpipe are software; Apple, NVIDIA and Intel GPUs are not', () => {
    expect(isSoftwareRenderer('ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)')).toBe(true);
    expect(isSoftwareRenderer('llvmpipe (LLVM 15.0.7, 256 bits)')).toBe(true);
    expect(isSoftwareRenderer('ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)')).toBe(false);
    expect(isSoftwareRenderer('Apple GPU')).toBe(false);
    expect(isSoftwareRenderer('ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)')).toBe(false);
    expect(isSoftwareRenderer('ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)')).toBe(false);
  });
  it('other software renderers by name: lavapipe, softpipe, WARP, Basic Render, Mesa OffScreen, Apple Software Renderer', () => {
    for (const r of [
      'llvmpipe (LLVM 17.0.6, 256 bits)',
      'ANGLE (Mesa, Vulkan 1.3 (llvmpipe (LLVM 17.0.6, 256 bits) (0x00000000)), lavapipe)',
      'softpipe',
      'ANGLE (Microsoft, Microsoft Basic Render Driver Direct3D11 vs_5_0 ps_5_0, D3D11)',
      'ANGLE (Microsoft, WARP Direct3D11)',
      'Mesa OffScreen',
      'Apple Software Renderer',
    ])
      expect(isSoftwareRenderer(r), r).toBe(true);
    expect(isSoftwareRenderer('ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Ti Direct3D11 vs_5_0 ps_5_0, D3D11)')).toBe(false);
    expect(isSoftwareRenderer('Adreno (TM) 740')).toBe(false);
    expect(isSoftwareRenderer('Mali-G78')).toBe(false);
  });
  it('a hidden or unknown renderer name counts as software when the browser reports a major performance caveat', () => {
    const f = (renderer: string, perfCaveat?: boolean): DeviceFacts => ({ renderer, coarsePointer: false, shortSidePx: 982, floatTargets: true, perfCaveat });
    expect(isSoftwareDevice(f('WebKit WebGL', true))).toBe(true);
    expect(isSoftwareDevice(f('WebKit WebGL', false))).toBe(false);
    expect(isSoftwareDevice(f('WebKit WebGL'))).toBe(false);
    expect(isSoftwareDevice(f('ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)', false))).toBe(true);
    expect(isSoftwareDevice(f('ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)', false))).toBe(false);
  });
});
