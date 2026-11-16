import spiceypy as sp, numpy as np, json, math
R=1737.4
for k in ['naif0012.tls','de440s.bsp','moon_pa_de440_200625.bpc','moon_de440_250416.tf','pck00011.tpc']: sp.furnsh('spice/'+k)
def ps_to_lonlat(x,y):
    rho=np.hypot(x,y); c=2*np.arctan(rho/(2*1737400.0)); lat=-(np.pi/2-c); lon=np.arctan2(x,y)  # south polar stereo: x=rho sin(lon), y=rho cos(lon)
    return np.degrees(lon), np.degrees(lat)
def lonlat_to_ps(lon,lat):
    lon=np.radians(lon); c=np.pi/2+np.radians(lat); rho=2*1737400.0*np.tan(c/2); return rho*np.sin(lon), rho*np.cos(lon)
def up_east_north(lon,lat):
    lo,la=math.radians(lon),math.radians(lat)
    up=np.array([math.cos(la)*math.cos(lo),math.cos(la)*math.sin(lo),math.sin(la)])
    east=np.array([-math.sin(lo),math.cos(lo),0.0]); north=np.cross(up,east); return up,east,north
def sun_azel(et, lon, lat, h=0.0, frame='MOON_ME'):
    up,e,n=up_east_north(lon,lat); site=up*(R+h/1000)
    s,_=sp.spkpos('SUN',et,frame,'LT+S','MOON'); v=np.array(s)-site; v/=np.linalg.norm(v)
    el=math.degrees(math.asin(v@up)); az=math.degrees(math.atan2(v@e,v@n))%360; return az,el,v
