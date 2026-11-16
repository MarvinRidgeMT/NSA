import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {
  ephemerisAt,
  horizonAt,
  horizonProfile,
  terrainRayProfile,
} from '../src/science.js';

const bundlePath=fileURLToPath(new URL('../data/polaris-source-site01-2026-11-14-v2.json',import.meta.url));
const bundle=JSON.parse(fs.readFileSync(bundlePath,'utf8'));
const dataset=bundle.datasets.find(item=>item.siteId==='connecting');
const timestamp='2026-11-14T14:00:00Z';

function targetResult(dem,target){
 const horizon=horizonProfile(dem,0,0,2,0);
 const skyline=horizonAt(horizon,target.az);
 const ray=terrainRayProfile(dem,{height:2,az:target.az,el:target.el,maxDistanceM:horizon.reachM});
 return {horizon,skyline,margin:target.el-skyline,ray};
}

test('Site01 2026-11-14T14:00Z source case preserves immutable provenance',()=>{
 assert.equal(bundle.validation.status,'SOURCE_BASED_UNVALIDATED');
 assert.equal(dataset.dem.cropValuesSha256,'d27c5aa679cd00ffee0a95ce36e0049b3189b477a6e14efb941eecac92d73b5d');
 assert.equal(dataset.localDem.sourceSha256,'3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e');
 assert.equal(dataset.ephemeris.records[0].responseSha256,'6346b02074c2711eec549045e219e58b24a8dd85f656c10253158749da7204be');
 assert.equal(dataset.ephemeris.records[1].responseSha256,'65a2c8eeee12a23f43bac4d0f9d0d01ae9cdc881a483d1003abd6dbfa4db7c81');
});

test('Site01 exact source sample uses local ENU rotated into the south-polar raster grid',()=>{
 const sky=ephemerisAt(timestamp,dataset.site,dataset.ephemeris);
 assert.ok(Math.abs(sky.sun.az-256.984524)<1e-9);
 assert.ok(Math.abs(sky.sun.el-1.435750)<1e-9);
 assert.ok(Math.abs(sky.earth.az-135.424493)<1e-9);
 assert.ok(Math.abs(sky.earth.el-(-4.411757))<1e-9);

 const sun=targetResult(dataset.dem,sky.sun);
 const earth=targetResult(dataset.dem,sky.earth);
 assert.equal(sun.horizon.frame,'derived-from-longitude');
 assert.ok(Math.abs(sun.skyline-(-4.224789967971033))<1e-9);
 assert.ok(Math.abs(sun.margin-5.660539967971033)<1e-9);
 assert.equal(sun.ray.firstHit,null);
 assert.ok(Math.abs(earth.skyline-1.1260756766224513)<1e-9);
 assert.ok(Math.abs(earth.margin-(-5.537832676622451))<1e-9);
 assert.equal(earth.ray.firstHit.d,70);
 assert.ok(Math.abs(earth.ray.firstHit.clearance-(-6.86467528245953))<1e-9);
});

test('legacy unrotated grid reproduces the reversed screenshot states and remains rejected',()=>{
 const sky=ephemerisAt(timestamp,dataset.site,dataset.ephemeris);
 const legacyDem={...dataset.dem};
 delete legacyDem.longitudeEastDeg;
 delete legacyDem.localNorthInGrid;
 delete legacyDem.localEastInGrid;
 const sun=targetResult(legacyDem,sky.sun);
 const earth=targetResult(legacyDem,sky.earth);
 assert.equal(sun.horizon.frame,'local-enu');
 assert.ok(Math.abs(sun.margin-(-0.423732497230892))<1e-9);
 assert.ok(Math.abs(earth.margin-0.27591529280770644)<1e-9);
 assert.equal(sun.margin>0,false);
 assert.equal(earth.margin>0,true);
});
