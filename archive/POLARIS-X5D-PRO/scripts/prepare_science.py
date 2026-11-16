#!/usr/bin/env python3
"""Create source-labelled NASA LOLA + JPL Horizons data for POLARIS X.

This is a data-preparation aid, NOT an independently validated frame-conversion pipeline.
It uses the NASA PGDA south-polar 80m COG and two separate Horizons requests
for apparent Sun/Earth angles. Review the output source/projection metadata.

Examples:
 python3 -m pip install rasterio requests numpy
 python3 scripts/prepare_science.py --sites connecting shackleton
 python3 scripts/prepare_science.py --sites connecting --dem-file /path/to/LDEM_80S_80MPP_ADJ.TIF
"""
import argparse
import datetime as dt
import json
import math
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

R = 1737400.0
NASA_URL = 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF'
HORIZONS_URL = 'https://ssd.jpl.nasa.gov/api/horizons.api'
SITES = {
    'connecting':(-89.4632,-137.4900,'Connecting Ridge / Site01'),
    'shackleton':(-89.7668,-171.8700,'Shackleton Rim / Site04'),
    'peak':(-88.8110,123.6901,'Peak Near Shackleton / Site07'),
    'gerlache':(-88.6834,-67.9321,'de Gerlache Rim / Site11'),
}

def xy_from_latlon(lat, lon):
    rho = 2 * R * math.tan(math.pi / 4 + math.radians(lat) / 2)
    return rho * math.sin(math.radians(lon)), rho * math.cos(math.radians(lon))

def read_dem(dem_file, site_id, n):
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    lat, lon, _ = SITES[site_id]
    x0,y0=xy_from_latlon(lat,lon)
    path = str(dem_file) if dem_file else '/vsicurl/' + NASA_URL
    if not dem_file:
        print('Opening NASA cloud-optimized GeoTIFF via GDAL HTTP range requests (internet needed)…', flush=True)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.TIF',GDAL_HTTP_MAX_RETRY='3',GDAL_HTTP_RETRY_DELAY='1'):
        with rasterio.open(path) as ds:
            print(f'Input DEM: {ds.width} x {ds.height}; CRS={ds.crs}; transform={ds.transform}')
            if not (ds.transform.a > 0 and ds.transform.e < 0 and abs(abs(ds.transform.a)-abs(ds.transform.e))<1e-3):
                raise ValueError('Expected unrotated equally spaced south-polar GeoTIFF grid')
            row,col=ds.index(x0,y0)
            half=n//2
            win=Window(col-half,row-half,n,n)
            if win.col_off<0 or win.row_off<0 or win.col_off+n>ds.width or win.row_off+n>ds.height:
                raise ValueError('Site not fully covered by chosen NASA DEM crop')
            a=ds.read(1,window=win,masked=True).astype('float64')
            if np.ma.is_masked(a):
                mask=np.ma.getmaskarray(a)
                if np.any(mask):raise ValueError(f'NASA DEM crop has {int(np.count_nonzero(mask))} nodata pixels; do not invent heights')
            data=np.flipud(np.asarray(a)).copy()
            if not np.all(np.isfinite(data)):raise ValueError('NASA DEM contains non-finite values')
            # Find true center of southwest pixel and express crop relative to observer site
            lowx, lowy = rasterio.transform.xy(ds.transform, row+half, col-half, offset='center')
            source = str(dem_file) if dem_file else NASA_URL
            return {'kind':'nasa','siteId':site_id,'lat':lat,'lon':lon,'n':n,'spacing':float(abs(ds.transform.a)),
                'originX':float(lowx-x0),'originY':float(lowy-y0),'values':data.flatten().round(3).tolist(),
                'source':'NASA PGDA product 90 / LOLA 80m COG: '+source,
                'datum':'NASA PGDA product describes MOON_ME / DE421 south polar stereographic; verify CRS and Heights before comparing to Horizons',
                'metadata':{'crs':str(ds.crs),'transform':[float(v) for v in list(ds.transform)[:6]],
                  'row':int(row),'column':int(col),'cropSizePixels':n,'coordinateProjection':'polar stereographic R=1737400 m; planetocentric lat/lon assumed',
                  'observerPixelOffset':{'x_m':float(lowx-x0),'y_m':float(lowy-y0)}}}

