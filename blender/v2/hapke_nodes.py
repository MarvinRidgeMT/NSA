"""Emit the Hapke expression graph (blender/v2/hapke.py) as Blender shader Math nodes. Runs only inside Blender (bpy).

Material: Diffuse BSDF whose colour is pi r(i,e,g) / mu0 for the dominant light direction L (a constant from the scene
spec, i.e. the bundle's Sun or Earth direction), so Cycles' diffuse returns L_out = r E with its own cast shadows.
  mu0  = N . L          (N = shading normal from the Geometry node)
  mu   = N . V          (V = Geometry 'Incoming', toward the ray origin: the camera, or the previous bounce)
  cosg = L . V
Works on CPU and Metal (plain nodes; no OSL). Known approximation (documented): light from any other direction (earthshine
while the Sun is up, inter-reflections) is shaded with the dominant light's i and g.
"""
import math

import bpy

from . import hapke

_BIN = {'add': 'ADD', 'sub': 'SUBTRACT', 'mul': 'MULTIPLY', 'div': 'DIVIDE', 'pow': 'POWER', 'min': 'MINIMUM', 'max': 'MAXIMUM'}
_UN = {'sin': 'SINE', 'cos': 'COSINE', 'tan': 'TANGENT', 'exp': 'EXPONENT', 'log': 'LOGARITHM', 'sqrt': 'SQRT',
       'acos': 'ARCCOSINE', 'atan': 'ARCTANGENT', 'abs': 'ABSOLUTE'}


class Emitter:
    def __init__(self, nt, inputs):
        self.nt, self.inputs, self.memo, self.count = nt, inputs, {}, 0
        self.x = -2000

    def _math(self, op, a, b=None, use_clamp=False):
        n = self.nt.nodes.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = use_clamp
        n.location = (self.x + (self.count % 40) * 40, -(self.count // 40) * 40 - 400)
        self.count += 1
        self._feed(n.inputs[0], a)
        if b is not None:
            self._feed(n.inputs[1], b)
        if op == 'LOGARITHM':
            n.inputs[1].default_value = math.e
        return n.outputs[0]

    def _feed(self, sock, v):
        if isinstance(v, float):
            sock.default_value = v
        else:
            self.nt.links.new(v, sock)

    def emit(self, x):
        k = id(x)
        if k in self.memo:
            return self.memo[k]
        if x.op == 'const':
            out = float(x.value)
        elif x.op == 'var':
            out = self.inputs[x.name]
        elif x.op in _BIN:
            a, b = self.emit(x.args[0]), self.emit(x.args[1])
            if isinstance(a, float) and isinstance(b, float):
                out = float(x.eval({}))
            else:
                out = self._math(_BIN[x.op], a, b)
        elif x.op in _UN:
            a = self.emit(x.args[0])
            out = float(x.eval({})) if isinstance(a, float) else self._math(_UN[x.op], a)
        elif x.op == 'select':
            cnd, a, b = (self.emit(v) for v in x.args)
            gt = self._math('GREATER_THAN', cnd, 0.0)           # 1 if cond > 0 else 0
            diff = self._math('SUBTRACT', a, b)
            out = self._math('MULTIPLY_ADD', gt, diff)          # gt * (a - b) + b
            n = out.node
            self._feed(n.inputs[2], b)
        else:
            raise ValueError(x.op)
        self.memo[k] = out
        return out


def hapke_material(name, params, light_dir, cap=4.0, w_attribute=None):
    """Build the material. Returns (material, info).
    w_attribute: name of a per-vertex float attribute holding the Hapke w (WAC albedo, blender/v2/albedo.py). The other
    parameters stay constants. Every mesh using such a material MUST carry the attribute (a missing one reads 0 = black)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    diff = nt.nodes.new('ShaderNodeBsdfDiffuse')
    diff.location = (400, 0)
    diff.inputs['Roughness'].default_value = 0.0
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    geo.location = (-2400, 0)
    Lv = nt.nodes.new('ShaderNodeCombineXYZ')
    Lv.location = (-2400, -300)
    Lv.label = 'dominant light direction (bundle)'
    for i, c in enumerate(light_dir):
        Lv.inputs[i].default_value = float(c)

    def dot(a, b):
        n = nt.nodes.new('ShaderNodeVectorMath')
        n.operation = 'DOT_PRODUCT'
        nt.links.new(a, n.inputs[0])
        nt.links.new(b, n.inputs[1])
        return n.outputs['Value']

    inputs = {'mu0': dot(geo.outputs['Normal'], Lv.outputs[0]), 'mu': dot(geo.outputs['Normal'], geo.outputs['Incoming']),
              'cosg': dot(Lv.outputs[0], geo.outputs['Incoming'])}
    if w_attribute:
        at = nt.nodes.new('ShaderNodeAttribute')
        at.location = (-2400, -500)
        at.attribute_type = 'GEOMETRY'
        at.attribute_name = w_attribute
        at.label = 'Hapke w per vertex (LROC WAC map)'
        inputs['w'] = at.outputs['Fac']
        params = dict(params, w=hapke.X.var('w'))
    colour, _r = hapke.diffuse_colour_graph(params, cap=cap)
    em = Emitter(nt, inputs)
    c = em.emit(colour)
    if isinstance(c, float):
        diff.inputs['Color'].default_value = (c, c, c, 1)
    else:
        rgb = nt.nodes.new('ShaderNodeCombineColor')
        rgb.location = (200, 0)
        for i in range(3):
            nt.links.new(c, rgb.inputs[i])
        nt.links.new(rgb.outputs[0], diff.inputs['Color'])
    nt.links.new(diff.outputs[0], out.inputs['Surface'])
    m.diffuse_color = (0.12, 0.12, 0.12, 1)
    info = {'mathNodes': em.count, 'lightDirEnu': list(light_dir), 'colourCap': cap, 'wAttribute': w_attribute,
            'rule': 'Diffuse colour = pi r(i,e,g)/mu0 (capped), dominant light direction constant from the scene spec'}
    m['polaris'] = 'Hapke (2012) regolith, LROC WAC 643 nm parameters (Sato et al. 2014 product); MODEL'
    return m, info
