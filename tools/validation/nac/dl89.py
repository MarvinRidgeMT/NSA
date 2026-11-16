from remotezip import RemoteZip
import json, os, sys
for reg,name,d in ((8,'Peak_Near_Shackleton','nac8'),(9,'deGerlache_Rim','nac9')):
    url=f"https://zenodo.org/api/records/17954508/files/A3CLR22_{reg}_{name}.zip/content"
    cams=[]
    with RemoteZip(url) as z:
        infos=z.infolist()
        tifs={i.filename.split('_005_')[-1][:-4]:(i.filename,i.file_size) for i in infos if '/LROC-NAC-maps/' in i.filename and i.filename.endswith('.tif')}
        for i in infos:
            if '/LROC-NAC-adjust/' in i.filename and i.filename.endswith('.json'):
                t=z.read(i.filename).decode(); j=json.loads(t[t.index('{'):]); img=i.filename.split('_005_')[-1][:-5]
                if img in tifs: cams.append(dict(img=img,et=j['m_centerEphemerisTime'],sun=j['m_sunPosition'][len(j['m_sunPosition'])//2*0:3],tif=tifs[img][0],bytes=tifs[img][1]))
        json.dump(cams,open(f'{d}_cams.json','w'))
        print(reg,'cams',len(cams),flush=True)
        for k,c in enumerate(cams):
            p=f"{d}/{c['img']}.tif"
            if os.path.exists(p) and os.path.getsize(p)==c['bytes']: continue
            open(p,'wb').write(z.read(c['tif'])); print(reg,k,flush=True)
    print('REGION DONE',reg,flush=True)
