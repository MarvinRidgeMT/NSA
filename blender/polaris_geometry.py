"""Geometry-only lunar visibility helpers. No Blender dependency.

Local axes: X east, Y north, Z up (metres). Azimuth clockwise from north.
This finite-DEM model deliberately does not claim full lunar line-of-sight.
"""
import math

MOON_RADIUS_M = 1_737_400.0


def norm360(value):
    return value % 360.0


def curvature_drop(distance_m, radius_m=MOON_RADIUS_M):
    """Exact spherical surface drop below a local tangent plane.

    The finite DEM uses local east/north distances.  This correction assumes a
    spherical Moon and is therefore a geometry model, not a vertical-datum
    transformation.
    """
    d = abs(float(distance_m))
    if d >= radius_m:
        raise ValueError('Tangent-plane distance must be smaller than Moon radius')
    return radius_m - math.sqrt(radius_m * radius_m - d * d)


def cell_id(dem, x, y):
    """Nearest containing raster cell in the canonical south-to-north grid."""
    n = int(dem['n']); step = float(dem['spacing'])
    column = math.floor((x-float(dem['originX']))/step)
    row = math.floor((y-float(dem['originY']))/step)
    if not (0 <= column < n and 0 <= row < n):
        return None
    return {'row': row, 'column': column, 'flat_index': row*n+column}


def reject_visual_layer(dem):
    """Solver guard (visual-layer contract): display rasters are never terrain.

    A visual layer (albedo/morphology image) is flagged status 'VISUAL' / numericalAuthority False and carries an
    `artifact` instead of elevation `values`. Raise before any height is read from such an object.
    """
    if isinstance(dem, dict) and (dem.get('status') == 'VISUAL' or dem.get('numericalAuthority') is False
                                  or (isinstance(dem.get('artifact'), dict) and 'values' not in dem)):
        raise ValueError('VISUAL_LAYER_AS_DEM: a visual layer cannot be used as solver terrain')
    return dem


def validate_dem(dem):
    reject_visual_layer(dem)
    n = int(dem['n'])
    if n < 3 or len(dem['values']) != n*n: raise ValueError('DEM array must be n x n, n >= 3')
    if float(dem['spacing']) <= 0: raise ValueError('DEM spacing must be positive')
    if not all(math.isfinite(float(v)) for v in dem['values']): raise ValueError('DEM contains non-finite heights')
    return n


def elevation(dem, x, y):
    """Bilinear raster sample. Reject out-of-footprint queries rather than extrapolating."""
    n=int(dem['n']); step=float(dem['spacing'])
    u=(x-float(dem['originX']))/step
    v=(y-float(dem['originY']))/step
    if not(0<=u<=n-1 and 0<=v<=n-1): raise ValueError('Sample outside DEM footprint')
    i=min(int(u),n-2); j=min(int(v),n-2)
    a=u-i;b=v-j
    z=lambda col,row:float(dem['values'][row*n+col])
    return ((1-a)*(1-b)*z(i,j) + a*(1-b)*z(i+1,j)
            +(1-a)*b*z(i,j+1)+a*b*z(i+1,j+1))


def direction(az_deg, el_deg):
    a=math.radians(az_deg);e=math.radians(el_deg)
    return (math.sin(a)*math.cos(e), math.cos(a)*math.cos(e), math.sin(e))


def inside(dem,x,y):
    xmax=float(dem['originX'])+(int(dem['n'])-1)*float(dem['spacing'])
    ymax=float(dem['originY'])+(int(dem['n'])-1)*float(dem['spacing'])
    return float(dem['originX'])<=x<=xmax and float(dem['originY'])<=y<=ymax


def terrain_horizon(dem, x, y, observer_z, az_deg, radius_m=12000, step_m=None):
    """Highest terrain apparent elevation, in degrees, to the edge of available DEM.

    This is an approximate spherical drop correction. Near horizon crossings a
    Moon-centered 3D ray solver is more appropriate for high-precision studies.
    """
    reject_visual_layer(dem)
    step_m=step_m or float(dem['spacing'])
    az=math.radians(az_deg);east=math.sin(az);north=math.cos(az)
    highest=-90.0;blocking_at=None; evaluated=0
    d=max(1.0,step_m)
    while d<=radius_m:
        xx=x+east*d;yy=y+north*d
        if not inside(dem,xx,yy):break
        terrain_z=elevation(dem,xx,yy)
        drop=curvature_drop(d)
        angle=math.degrees(math.atan2(terrain_z-observer_z-drop,d))
        if angle>highest:
            highest=angle;blocking_at=d;blocking_point=(xx,yy,terrain_z);blocking_cell=cell_id(dem,xx,yy)
        evaluated+=1;d+=step_m
    return {'angle_deg':highest,'critical_distance_m':blocking_at,'samples':evaluated,
            'critical_point':blocking_point if blocking_at is not None else None,
            'critical_cell':blocking_cell if blocking_at is not None else None,
            'footprint_limited':d<=radius_m,
            'termination':'dem_edge' if d<=radius_m else 'requested_radius'}


def trace_visibility(dem,x,y,observer_z,az_deg,el_deg,radius_m=12000,step_m=None):
    """First modeled obstruction; source/azimuth convention must be validated."""
    reject_visual_layer(dem)
    step_m=step_m or float(dem['spacing'])
    a=math.radians(az_deg)
    dx,dy=math.sin(a),math.cos(a)
    d=max(1.0,step_m)
    n=0
    while d<=radius_m:
        xx=x+dx*d;yy=y+dy*d
        if not inside(dem,xx,yy): break
        sample_z=elevation(dem,xx,yy)
        # curvature correction in local tangent-plane geometry
        apparent_terrain=sample_z-curvature_drop(d)
        line_z=observer_z+d*math.tan(math.radians(el_deg))
        n+=1
        if apparent_terrain >= line_z:
            return {'visible':False,'first_hit_m':d,'point':[xx,yy,line_z],
                    'terrain_elevation_m':sample_z,'clearance_m':line_z-apparent_terrain,
                    'blocking_cell':cell_id(dem,xx,yy),'sample_count':n,
                    'footprint_limited':True,'termination':'first_hit'}
        d+=step_m
    last_d=min(d-step_m,radius_m)
    last_d=max(last_d,0)
    return {'visible':True,'first_hit_m':None,
            'point':[x+dx*last_d,y+dy*last_d,observer_z+math.tan(math.radians(el_deg))*last_d],
            'terrain_elevation_m':None,'clearance_m':None,'blocking_cell':None,
            'sample_count':n,'footprint_limited':d<=radius_m,
            'termination':'dem_edge' if d<=radius_m else 'requested_radius'}
