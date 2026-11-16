#!/usr/bin/env python3
"""Build the website's Blender showcase gallery (web/public/showcase/) from blender/output/*_showcase_manifest.json.

Copies each showcase render as WebP (quality 88, 1920 px wide) and writes index.html + gallery.json. The page states for every
image what it shows, the bundle UTC sample, the Sun azimuth/elevation and the ray states read from the bundle, and that terrain
detail beyond the DEM (boulders, micro-relief, albedo variation) is synthetic. Run after showcase_render.command:
    python tools/showcase/build_gallery.py
"""
import hashlib
import html
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'blender' / 'output'
OUT = ROOT / 'web' / 'public' / 'showcase'
NAMES = {'site01_roi6': 'Connecting Ridge (Site01 ROI6)', 'site04_roi3': 'Shackleton Rim (Site04 ROI3)'}
VIEW = {
    'aerial': 'Aerial view across the Sun azimuth',
    'ground': 'Ground level, 1.7 m eye height, about 50 m from the mast on the Sun side, looking down-Sun',
    'low_sun': 'Low camera on the Sun side, grazing light',
    'obstruction_mast1m': 'Sun transition hour, 1 m mast: the bundle ray ends at the first terrain hit',
    'obstruction_mast10m': 'Same hour, 10 m mast: the bundle ray clears the terrain',
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    for man_path in sorted(SRC.glob('POLARIS_X_*_bundlev2_showcase_manifest.json')):
        man = json.loads(man_path.read_text())
        site = man['site']
        for r in man['renders']:
            png = SRC / r['png']
            if not png.is_file():
                continue
            webp = OUT / (png.stem + '.webp')
            im = Image.open(png).convert('RGB')
            if im.width > 1920:
                im = im.resize((1920, round(im.height * 1920 / im.width)), Image.LANCZOS)
            im.save(webp, 'WEBP', quality=88, method=6)
            rays = r.get('rays') or {}
            ray_txt = ', '.join(f"{t}: {v['state']}" + (f" (first hit {v['firstHitM']:g} m)" if v.get('firstHitM') is not None else '') for t, v in rays.items())
            if r.get('sunRay'):
                v = r['sunRay']
                ray_txt = f"Sun at {r['mastM']:g} m mast: {v['state']}" + (f" (first hit {v['firstHitM']:g} m)" if v.get('firstHitM') is not None else '') + f", bundle margin {r['bundleMarginDeg']:+.2f}°"
            items.append({'site': site, 'siteName': NAMES.get(site, site), 'label': r['label'], 'title': VIEW.get(r['label'], r['label']),
                          'file': webp.name, 'sha256': hashlib.sha256(webp.read_bytes()).hexdigest(), 'utc': r['utc'],
                          'sunAz': r['sun']['az'], 'sunEl': r['sun']['el'], 'rays': ray_txt, 'sourcePng': r['png'], 'sourcePngSha256': r['pngSha256'],
                          'status': man.get('status'), 'boulders': man['syntheticDetail']['boulders']})
    (OUT / 'gallery.json').write_text(json.dumps({'schema': 'polaris-showcase-gallery-v1', 'items': items}, indent=1))
    cards = []
    for it in items:
        cards.append(f'''<figure>
  <img src="{html.escape(it['file'])}" alt="{html.escape(it['siteName'] + ': ' + it['title'])}" loading="lazy" width="1920" height="1080">
  <figcaption><b>{html.escape(it['siteName'])}</b> · {html.escape(it['title'])}<br>
  <span>{html.escape(it['utc'])} · Sun az {it['sunAz']:.1f}°, el {it['sunEl']:+.2f}° · {html.escape(it['rays'])}</span></figcaption>
</figure>''')
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark"><title>POLARIS X · Blender showcase</title>
<style>
:root {{ --bg:#050505; --fg:#e9e4da; --ash:#9a958c; --line:#2a2826; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; padding:24px max(16px, env(safe-area-inset-left)); }}
header {{ max-width:1200px; margin:0 auto 24px; }} h1 {{ font-weight:400; font-size:30px; margin:0 0 6px; }}
p {{ color:var(--ash); max-width:72ch; margin:6px 0; }} a {{ color:var(--fg); }}
.badge {{ display:inline-block; border:1px solid var(--line); padding:2px 8px; font:500 11px ui-monospace, monospace; letter-spacing:.08em; }}
main {{ max-width:1200px; margin:0 auto; display:grid; gap:28px; }}
figure {{ margin:0; }} img {{ width:100%; height:auto; display:block; background:#000; }}
figcaption {{ margin-top:8px; font-size:14px; }} figcaption span {{ color:var(--ash); font:12px ui-monospace, monospace; }}
</style></head><body>
<header><h1>POLARIS X · Blender showcase</h1>
<p><span class="badge">SOURCE-BASED · UNVALIDATED</span></p>
<p>Offline Cycles renders of the two hero sites, built from the same bundle the viewer reads. Terrain is NASA PGDA 78 (5 m LOLA) with the
NASA GSFC shape-from-shading relief as display surface where it exists, NASA PGDA 90 (80 m) around it. Sun direction, rays and
visible/blocked states come from the bundle (JPL Horizons). <b>Boulders, regolith albedo variation and sub-5 m relief are synthetic</b>
presentation; no synthetic boulder lies within 150 m of the landing point. Renders are pictures, not measurements.</p>
<p><a href="../">Open the interactive viewer</a></p></header>
<main>
{chr(10).join(cards) if cards else '<p>No showcase renders yet: run showcase_render.command, then tools/showcase/build_gallery.py.</p>'}
</main></body></html>
'''
    (OUT / 'index.html').write_text(page)
    print(f'gallery: {len(items)} images -> {OUT}')


if __name__ == '__main__':
    main()
