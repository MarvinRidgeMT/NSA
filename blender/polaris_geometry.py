"""Geometry-only lunar visibility helpers. No Blender dependency.

Local axes: X east, Y north, Z up (metres). Azimuth clockwise from north.
This finite-DEM model deliberately does not claim full lunar line-of-sight.
"""
import math

MOON_RADIUS_M = 1_737_400.0


def validate_dem(dem):
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
    step_m=step_m or float(dem['spacing'])
    az=math.radians(az_deg);east=math.sin(az);north=math.cos(az)
    highest=-90.0;blocking_at=None; evaluated=0
    d=max(1.0,step_m)
    while d<=radius_m:
        xx=x+east*d;yy=y+north*d
        if not inside(dem,xx,yy):break
        terrain_z=elevation(dem,xx,yy)
        curvature_drop=d*d/(2*MOON_RADIUS_M)
        angle=math.degrees(math.atan2(terrain_z-observer_z-curvature_drop,d))
        if angle>highest: highest=angle;blocking_at=d
        evaluated+=1;d+=step_m
    return {'angle_deg':highest,'critical_distance_m':blocking_at,'samples':evaluated,
            'footprint_limited':d<=radius_m}


def trace_visibility(dem,x,y,observer_z,az_deg,el_deg,radius_m=12000,step_m=None):
    """First modeled obstruction; source/azimuth convention must be validated."""
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
        apparent_terrain=sample_z-d*d/(2*MOON_RADIUS_M)
        line_z=observer_z+d*math.tan(math.radians(el_deg))
        n+=1
        if apparent_terrain >= line_z:
            return {'visible':False,'first_hit_m':d,'point':[xx,yy,line_z],
                    'sample_count':n,'limited':True}
        d+=step_m
    last_d=min(d-step_m,radius_m)
    last_d=max(last_d,0)
    return {'visible':True,'first_hit_m':None,
            'point':[x+dx*last_d,y+dy*last_d,observer_z+math.tan(math.radians(el_deg))*last_d],
            'sample_count':n,'limited':True}
