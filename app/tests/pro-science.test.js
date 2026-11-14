import test from 'node:test';
import assert from 'node:assert/strict';
import {SITES,makeDemoTerrain,terrainRayProfile,windowEvents,evaluateTimeline,stressTest,compareSites,ephemerisAt} from '../src/science.js';
const s=SITES[0],d=makeDemoTerrain(s,61,150);

test('Sun and Earth angular objects are not overwritten by visibility flags',()=>{
 const out=evaluateTimeline(s,d,null,{durationH:24,stepH:1});
 assert.equal(typeof out.rows[0].sun,'object');
 assert.equal(typeof out.rows[0].sunVisible,'boolean');
 assert.ok(Number.isFinite(out.rows[0].sun.az));
 assert.equal(out.metrics.sunPct,100*out.rows.filter(r=>r.sunVisible).length/out.rows.length);
});
test('synthetic east ridge blocks a low ray at the predicted azimuth',()=>{
 const n=61,spacing=100,values=Array(n*n).fill(0);
 for(let j=0;j<n;j++)for(let i=42;i<46;i++)values[j*n+i]=300;
 const dem={n,spacing,originX:-3000,originY:-3000,values,kind:'illustrative'};
 const low=terrainRayProfile(dem,{az:90,el:1,stepM:60,maxDistanceM:2600});
 const high=terrainRayProfile(dem,{az:90,el:40,stepM:60,maxDistanceM:2600});
 assert.ok(low.firstHit && low.firstHit.d>1000 && low.firstHit.d<1700);
 assert.equal(high.visible,true);
});
test('stress-test nominal uses the currently selected observer location and terrain scenario',()=>{
 const opts={start:'2026-11-14T14:00:00Z',durationH:18,stepH:1,ox:300,oy:-300,height:4,uncertainty:25};
 const nominal=evaluateTimeline(s,d,null,opts).metrics,stress=stressTest(s,d,null,opts)[0];
 assert.ok(stress.valid);assert.equal(stress.sunPct,nominal.sunPct);assert.equal(stress.darkH,nominal.darkH);
});
test('imported ephemerides never secretly fall back to demonstration sky outside their period',()=>{
 const ep={samples:[
 {time:'2026-11-14T00:00:00Z',sun:{az:1,el:2},earth:{az:3,el:4}},
 {time:'2026-11-14T02:00:00Z',sun:{az:2,el:3},earth:{az:4,el:5}}]};
 assert.throws(()=>ephemerisAt('2026-11-15T00:00:00Z',s,ep),/outside imported JPL/);
 const tests=stressTest(s,d,ep,{start:'2026-11-14T00:00:00Z',durationH:2,stepH:1});
 assert.equal(tests[0].valid,true);assert.equal(tests.at(-1).valid,false);
});
test('window events form complete non-overlapping mission-time segmentation',()=>{
 const rows=[
 {time:'2026-11-14T00:00:00Z',sunVisible:true,earthVisible:false,both:false},
 {time:'2026-11-14T01:00:00Z',sunVisible:false,earthVisible:false,both:false},
 {time:'2026-11-14T02:00:00Z',sunVisible:false,earthVisible:true,both:false},
 ];
 const events=windowEvents(rows);
 const sun=events.filter(e=>e.target==='sunVisible');assert.equal(sun.length,2);assert.equal(sun[0].durationH,1);assert.equal(sun[1].durationH,2);
});
test('four-site comparison retains independent data-mode caveats',()=>{
 const a=compareSites(SITES,site=>({dem:makeDemoTerrain(site,31,240),ephem:null}),{durationH:8,stepH:1});
 assert.equal(a.length,4);assert.ok(a.every(x=>x.valid));assert.ok(a.every(x=>x.mode!=='nasa+jpl'));
});
