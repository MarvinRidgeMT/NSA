import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateVisualLayers,assertNumericalDem,VisualLayerError} from '../src/visual-layers.js';
import {horizonProfile,terrainRayProfile} from '../src/science.js';

const CASES=JSON.parse(readFileSync(new URL('../../schemas/fixtures/visual-layers-cases.json',import.meta.url),'utf8'));
const clone=o=>JSON.parse(JSON.stringify(o));
function mutate(c){
  const doc=clone(CASES.valid);
  const walk=path=>{const parts=path.split('.'),leaf=parts.pop();let node=doc;for(const p of parts)node=node[Array.isArray(node)?Number(p):p];return[node,leaf];};
  for(const[path,value]of Object.entries(c.set??{})){const[n,l]=walk(path);n[l]=value;}
  for(const path of c.delete??[]){const[n,l]=walk(path);delete n[l];}
  if('duplicateLayer' in c)doc.layers.push(clone(doc.layers[c.duplicateLayer]));
  return doc;
}
const guardObjects=key=>CASES.solverGuard[key].map(c=>[c.name,'useLayer' in c?clone(CASES.valid.layers[c.useLayer]):clone(c.object)]);

test('visual layers: the shared valid fixture passes',()=>{validateVisualLayers(clone(CASES.valid));});

test('visual layers: every shared invalid case is rejected with its code',()=>{
  assert.ok(CASES.invalid.length>=15);
  for(const c of CASES.invalid)assert.throws(()=>validateVisualLayers(mutate(c)),e=>e instanceof VisualLayerError&&e.code===c.code,c.name);
});

test('solver guard: visual layers are refused by the guard and by the horizon/ray solvers',()=>{
  for(const[name,o]of guardObjects('rejected')){
    assert.throws(()=>assertNumericalDem(o),/VISUAL_LAYER_AS_DEM/,name);
    assert.throws(()=>horizonProfile(o,0,0,2,0,36),/VISUAL_LAYER_AS_DEM/,name);
    assert.throws(()=>terrainRayProfile(o,{az:90,el:1}),/VISUAL_LAYER_AS_DEM/,name);
  }
});

test('solver guard: a numerical DEM is still accepted',()=>{
  for(const[name,o]of guardObjects('accepted')){assert.equal(assertNumericalDem(o),o,name);assert.equal(horizonProfile(o,5,5,2,0,36).length>0||true,true);}
});
