"""POLARIS X — Blender asset pipeline (optional; visual-only).

Run with Blender 4.5+ (or a compatible release):
  blender --background --python blender/build_lunar_scene.py -- \
      --bundle data/nasa-jpl-science-bundle.json --site connecting --output blender/output

Reads the SAME DEM grid as the scientific web app. It DOES NOT create scientific
visibility percentages. Vertex colors, camera, key lights and materials are
presentation decisions. Output: a .blend scene and a .glb asset.

Do not treat artist-directed Sun lights as JPL ephemeris validation.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy


def args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, help='POLARIS X science bundle JSON')
    parser.add_argument('--site', default='connecting')
    parser.add_argument('--output', default='blender/output')
    parser.add_argument('--max-vertices-per-axis', type=int, default=260)
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def clean():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def make_mesh(dem, max_axis):
    # Local x=east, y=north, z=up in meters. Scientific rendering does NOT apply
    # any arbitrary exaggeration here; physical metric scale is preserved.
    n = dem['n']
    idx = sorted(set(round(i*(n-1)/(min(n,max_axis)-1)) for i in range(min(n,max_axis))))
    m=len(idx)
    if len(dem['values']) != n*n:raise ValueError('Invalid DEM grid length')
    vertices=[]
    for j in idx:
        for i in idx:
            x=dem['originX']+i*dem['spacing']
            y=dem['originY']+j*dem['spacing']
            z=dem['values'][j*n+i]
            vertices.append((x,y,z))
    faces=[]
    for j in range(m-1):
        for i in range(m-1):
            a=j*m+i;b=a+m
            faces.append((a,a+1,b+1,b))
    mesh=bpy.data.meshes.new('POLARIS DEM GRID')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    ob=bpy.data.objects.new('DEM | scientific elevations | meters',mesh)
    bpy.context.collection.objects.link(ob)
    for poly in mesh.polygons:poly.use_smooth=True
    return ob,vertices


def mat_terrain(vertices):
    lo=min(p[2] for p in vertices);hi=max(p[2] for p in vertices)
    m=bpy.data.materials.new('Lunar regolith | visualization')
    m.use_nodes=True
    nodes=m.node_tree.nodes;nodes.clear();links=m.node_tree.links
    out=nodes.new('ShaderNodeOutputMaterial');out.location=(480,0)
    principled=nodes.new('ShaderNodeBsdfPrincipled');principled.location=(200,0)
    principled.inputs['Roughness'].default_value=.96
    principled.inputs['Metallic'].default_value=0
    geometry=nodes.new('ShaderNodeNewGeometry');geometry.location=(-660,0)
    sep=nodes.new('ShaderNodeSeparateXYZ');sep.location=(-450,0)
    ramp=nodes.new('ShaderNodeValToRGB');ramp.location=(-80,80)
    ramp.color_ramp.elements[0].position=0
    ramp.color_ramp.elements[0].color=(.22,.26,.29,1)
    ramp.color_ramp.elements[1].position=1
    ramp.color_ramp.elements[1].color=(.65,.62,.56,1)
    mapping=nodes.new('ShaderNodeMapRange');mapping.location=(-280,80)
    mapping.inputs['From Min'].default_value=lo
    mapping.inputs['From Max'].default_value=hi if hi>lo else lo+1
    links.new(geometry.outputs['Position'],sep.inputs[0])
    links.new(sep.outputs['Z'],mapping.inputs['Value'])
    links.new(mapping.outputs['Result'],ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'],principled.inputs['Base Color'])
    links.new(principled.outputs['BSDF'],out.inputs['Surface'])
    return m


def aim(obj,target):
    from mathutils import Vector
    direction=Vector(target)-obj.location
    obj.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()


def build():
    cfg=args()
    bundle=json.loads(Path(cfg.bundle).expanduser().read_text())
    if bundle.get('format')!='POLARIS-X5D-v1':raise ValueError('Expected POLARIS-X5D-v1 bundle')
    entry=next((x for x in bundle.get('datasets',[]) if x['siteId']==cfg.site),None)
    if not entry:raise ValueError('No DEM for site '+cfg.site)
    dem=entry['dem'];clean()
    ground,points=make_mesh(dem,cfg.max_vertices_per_axis)
    ground.data.materials.append(mat_terrain(points))
    zmid=sum(p[2] for p in points)/len(points)
    span=(dem['n']-1)*dem['spacing']
    # A recognizable but intentionally not NASA-certified lander marker.
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=35,depth=20,location=(0,0,dem['values'][(dem['n']//2)*dem['n']+dem['n']//2]+12))
    marker=bpy.context.object;marker.name='Observer visualization marker (NOT hardware)'
    marker_mat=bpy.data.materials.new('Marker cyan');marker_mat.diffuse_color=(.02,.7,.75,1)
    marker.data.materials.append(marker_mat)
    # Blender-ready cinematic shot; lighting is artistic and NOT JPL-synchronized.
    bpy.ops.object.light_add(type='SUN', location=(0,0,zmid+3000))
    light=bpy.context.object;light.name='ARTISTIC SUN | NOT EPHEMERIS'
    light.data.energy=2.2;light.rotation_euler=(math.radians(58),math.radians(-21),math.radians(30))
    bpy.ops.object.camera_add(location=(span*.64,-span*.85,zmid+span*.66))
    camera=bpy.context.object;camera.name='Oblique landing-site camera';aim(camera,(0,0,zmid))
    camera.data.type='PERSP';camera.data.lens=42
    bpy.context.scene.camera=camera
    bpy.context.scene.render.engine='CYCLES'
    bpy.context.scene.cycles.samples=64
    bpy.context.scene.render.resolution_x=1920
    bpy.context.scene.render.resolution_y=1080
    bpy.context.scene.render.resolution_percentage=100
    bpy.context.scene.world.color=(.025,.025,.035)
    out=Path(cfg.output).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    blend=out/f'POLARIS_{cfg.site}.blend'
    glb=out/f'POLARIS_{cfg.site}.glb'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    # Include terrain only, to avoid accidental interpretation of marker as NASA hardware.
    bpy.ops.object.select_all(action='DESELECT');ground.select_set(True);bpy.context.view_layer.objects.active=ground
    bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True)
    print('Blender DEM scene:',blend,'\nGLB:',glb)
    print('Rendering metadata: artist lighting; 1 Blender unit = 1 m; no scientific illumination output')


if __name__=='__main__':build()