def parse_csv_response(content):
    if '$$SOE' not in content or '$$EOE' not in content:
        raise ValueError('Horizons response lacks ephemeris markers. Response opening:\n'+content[:1000])
    lines=content.split('$$SOE',1)[1].split('$$EOE',1)[0].splitlines()
    samples=[]
    for raw in lines:
        line=raw.strip()
        if not line:continue
        match=re.search(r'(\d{4}-[A-Za-z]{3}-\d\d \d\d:\d\d(?::\d\d)?)',line)
        if not match:continue
        t=dt.datetime.strptime(match.group(1),'%Y-%b-%d %H:%M:%S' if match.group(1).count(':')==2 else '%Y-%b-%d %H:%M')
        later=line[match.end():]
        # QUANTITIES=4 and CSV_FORMAT=YES yields two angle columns after optional presence flags.
        num=[]
        for token in later.split(','):
            token=token.strip()
            try:num.append(float(token))
            except ValueError:pass
        if len(num)!=2:
            raise ValueError(f'Expected exactly 2 azimuth/elevation fields, received {num} in row: {line[:150]}')
        az,el=num
        if not (0<=az<=360 and -90<=el<=90):raise ValueError('Invalid Horizons apparent azimuth/elevation values')
        samples.append({'time':t.replace(tzinfo=dt.timezone.utc).isoformat().replace('+00:00','Z'),'az':az,'el':el})
    if len(samples)<2:raise ValueError('Not enough numeric JPL rows, cannot interpolate')
    return samples

def get_ephemeris(site_id,start,days,step_h=1):
    import requests
    lat,lon,_=SITES[site_id]
    from_date=dt.datetime.fromisoformat(start.replace('Z','+00:00'))
    if from_date.tzinfo is None:from_date=from_date.replace(tzinfo=dt.timezone.utc)
    to_date=from_date+dt.timedelta(days=days)
    result={}
    for name,command in [('sun','10'),('earth','399')]:
        args={'format':'text','COMMAND':f"'{command}'",'OBJ_DATA':"'NO'",'MAKE_EPHEM':"'YES'",'EPHEM_TYPE':"'OBSERVER'",'CENTER':"'coord@301'",'COORD_TYPE':"'GEODETIC'",
          'SITE_COORD':f"'{(lon%360):.7f},{lat:.7f},0'",'START_TIME':f"'{from_date.strftime('%Y-%m-%d %H:%M')}'",
          'STOP_TIME':f"'{to_date.strftime('%Y-%m-%d %H:%M')}'",'STEP_SIZE':f"'{step_h} h'",'QUANTITIES':"'4'",'CSV_FORMAT':"'YES'",'TIME_TYPE':"'UT'",'ANG_FORMAT':"'DEG'"}
        print(f'Querying JPL Horizons {name} for {site_id}…',flush=True)
        resp=requests.get(HORIZONS_URL,params=args,timeout=90)
        resp.raise_for_status()
        result[name]=parse_csv_response(resp.text)
        result[name+'QueryURL']=resp.url
    a,b=result['sun'],result['earth']
    pair={x['time']:x for x in b}
    rows=[{'time':v['time'],'sun':{'az':v['az'],'el':v['el']},'earth':{'az':pair[v['time']]['az'],'el':pair[v['time']]['el']}} for v in a if v['time'] in pair]
    if len(rows)<2:raise ValueError('Sun and Earth JPL sample timestamps did not match')
    return {'source':'NASA/JPL Horizons API, QUANTITIES=4, geodetic coord@301, UTC, 1h, apparent AZ & EL (Moon frame compatibility requires validation)',
            'sampling':f'{step_h} h','sunQuery':result['sunQueryURL'],'earthQuery':result['earthQueryURL'],'samples':rows}

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sites',nargs='+',choices=list(SITES),default=['connecting','shackleton'])
    p.add_argument('--dem-file',help='Optional already downloaded NASA 80m COG TIF path')
    p.add_argument('--pixels',type=int,default=401,help='Odd crop dimension; default 401 x 401 ~32 km')
    p.add_argument('--start',default='2026-11-14T14:00:00Z')
    p.add_argument('--days',type=int,default=14)
    p.add_argument('--output',default='data/nasa-jpl-science-bundle.json')
    args=p.parse_args()
    if args.pixels<51 or args.pixels>1201 or args.pixels%2!=1:p.error('--pixels must be odd between 51 and 1201')
    if args.days<1 or args.days>90:p.error('--days must be 1–90')
    datasets=[]
    for site_id in args.sites:
        dem=read_dem(args.dem_file,site_id,args.pixels)
        eph=get_ephemeris(site_id,args.start,args.days)
        datasets.append({'siteId':site_id,'dem':dem,'ephemeris':eph})
    bundle={'format':'POLARIS-X5D-v1','generatedUTC':dt.datetime.now(dt.timezone.utc).isoformat(),'sources':{'NASA_DEM':NASA_URL,'JPL_Horizons':HORIZONS_URL,'model':'lunar polar local-horizon sensitivity prototype; not a certified mission model'},'datasets':datasets}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(bundle,separators=(',',':')))
    print(f'Wrote {out} ({out.stat().st_size/1048576:.1f} MiB). Import this JSON inside the POLARIS X sidebar.')
    print('IMPORTANT: Independently verify topographic projection, datum/frame and a reference Horizons direction before scientific claims.')
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('\nDATA PREPARATION FAILED:',str(exc),file=sys.stderr)
        print('Try --dem-file with a locally downloaded LDEM_80S_80MPP_ADJ.TIF or inspect JPL query output.',file=sys.stderr)
        sys.exit(1)
