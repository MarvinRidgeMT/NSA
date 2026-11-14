// POLARIS X — transparent teaching model and source-labelled scientific pipeline.
// Never equate a pedagogical ephemeris or demonstration DEM with flight-ready NASA calculations.
export const MOON_RADIUS_M = 1737400;
export const SITES = [
  {id:'connecting',name:'Connecting Ridge',code:'Site01',lat:-89.4632,lon:-137.4900,seed:17},
  {id:'shackleton',name:'Shackleton Rim',code:'Site04',lat:-89.7668,lon:-171.8700,seed:41},
  {id:'peak',name:'Peak Near Shackleton',code:'Site07',lat:-88.8110,lon:123.6901,seed:53},
  {id:'gerlache',name:'de Gerlache Rim',code:'Site11',lat:-88.6834,lon:-67.9321,seed:71}
];
export const degrees = r => r*180/Math.PI;
export const radians = d => d*Math.PI/180;
export const clamp = (v,lo,hi) => Math.max(lo,Math.min(hi,v));
export const norm360 = v => (v%360+360)%360;
export function curvatureDrop(distanceM){const d=Math.abs(distanceM);if(d>=MOON_RADIUS_M)throw Error('Tangent-plane distance must be smaller than Moon radius');return MOON_RADIUS_M-Math.sqrt(MOON_RADIUS_M*MOON_RADIUS_M-d*d);}
export function polarMeters(lat, lon) { const rho=2*MOON_RADIUS_M*Math.tan(Math.PI/4+radians(lat)/2);return {x:rho*Math.sin(radians(lon)), y:rho*Math.cos(radians(lon))}; }
function hash(x,y,seed){ const v=Math.sin(x*127.1+y*311.7+seed*13.17)*43758.5453123;return v-Math.floor(v);}
function crater(x,y,cx,cy,r,depth){let d=Math.hypot(x-cx,y-cy)/r;if(d>2.5)return 0;return -depth*Math.exp(-Math.pow(d/0.72,4))+depth*.42*Math.exp(-Math.pow((d-1)/.19,2));}
export function makeDemoTerrain(site,n=105,spacing=220){
 const values=[];const s=site.seed||17;const centers=[[-3900,1800,3300,330], [4000,-2300,2100,220],[-1100,-4300,1800,170],[5300,4300,3300,450]];
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){
  const x=(i-(n-1)/2)*spacing,y=(j-(n-1)/2)*spacing;
  let z=240*Math.sin(x/2800+s)*Math.cos(y/3200-s)+175*Math.sin((x+y)/1500)+110*Math.cos(y/1080)+70*Math.sin(x/520);
  z+=140*Math.sin(x/1700+y/2600+s*.17);
  for(let k=0;k<centers.length;k++){const c=centers[k];z+=crater(x,y,c[0]+(s%13)*42,c[1],c[2],c[3]);}
  z+=32*(hash(i,j,s)-.5);
  values.push(Math.round(z*10)/10);
 }
 return {seed:s,siteId:site.id,lat:site.lat,lon:site.lon,originX:-(n-1)*spacing/2,originY:-(n-1)*spacing/2,spacing,n,values,kind:'illustrative',source:'Deterministic synthetic crater/ridge DEM; NOT NASA data',datum:'illustrative heights; no lunar datum'};
}
export function sampleHeight(dem,x,y){const fx=(x-dem.originX)/dem.spacing,fy=(y-dem.originY)/dem.spacing;const i=Math.floor(fx),j=Math.floor(fy);if(i<0||j<0||i>=dem.n-1||j>=dem.n-1)return NaN;const tx=fx-i,ty=fy-j;const a=dem.values[j*dem.n+i],b=dem.values[j*dem.n+i+1],c=dem.values[(j+1)*dem.n+i],d=dem.values[(j+1)*dem.n+i+1];return (a*(1-tx)+b*tx)*(1-ty)+(c*(1-tx)+d*tx)*ty;}
export function scenarioDelta(x,y,seed=17){ // deterministic bounded spatial perturbation field, not a statistical error model
 return .53*Math.sin(x/1350+seed*.32)*Math.cos(y/1650+seed*.27)+.32*Math.sin((x+y)/760)+.15*Math.cos((x-y)/530);
}
export function horizonProfile(dem,ox=0,oy=0,height=2,uncertainty=0,bins=360){
 const base=sampleHeight(dem,ox,oy);if(!Number.isFinite(base))throw new Error('Observer outside terrain coverage');
 const profile=[], blockers=[];const reach=(dem.n-2)*dem.spacing*.47;
 const step=Math.max(dem.spacing*.78,80);
 for(let a=0;a<bins;a++){
  const az=2*Math.PI*a/bins,ex=Math.sin(az),ny=Math.cos(az);let best=-90,bestD=0;
  for(let d=step;d<=reach;d+=step){let x=ox+ex*d,y=oy+ny*d;let z=sampleHeight(dem,x,y);if(!Number.isFinite(z))break;
   z+=uncertainty*scenarioDelta(x,y,dem.seed||17);
   const theta=degrees(Math.atan2(z-base-height-curvatureDrop(d),d));
   if(theta>best){best=theta;bestD=d;}
  }
  profile.push(best===-90?-5:best);blockers.push(bestD);
 }
 return {angles:profile,distances:blockers,reachM:reach,observerElevationM:base+height,bins};
}
export function horizonAt(h,az){let p=norm360(az)/360*h.bins,i=Math.floor(p),f=p-i;return h.angles[i]*(1-f)+h.angles[(i+1)%h.bins]*f;}
// This is a simplified geometric pedagogical approximation. For real analysis import JPL Horizons CSV-derived ephemerides.
export function approximateSky(time,site){
 const days=(+new Date(time)-Date.UTC(2026,0,1))/86400000;
 const lat=radians(site.lat),lon=radians(site.lon);
 const obliquity=radians(1.54),season=2*Math.PI*days/365.25;
 const decl=obliquity*Math.sin(season),H=2*Math.PI*days/29.530588+lon+0.45;
 const enu=(dec,h)=>{const east=-Math.cos(dec)*Math.sin(h),north=Math.sin(dec)*Math.cos(lat)-Math.cos(dec)*Math.sin(lat)*Math.cos(h),up=Math.sin(lat)*Math.sin(dec)+Math.cos(lat)*Math.cos(dec)*Math.cos(h);return {az:norm360(degrees(Math.atan2(east,north))),el:degrees(Math.asin(clamp(up,-1,1)))};};
 const sun=enu(decl,H);const eDecl=radians(5.1*Math.sin(2*Math.PI*days/27.55+1.1));const earth=enu(eDecl,lon+0.12*Math.sin(days*2*Math.PI/27.3));
 return {sun,earth,source:'illustrative-analytic'};
}
export function ephemerisAt(time,site,ephem){
 if(!ephem||!Array.isArray(ephem.samples)||ephem.samples.length<2)return approximateSky(time,site);
 const q=+new Date(time),a=ephem.samples;
 if(q<+new Date(a[0].time)||q>+new Date(a[a.length-1].time))throw new Error('Requested time is outside imported JPL ephemeris coverage. Change the mission interval or regenerate the bundle; illustrative geometry will not be silently substituted.');
 let lo=0,hi=a.length-1;
 while(lo+1<hi){const mid=Math.floor((lo+hi)/2);if(+new Date(a[mid].time)<q)lo=mid;else hi=mid;}
 let t0=+new Date(a[lo].time),t1=+new Date(a[hi].time),f=clamp((q-t0)/(t1-t0),0,1);
 const mixAz=(u,v)=>norm360(u+((((v-u+540)%360)-180))*f);
 return {sun:{az:mixAz(a[lo].sun.az,a[hi].sun.az),el:a[lo].sun.el*(1-f)+a[hi].sun.el*f},earth:{az:mixAz(a[lo].earth.az,a[hi].earth.az),el:a[lo].earth.el*(1-f)+a[hi].earth.el*f},source:'jpl-horizons-interpolated'};
}
export function evaluateTimeline(site,dem,ephem,options={}){
 const start=options.start||'2026-11-14T14:00:00Z',durationH=options.durationH??72,stepH=options.stepH??1;
 const horizon=horizonProfile(dem,options.ox||0,options.oy||0,options.height??2,options.uncertainty??0);
 const rows=[];for(let k=0;k<Math.ceil(durationH/stepH);k++){
  const t=new Date(+new Date(start)+k*stepH*3600000).toISOString(),sky=ephemerisAt(t,site,ephem);
  const sunMargin=sky.sun.el-horizonAt(horizon,sky.sun.az),earthMargin=sky.earth.el-horizonAt(horizon,sky.earth.az);
  rows.push({time:t,...sky,sunMargin,earthMargin,sunVisible:sunMargin>0,earthVisible:earthMargin>0,both:sunMargin>0&&earthMargin>0});
 }
 const frac=key=>rows.filter(x=>x[key]).length/(rows.length||1)*100;
 function longestMissing(key){let longest=0,current=0;for(const r of rows){if(!r[key])current+=stepH;else {longest=Math.max(longest,current);current=0;}}return Math.max(longest,current);}
 return {horizon,rows,metrics:{sunPct:frac('sunVisible'),earthPct:frac('earthVisible'),bothPct:frac('both'),darkH:longestMissing('sunVisible'),blackoutH:longestMissing('earthVisible'),minSunMargin:Math.min(...rows.map(x=>x.sunMargin)),minEarthMargin:Math.min(...rows.map(x=>x.earthMargin))},dataMode:dem.kind==='nasa'&&rows.every(r=>r.source==='jpl-horizons-interpolated')?'nasa+jpl':'mixed-or-demo',demSource:dem.source,stepH};
}
// A geometrical ray is expressed in the SAME local ENU frame as the DEM.
// Height along the local tangent plane includes the lunar curvature term.
// This detects the FIRST obstruction, rather than the skyline's maximum-angle feature.
export function terrainRayProfile(dem,{ox=0,oy=0,height=2,az=0,el=0,uncertainty=0,maxDistanceM=0,stepM=0}={}){
 const z0=sampleHeight(dem,ox,oy);
 if(!Number.isFinite(z0))throw Error('Observer outside terrain coverage');
 const reach=maxDistanceM || (dem.n-2)*dem.spacing*.47;
 const step=stepM || Math.max(70,dem.spacing*.6);
 const east=Math.sin(radians(az)),north=Math.cos(radians(az));
 const rows=[{d:0,terrain:z0,ray:z0+height,clearance:height,x:ox,y:oy}];
 let firstHit=null;
 for(let d=step;d<=reach;d+=step){
  const x=ox+east*d,y=oy+north*d;
  let terrain=sampleHeight(dem,x,y);if(!Number.isFinite(terrain))break;
  terrain+=uncertainty*scenarioDelta(x,y,dem.seed||17);
  const ray=z0+height+d*Math.tan(radians(el))+curvatureDrop(d);
  const row={d,terrain,ray,clearance:ray-terrain,x,y};rows.push(row);
  if(!firstHit&&row.clearance<=0)firstHit=row;
 }
 return {rows,firstHit,visible:!firstHit,reachM:rows.at(-1).d,az,el};
}
export function windowEvents(rows,stepH=1){
 const events=[];
 for(const key of ['sunVisible','earthVisible','both']){
  let start=0;
  for(let i=1;i<=rows.length;i++){
   if(i===rows.length||rows[i][key]!==rows[start][key]){
    events.push({target:key,visible:rows[start][key],start:rows[start].time,end:i===rows.length?new Date(+new Date(rows.at(-1).time)+stepH*3600000).toISOString():rows[i].time,durationH:(i-start)*stepH,startIndex:start,endIndex:i-1});
    start=i;
   }
  }
 }
 return events;
}
// Deterministic stress tests are SCENARIOS, never calibrated probabilities.
export function stressTest(site,dem,ephem,options){
 const u=options.uncertainty??0,e=options.ox??0,n=options.oy??0;
 const amp=Math.abs(options.stressAmplitude??20),offset=options.stressOffsetM??400;
 const plan=[
  {name:'Nominal',ox:e,oy:n,uncertainty:u,shiftH:0},
  {name:'Terrain + variation',uncertainty:u+amp},
  {name:'Terrain − variation',uncertainty:u-amp},
  {name:'Landing east',ox:e+offset},
  {name:'Landing west',ox:e-offset},
  {name:'Landing north',oy:n+offset},
  {name:'Landing south',oy:n-offset},
  {name:'Arrival +12 h',shiftH:12},
  {name:'Arrival −12 h',shiftH:-12}
 ];
 return plan.map(p=>{
  try{
   const sim=evaluateTimeline(site,dem,ephem,{...options,ox:p.ox??e,oy:p.oy??n,uncertainty:p.uncertainty??u,start:new Date(+new Date(options.start)+(p.shiftH||0)*3600000).toISOString()});
   const maxDark=options.maxDarkH??24,maxBlackout=options.maxBlackoutH??20;
   return {name:p.name,valid:true,...sim.metrics,feasible:sim.metrics.darkH<=maxDark&&sim.metrics.blackoutH<=maxBlackout,mode:sim.dataMode};
  }catch(err){return {name:p.name,valid:false,error:String(err.message),feasible:false,mode:'unavailable'};}
 });
}
export function compareSites(sites,getData,options){
 return sites.map(site=>{
  try{
   const {dem,ephem}=getData(site);
   const sim=evaluateTimeline(site,dem,ephem,{...options,ox:0,oy:0,uncertainty:0});
   const stress=stressTest(site,dem,ephem,{...options,ox:0,oy:0,uncertainty:0});
   return {id:site.id,name:site.name,code:site.code,...sim.metrics,mode:sim.dataMode,valid:true,stable:stress.filter(x=>x.feasible).length,scenarioCount:stress.length,feasible:stress[0].feasible};
  }catch(e){return {id:site.id,name:site.name,code:site.code,valid:false,error:String(e.message)};}
 });
}
export function validateBundle(b){
 const formats=new Set(['POLARIS-X5D-v1','POLARIS-X5D-v2']);
 if(!b||!formats.has(b.format))throw Error('Not a supported POLARIS-X5D scientific bundle');
 if(b.format==='POLARIS-X5D-v2'&&b.validation?.status!=='SOURCE_BASED_UNVALIDATED'&&b.validation?.status!=='VALIDATED_NASA_JPL')throw Error('V2 bundle must declare a recognized validation state');
 if(!Array.isArray(b.datasets)||!b.datasets.length)throw Error('No datasets in bundle');
 const validateDem=(d,label)=>{if(!d||!Number.isInteger(d.n)||d.n<4||d.n>2048||!Array.isArray(d.values)||d.values.length!==d.n*d.n||!(d.spacing>0)||!d.values.every(Number.isFinite))throw Error('Invalid terrain grid for '+label);};
 for(const item of b.datasets){
  validateDem(item.dem,item.siteId);
  if(item.localDem)validateDem(item.localDem,item.siteId+' local DEM');
  if(item.uncertainty?.totalZRms)validateDem(item.uncertainty.totalZRms,item.siteId+' error layer');
  for(const clone of item.uncertainty?.clones||[])validateDem(clone.dem,item.siteId+' clone '+clone.id);
  if(item.ephemeris){const r=item.ephemeris.samples;if(!Array.isArray(r)||r.length<2)throw Error('Invalid JPL samples');let previous=-Infinity;for(const sample of r){const time=+new Date(sample.time);if(!Number.isFinite(time)||time<=previous||!sample.sun||!sample.earth||![sample.sun.az,sample.sun.el,sample.earth.az,sample.earth.el].every(Number.isFinite)||sample.sun.az<0||sample.sun.az>360||sample.earth.az<0||sample.earth.az>360||Math.abs(sample.sun.el)>90||Math.abs(sample.earth.el)>90)throw Error('Invalid ephemeris sample');previous=time;}}
 }
 return b;
}
export function summarizeSource(d,ephem){return {terrain:d?.kind==='nasa'?'NASA LOLA elevation input':'Illustrative DEM',sunEarth:ephem?.samples?.length?'JPL Horizons imported':'Approximate analytic illustration',hasImportedInputs:!!(d?.kind==='nasa'&&ephem?.samples?.length)};}
