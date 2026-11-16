import json, os, re, time
from remotezip import RemoteZip
url = "https://zenodo.org/api/records/17954508/files/A3CLR22_8_Peak_Near_Shackleton.zip/content"
os.makedirs('nac8', exist_ok=True)
with RemoteZip(url) as z:
    infos = [i for i in z.infolist() if 'LROC-NAC-maps/' in i.filename and i.filename.endswith('.tif')]
    for k, i in enumerate(infos):
        out = 'nac8/' + os.path.basename(i.filename)
        for attempt in range(4):
            if os.path.exists(out) and os.path.getsize(out) == i.file_size: break
            try:
                open(out + '.part', 'wb').write(z.read(i.filename)); os.replace(out + '.part', out)
            except Exception as e:
                print('retry', out, e, flush=True); time.sleep(3)
        print(8, k, os.path.getsize(out) == i.file_size, flush=True)
    json.dump([{'img': re.search(r'_(M\d+[LR]E)\.tif', i.filename).group(1), 'tif': i.filename, 'tif_bytes': i.file_size} for i in infos], open('nac8_imgs.json', 'w'))
print('REGION DONE 8', flush=True)
