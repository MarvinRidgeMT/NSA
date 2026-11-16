// Visual-layer contract (polaris-visual-layers-v1) for the app: validation + the solver guard.
// A visual layer is a display raster (albedo, morphology...). It is never terrain: status 'VISUAL',
// numericalAuthority false, and no DEM fields. Same rules as tools/sources/visual_layers.py and
// web/src/bundle/visualLayers.ts; all three run schemas/fixtures/visual-layers-cases.json.
export const VISUAL_LAYERS_SCHEMA='polaris-visual-layers-v1';
export const VISUAL_ROLES=['albedo','morphology','hillshade','reference-image'];
const DEM_FIELDS=['values','verticalUnits','spacing','n','originX','originY','layer','kind'];
const HEX=/^[0-9a-f]{64}$/,ID=/^[a-z0-9][a-z0-9_-]{2,63}$/,PATH=/^(?!\/)(?!.*\.\.)[A-Za-z0-9_./-]+$/;

export class VisualLayerError extends Error{constructor(code,message){super(`${code}: ${message}`);this.code=code;this.name='VisualLayerError';}}
const fail=(code,message)=>{throw new VisualLayerError(code,message);};
const num=v=>typeof v==='number'&&Number.isFinite(v);
const obj=v=>v&&typeof v==='object'&&!Array.isArray(v);

export function validateVisualLayer(layer){
  if(!obj(layer))fail('LAYER','layer must be an object');
  for(const f of DEM_FIELDS)if(f in layer)fail('DEM_FIELDS',`visual layer must not carry the numerical DEM field '${f}'`);
  if(layer.status!=='VISUAL'||!String(layer.label??'').includes('VISUAL'))fail('VISUAL_STATUS',"status must be 'VISUAL' and the label must contain the word VISUAL");
  if(layer.numericalAuthority!==false)fail('NUMERICAL_AUTHORITY','numericalAuthority must be exactly false');
  if(typeof layer.id!=='string'||!ID.test(layer.id))fail('ID','id must be a stable lower-case slug');
  if(!VISUAL_ROLES.includes(layer.role))fail('ROLE',`role must be one of ${VISUAL_ROLES.join(', ')}`);
  for(const k of ['title','productId','frame'])if(typeof layer[k]!=='string'||layer[k].length<3)fail('FIELD',`${k} missing`);
  if(!String(layer.sourceUrl??'').startsWith('https://'))fail('FIELD','sourceUrl must be https');
  const p=layer.projection??{};
  if(p.units!=='m')fail('UNITS',"projection.units must be 'm'");
  if(p.type!=='south_polar_stereographic'||p.centreLatDeg!==-90||p.centreLonEastDeg!==0||p.radiusM!==1737400)fail('PROJECTION','only south polar stereographic, 90 S / 0 E, R = 1737400 m is accepted');
  const a=layer.artifact??{};
  if(typeof a.path!=='string'||!PATH.test(a.path))fail('ARTIFACT','artifact.path must be a repository-relative path');
  if(typeof a.sha256!=='string'||!HEX.test(a.sha256))fail('HASH','artifact.sha256 must be 64 lower-case hex characters');
  const sh=layer.sourceHash??{};
  if(!['whole-file','byte-range-window'].includes(sh.kind)||typeof sh.sha256!=='string'||!HEX.test(sh.sha256))fail('HASH','sourceHash.sha256 must be 64 lower-case hex characters');
  if(sh.wholeFileSha256!=null&&!HEX.test(String(sh.wholeFileSha256)))fail('HASH','sourceHash.wholeFileSha256 must be null or 64 hex characters');
  if(!Number.isInteger(a.width)||!Number.isInteger(a.height)||a.width<1||a.height<1)fail('ARTIFACT','artifact width/height must be positive integers');
  const px=layer.pixelSizeM;
  if(!num(px)||px<=0)fail('UNITS','pixelSizeM must be a positive number of metres');
  const b=layer.boundsM??{};
  if(!['xmin','xmax','ymin','ymax'].every(k=>num(b[k]))||b.boundsAre!=='pixel-edges')fail('BOUNDS','boundsM needs xmin/xmax/ymin/ymax (pixel-edges)');
  if(!(b.xmin<b.xmax&&b.ymin<b.ymax))fail('BOUNDS','bounds are inverted');
  if(Math.abs((b.xmax-b.xmin)-a.width*px)>1e-6||Math.abs((b.ymax-b.ymin)-a.height*px)>1e-6)fail('BOUNDS','bounds do not equal artifact size x pixelSizeM');
  if(layer.rowOrder!=='north-to-south')fail('BOUNDS','rowOrder must be north-to-south');
  const r=layer.registration??{},o=r.offsetM??{};
  if(r.status!=='display-alignment-evidence-only'||!num(o.x)||!num(o.y)||!r.method||!r.against)fail('REGISTRATION',"registration needs method, against, offsetM and status 'display-alignment-evidence-only'");
  if(typeof layer.display?.processing!=='string')fail('DISPLAY','display.processing must describe the stretch');
  const lim=layer.limitations;
  if(!Array.isArray(lim)||!lim.length||!lim.every(x=>typeof x==='string'&&x.length>=8))fail('LIMITATIONS','at least one limitation is required');
  return layer;
}

export function validateVisualLayers(doc){
  if(!obj(doc)||doc.schema!==VISUAL_LAYERS_SCHEMA)fail('SCHEMA',`schema must be ${VISUAL_LAYERS_SCHEMA}`);
  if(doc.releaseStatus!=='SOURCE_BASED_UNVALIDATED')fail('RELEASE_STATUS','releaseStatus must stay SOURCE_BASED_UNVALIDATED');
  if(!Array.isArray(doc.layers))fail('SCHEMA','layers must be an array');
  const seen=new Set();
  for(const layer of doc.layers){validateVisualLayer(layer);if(seen.has(layer.id))fail('DUPLICATE_ID',layer.id);seen.add(layer.id);}
  return doc;
}

export function isVisualLayer(o){return !!obj(o)&&(o.status==='VISUAL'||o.numericalAuthority===false||(obj(o.artifact)&&!('values' in o)));}

// Solver guard: call before any height is read. Throws if a visual layer is passed where terrain is expected.
export function assertNumericalDem(dem){if(isVisualLayer(dem))fail('VISUAL_LAYER_AS_DEM','a visual layer cannot be used as solver terrain (numericalAuthority is false)');return dem;}
