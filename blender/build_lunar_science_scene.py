#!/usr/bin/env python3
"""Build a time-scrubbable Blender lunar DEM scene from POLARIS X NASA/JPL bundle.

This is a research/education visualization, NOT lunar flight planning.
Requires Blender 4.5+ (bpy). 1 Blender unit = 1 metre; local X east, Y north, Z up.
Example:
 blender --background --python blender/build_lunar_science_scene.py -- \
   --bundle data/nasa-jpl-science-bundle.json --site connecting --outdir blender/output

The input bundle is produced by the parent POLARIS-X5D-PRO scripts/prepare_science.py.
Visibilities are geometrical estimates within a finite DEM; frame conversion,
angular conventions, lunar curvature accuracy and independent validation remain open.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Blender does not reliably put the directory containing a --python script on
# sys.path.  Resolve the geometry helper relative to this file so the builder
# works regardless of the caller's current working directory.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from polaris_geometry import elevation, validate_dem, direction, trace_visibility, terrain_horizon


def parse_args():
    p=argparse.ArgumentParser(description=__doc__)
    src=p.add_mutually_exclusive_group(required=True)
    src.add_argument('--bundle')
    src.add_argument('--demo',action='store_true')
    p.add_argument('--site',default='connecting')
    p.add_argument('--outdir',default='blender/output')
    p.add_argument('--max-mesh-axis',type=int,default=210)
    p.add_argument('--max-frames',type=int,default=130)
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def collection(name):
    c=bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def transfer(ob,c):
    for old in list(ob.users_collection): old.objects.unlink(ob)
    c.objects.link(ob)
    return ob


def mat(name,color,emission=0):
    m=bpy.data.materials.new(name)
    m.diffuse_color=tuple(color)+(1,)
    m.use_nodes=True
    node=m.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=tuple(color)+(1,)
    node.inputs['Roughness'].default_value=.94
    if emission:
        node.inputs['Emission Color'].default_value=tuple(color)+(1,)
        node.inputs['Emission Strength'].default_value=emission
    return m


def point_between(ob,first,second):
    a=Vector(first);b=Vector(second)
    vec=b-a
    if vec.length < 1e-4: vec.z+=1e-4
    ob.location=(a+b)/2
    ob.rotation_euler=vec.to_track_quat('Z','Y').to_euler()
    # This cylinder is modelled at 2 metres long and scaled on its local Z axis.
    ob.scale=(ob['tube_radius_m'],ob['tube_radius_m'],vec.length/2)


def add_tube(name,c,radius,material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=1,depth=2)
    ob=transfer(bpy.context.object,c);ob.name=name
    ob['tube_radius_m']=radius
    ob.data.materials.append(material)
    return ob


def sphere(name,c,location,radius,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=radius,location=location)
    ob=transfer(bpy.context.object,c);ob.name=name
    ob.data.materials.append(material)
    return ob


def line(name,c,coordinates,material,radius):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D'
    spl=curve.splines.new('POLY');spl.points.add(len(coordinates)-1)
    for p,xyz in zip(spl.points,coordinates):p.co=(*xyz,1)
    curve.bevel_depth=radius;curve.bevel_resolution=2
    ob=bpy.data.objects.new(name,curve);c.objects.link(ob)
    curve.materials.append(material)
    return ob


def look_at(ob,target):
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()


def dem_mesh(name, dem, target_collection, max_axis):
    """Create an unexaggerated ENU mesh from a canonical south-to-north DEM."""
    step=float(dem['spacing']);n=int(dem['n'])
    count=min(n,max(10,max_axis))
    inds=sorted(set(int(round(i*(n-1)/(count-1))) for i in range(count)))
    m=len(inds)
    verts=[(float(dem['originX'])+i*step,float(dem['originY'])+j*step,
            float(dem['values'][j*n+i])) for j in inds for i in inds]
    faces=[(j*m+i,j*m+i+1,(j+1)*m+i+1,(j+1)*m+i)
           for j in range(m-1) for i in range(m-1)]
    mesh=bpy.data.meshes.new(name+' geometry')
    mesh.from_pydata(verts,[],faces);mesh.update()
    terrain=bpy.data.objects.new(name,mesh);target_collection.objects.link(terrain)
    for face in mesh.polygons:face.use_smooth=True
    terrain['source']=dem.get('source','unspecified')
    terrain['source_sha256']=dem.get('sourceSha256') or 'not-recorded'
    terrain['frame']=dem.get('frame','unspecified')
    terrain['local_axes']='X east, Y north, Z elevation; metres'
    terrain['vertical_exaggeration']=1.0
    terrain['original_spacing_m']=step
    return terrain,verts


def add_camera(name,target_collection,location,target,lens=45):
    bpy.ops.object.camera_add(location=location)
    camera=transfer(bpy.context.object,target_collection);camera.name=name
    look_at(camera,target);camera.data.lens=lens
    return camera


def file_sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def synthetic_bundle():
    # Deterministic illustrative DEM and sky. NOT NASA data or JPL ephemerides.
    n=121;span=2300;spacing=span/(n-1)
    values=[]
    for j in range(n):
        y=-span/2+j*spacing
        for i in range(n):
            x=-span/2+i*spacing
            rr=math.hypot((x-220)/1.16,(y-110)*1.14)
            z=(-87*math.exp(-((rr/270)**4))
              +49*math.exp(-((rr-280)/87)**2)
              +118*math.exp(-((x+440)/225)**2)*math.exp(-((y-210)/510)**2)
              +70*math.exp(-((y+340)/110)**2)*math.exp(-((x-50)/560)**2)
              +12*math.sin(x/85+y/130)+8*math.sin(x/41-y/65)
              +4*math.cos(x/27+y/34)+.024*x-.018*y)
            values.append(z)
    rows=[]
    for t in range(49):
        sunel=1+11*math.sin(math.pi*t/48)
        rows.append({'time':'DEMO frame %d / NO EPHEMERIS'%t,
          'sun':{'az':0,'el':sunel},'earth':{'az':94,'el':10}})
    return {'format':'POLARIS-X5D-v1','datasets':[{'siteId':'connecting',
       'dem':{'kind':'synthetic','n':n,'spacing':spacing,
               'originX':-span/2,'originY':-span/2,'values':values,
               'source':'DEMO - PROCEDURALLY GENERATED TERRAIN; not NASA'},
       'ephemeris':{'source':'DEMO - analytic Sun/Earth; not JPL','samples':rows}}]}

def main():
    cfg=parse_args()
    bundle=synthetic_bundle() if cfg.demo else json.loads(Path(cfg.bundle).read_text())
    if bundle.get('format') not in ('POLARIS-X5D-v1','POLARIS-X5D-v2'):
        raise ValueError('Unsupported POLARIS data format')
    dataset=next((d for d in bundle['datasets'] if d['siteId']==cfg.site),None)
    if not dataset:raise ValueError('Site missing from bundle: '+cfg.site)
    dem=dataset['dem'];validate_dem(dem)
    local_dem=dataset.get('localDem')
    if local_dem:validate_dem(local_dem)
    if dem.get('kind')!='nasa' and not cfg.demo:raise ValueError('Refusing to label non-NASA DEM as NASA terrain')
    samples=dataset['ephemeris']['samples']
    if len(samples)<2:raise ValueError('At least two JPL samples are required')
    for row in samples:
        for k in ('sun','earth'):
            if not all(q in row[k] for q in ('az','el')):raise ValueError('Missing '+k+' angle')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for c in list(bpy.data.collections):
        if c.name!='Collection' and c.users==0:bpy.data.collections.remove(c)
    collections={name:collection(name) for name in (
        'NASA_DEM_TERRAIN' if not cfg.demo else 'SYNTHETIC_DEM_TERRAIN',
        'GLOBAL_CONTEXT','LANDING_SITE_MARKERS','OBSERVER_AND_MAST','SUN_GEOMETRY',
        'EARTH_GEOMETRY','RAYS_AND_OBSTRUCTIONS','HORIZON_WHEEL','5D_SCENARIOS',
        'SCIENTIFIC_LABELS','CAMERAS','LIGHTS','METADATA')}
    terrain_c=collections['NASA_DEM_TERRAIN' if not cfg.demo else 'SYNTHETIC_DEM_TERRAIN']
    global_c=collections['GLOBAL_CONTEXT'];marker_c=collections['LANDING_SITE_MARKERS']
    observer_c=collections['OBSERVER_AND_MAST'];sun_c=collections['SUN_GEOMETRY']
    earth_c=collections['EARTH_GEOMETRY'];ray_c=collections['RAYS_AND_OBSTRUCTIONS']
    horizon_c=collections['HORIZON_WHEEL'];status_c=collections['5D_SCENARIOS']
    cam_c=collections['CAMERAS'];light_c=collections['LIGHTS']
    step=float(dem['spacing']);n=int(dem['n'])
    regolith=mat('Regolith | neutral reference surface',(.31,.35,.39))
    terrain,verts=dem_mesh(
        'ENV | SYNTHETIC demonstrator | not NASA' if cfg.demo else 'ENV | NASA regional horizon DEM',
        dem,global_c if local_dem else terrain_c,cfg.max_mesh_axis)
    terrain.data.materials.append(regolith)
    local_terrain=None
    if local_dem:
        local_terrain,local_verts=dem_mesh('ENV | NASA PGDA 5m local DEM',local_dem,terrain_c,cfg.max_mesh_axis)
        local_terrain.data.materials.append(regolith)
    sun_color=mat('SUN | amber center-direction guide',(.98,.58,.07),1.6)
    earth_color=mat('EARTH | blue center-direction guide',(.06,.70,.98),1.6)
    observer_color=mat('OBSERVER | teal datum',(.06,.88,.74),1.4)
    blocked_color=mat('CRITICAL | terrain blockage',(.95,.21,.17),1.2)
    base_color=mat('SUPPORT | instrument housing',(.21,.27,.32))
    plot_color=mat('PLOT | horizon-angle visual exaggeration',(.36,.90,.67),1.0)
    z=elevation(dem,0,0)
    span=(n-1)*step
    r=max(3,span*.003)
    observer_height=2.0
    start=(0,0,z+observer_height)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=r*.7,depth=r*.45,location=(0,0,z+r*.225))
    base=transfer(bpy.context.object,marker_c);base.name='OBS | surface reference (illustrative marker)';base.data.materials.append(base_color)
    sphere('OBS | local observer +2m',observer_c,start,r*.5,observer_color)
    # A 360-degree synthetic-style horizon ring is a *chart*, not measured terrain elevation.
    plot=[]
    horizon_limit=min(span*.4,12000)
    for az in range(0,361,3):
        info=terrain_horizon(dem,0,0,z+observer_height,az,radius_m=horizon_limit,step_m=step)
        ang=info['angle_deg'] if info['samples'] else 0
        a=math.radians(az)
        plot.append((math.sin(a)*span*.065, math.cos(a)*span*.065,
                     z+max(span*.01,10)+max(-15,min(30,ang))*max(span*.0018,1)))
    line('PLOT | horizon wheel (angle vertically exaggerated)',horizon_c,plot,plot_color,max(r*.035,.5))
    # Note: a cropped DEM cannot resolve distant ridges beyond the supplied footprint.
    sun_ray=add_tube('SUN | animated center ray finite DEM',ray_c,max(2,r*.10),sun_color)
    earth_ray=add_tube('EARTH | animated center ray finite DEM',ray_c,max(2,r*.10),earth_color)
    sun_tip=sphere('SUN | ray endpoint',sun_c,start,max(3,r*.4),sun_color)
    earth_tip=sphere('EARTH | ray endpoint',earth_c,start,max(3,r*.4),earth_color)
    # Show a 3x3 neighborhood with a fixed scenario at the first source-backed timestamp.
    offset=max(2*step,span*.006)
    first=samples[0]['sun']
    stress=[]
    for dy in (-offset,0,offset):
        for dx in (-offset,0,offset):
            if not (float(dem['originX'])<=dx<=float(dem['originX'])+(n-1)*step and
                    float(dem['originY'])<=dy<=float(dem['originY'])+(n-1)*step):continue
            oz=elevation(dem,dx,dy)+observer_height
            hit=trace_visibility(dem,dx,dy,oz,first['az'],first['el'],
                                 radius_m=horizon_limit,step_m=step)
            sphere('5D | position perturbation %+.0f,%+.0f'%(dx,dy),status_c,
                   (dx,dy,oz+max(2,r*.25)),max(1.7,r*.24),
                   blocked_color if not hit['visible'] else observer_color)
            stress.append({'offset_m':[dx,dy],'sun_visible':hit['visible']})
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=1280;scene.render.resolution_y=720
    scene.render.resolution_percentage=80
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1.0
    scene.render.fps=24
    scene.world.use_nodes=True
    scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.009,.015,.022,1)
    scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.24
    bpy.ops.object.camera_add(location=(span*.55,-span*.71,z+span*.32))
    cam=transfer(bpy.context.object,cam_c);cam.name='CAM | three-quarter mission overview'
    look_at(cam,(0,0,z));cam.data.lens=43;cam.data.clip_end=max(span*6,20000)
    scene.camera=cam
    camera_presets=[cam]
    camera_presets.append(add_camera('CAM | overhead',(cam_c),(0,0,z+span*.95),(0,0,z),52))
    camera_presets.append(add_camera('CAM | observer horizon',cam_c,(0,-max(25,span*.006),z+observer_height+4),(0,span*.12,z+span*.018),35))
    camera_presets.append(add_camera('CAM | obstruction closeup',cam_c,(span*.11,-span*.16,z+span*.07),(0,0,z),62))
    camera_presets.append(add_camera('CAM | extreme ridge',cam_c,(-span*.08,-span*.10,z+span*.035),(span*.10,span*.05,z+span*.015),85))
    for preset in camera_presets:preset.data.clip_end=max(span*6,20000)
    bpy.ops.object.light_add(type='SUN',location=(0,0,z+50))
    light=transfer(bpy.context.object,light_c);light.name='LGT | Sun from JPL direction (unvalidated frame)'
    light.data.energy=2.0;light.data.angle=math.radians(.53)
    bpy.ops.object.light_add(type='POINT',location=(0,-span*.12,z+span*.16))
    fill=transfer(bpy.context.object,light_c);fill.name='LGT | low fill for analytical legibility'
    fill.data.energy=max(20000,span*80);fill.data.shadow_soft_size=max(50,span*.10)
    # Model time samples become a keyframe timeline. Between JPL samples Blender
    # interpolates the graphical direction only; binary visibility is not inferred there.
    skip=max(1,math.ceil(len(samples)/cfg.max_frames))
    sampled=list(enumerate(samples))[::skip]
    if sampled[-1][0]!=len(samples)-1:sampled.append((len(samples)-1,samples[-1]))
    scene.frame_start=1;scene.frame_end=len(sampled)
    evidence=[]
    for fi,(idx,row) in enumerate(sampled,1):
        scene.frame_set(fi)
        entry={'frame':fi,'source_index':idx,'time_utc':row['time']}
        for name,ray,tip in [('sun',sun_ray,sun_tip),('earth',earth_ray,earth_tip)]:
            ang=row[name]
            ray_hit=trace_visibility(dem,0,0,z+observer_height,ang['az'],ang['el'],
                    radius_m=horizon_limit,step_m=step)
            ex,ey,ez=ray_hit['point']
            # Show short, finite-range ray rather than a literal celestial distance.
            point_between(ray,start,(ex,ey,ez))
            for path in ('location','rotation_euler','scale'):ray.keyframe_insert(data_path=path,frame=fi)
            tip.location=(ex,ey,ez)
            tip.keyframe_insert(data_path='location',frame=fi)
            entry[name]={'az_deg':ang['az'],'el_deg':ang['el'],
                         'visible_within_crop':ray_hit['visible'],'samples':ray_hit['sample_count']}
        sun_vec=Vector(direction(row['sun']['az'],row['sun']['el']))
        light.rotation_euler=(-sun_vec).to_track_quat('-Z','Y').to_euler()
        light.keyframe_insert(data_path='rotation_euler',frame=fi)
        evidence.append(entry)
    for ob in (sun_ray,earth_ray,sun_tip,earth_tip,light):
        if ob.animation_data and ob.animation_data.action:
            for fcurve in getattr(ob.animation_data.action, 'fcurves', []):
                for kp in fcurve.keyframe_points:kp.interpolation='LINEAR'
    scene.frame_set(max(1,len(sampled)//2))
    scene['DATA_STATUS']=('SYNTHETIC DEM AND SKY; NOT NASA OR JPL DATA' if cfg.demo else bundle.get('validation',{}).get('status','SOURCE_BASED_UNVALIDATED'))
    scene['DATA_SOURCE_DEM']=dem.get('source','unspecified DEM')
    scene['DATA_SOURCE_LOCAL_DEM']=local_dem.get('source','not supplied') if local_dem else 'not supplied'
    scene['DATA_SOURCE_JPL']=dataset['ephemeris'].get('source','unspecified JPL')
    scene['SITE_ID']=cfg.site
    scene['FIFTH_AXIS']='3x3 observer-position perturbation scenario at the first UTC sample; not a probability'
    scene['TIME_NOTE']='Keyframe i corresponds to report JSON source_time; Blender intermediate frames are graphical interpolation only'
    scene['LIMITATION']='No DSN schedule, solar disk size, guaranteed battery power or full-disk occultations. DEM footprint limits.'
    out=Path(cfg.outdir).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    tag='DEMO' if cfg.demo else 'science'
    blend=out/f'POLARIS_X_{cfg.site}_{tag}.blend'
    glb=out/f'POLARIS_X_{cfg.site}_{tag}.glb'
    report=out/f'POLARIS_X_{cfg.site}_{tag}_metadata.json'
    manifest=out/f'POLARIS_X_{cfg.site}_{tag}_scene_manifest.json'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB')
    scene.render.image_settings.file_format='PNG'
    render_frames=sorted(set((scene.frame_start,max(scene.frame_start,(scene.frame_start+scene.frame_end)//2),scene.frame_end)))
    render_paths=[]
    for frame in render_frames:
        scene.frame_set(frame)
        render_path=out/f'POLARIS_X_{cfg.site}_{tag}_frame_{frame:03d}.png'
        scene.render.filepath=str(render_path)
        bpy.ops.render.render(write_still=True)
        render_paths.append(str(render_path))
    # Restore the saved scene at its middle evidence frame after rendering.
    scene.frame_set(max(1,len(sampled)//2))
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report.write_text(json.dumps({'site':cfg.site,'n':n,'original_spacing_m':step,
      'mesh_vertices':len(verts),'sun_earth_samples':evidence,'stress_first_utc_sample':stress,
      'source_dem':dem.get('source'),'source_jpl':dataset['ephemeris'].get('source'),'is_illustrative_demo':cfg.demo,
      'limitations':['NASA and JPL lunar coordinate frames require independent alignment checks',
          'finite DEM footprint','point-center visibility only','between-keyframe visual interpolation only',
          'uncertainty grid is deterministic test cases, not mission success probability']},indent=2))
    manifest.write_text(json.dumps({
      'schema':'POLARIS-X-scene-manifest-v1','site':cfg.site,'demo':cfg.demo,
      'validation_status':'DEMO_ONLY' if cfg.demo else bundle.get('validation',{}).get('status','SOURCE_BASED_UNVALIDATED'),
      'blender_version':bpy.app.version_string,'units':'1 Blender unit = 1 metre',
      'local_axes':{'x':'east','y':'north','z':'elevation/up'},
      'vertical_exaggeration':1.0,'source_dem':dem.get('source'),
      'source_local_dem':local_dem.get('source') if local_dem else None,
      'frame_to_utc':evidence,'active_camera':scene.camera.name,
      'camera_presets':[camera.name for camera in camera_presets],
      'renders':render_paths,
      'assets':{
        'blend':{'path':str(blend),'bytes':blend.stat().st_size,'sha256':file_sha256(blend)},
        'glb':{'path':str(glb),'bytes':glb.stat().st_size,'sha256':file_sha256(glb)}},
      'limitations':['finite regional DEM horizon','target-center visibility only',
        'local 5m mesh is visual context; current ray solver uses the regional DEM',
        'intermediate Blender frames are graphical interpolation']},indent=2))
    print('BLENDER_SOURCE',blend,'GLB',glb,'REPORT',report,'MANIFEST',manifest)
    print('CAUTION: visualized scientific inputs are not independently validated.')

if __name__=='__main__':main()
