// Independent scientific dashboard panels.  No invented NASA metrics or black-box rankings.
import {SITES,makeDemoTerrain,compareSites,terrainRayProfile,horizonAt} from './science.js';
const format=(n,p=1)=>Number.isFinite(n)?n.toFixed(p):'—';
function chart(canvas,height){const rect=canvas.getBoundingClientRect(),w=Math.max(270,rect.width||700),h=height,dpr=Math.min(devicePixelRatio||1,2),ctx=canvas.getContext('2d');canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);return {ctx,w,h};}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
let currentTarget='sun';
export function installProUI({$,state,recompute,saveFile,toast}){
 const cameraIds={cameraOblique:'oblique',cameraTop:'top',cameraHorizon:'horizon',cameraRegional:'regional',cameraObstruction:'obstruction'};
 for(const [id,preset] of Object.entries(cameraIds)){
  $(id).addEventListener('click',()=>{if(state.mode!=='local'&&preset!=='orbit'){toast('Camera presets apply to the local terrain. Switch to LOCAL TERRAIN first.');return;}const pose=state.scene?.preset?.(preset,true);if(pose===false){toast(preset==='obstruction'?'No blocked Sun or Earth ray at this time, so there is no obstruction to inspect.':'Camera preset unavailable.');return;}for(const key of Object.keys(cameraIds))$(key).classList.toggle('camera-active',key===id);if(preset==='obstruction'&&pose?.target3){const hit=state.scene.hits?.[pose.target3];toast(`${pose.target3==='earth'?'Earth':'Sun'} ray: first sampled terrain hit${Number.isFinite(hit?.distanceM)?' at '+Math.round(hit.distanceM)+' m':''}. Discrete sampling; not sub-cell truth.`);}});
 }
 $('colorMode').addEventListener('change',e=>{state.scene?.setColorMode(e.target.value);$('modelBadge').textContent=e.target.value==='natural'?'REGOLITH LIGHTING · VISUAL':e.target.value==='elevation'?'HEIGHT MAP · DEM':'DIRECTIONAL LIGHT · VISUAL';});
 $('showRays').addEventListener('change',e=>state.scene?.setRays(e.target.checked));
 $('captureBtn').addEventListener('click',()=>{
  try{
   const canvas=state.cesium?.canvas || state.scene?.canvas;
   if(!canvas)throw Error('Scene has not initialized');
   if(!state.cesium&&typeof state.scene?.render==='function')state.scene.render(); // capture path: draw now, then snapshot in the same task (the buffer is not preserved)
   canvas.toBlob(blob=>{if(!blob){toast('Screenshot blocked by browser. Try the local rendering mode.');return;}
    let url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`POLARIS-X-${state.site.id}-scene.png`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   });
  }catch(e){toast('Unable to capture 3D scene: '+e.message);}
 });
 $('profileSun').addEventListener('click',()=>{currentTarget='sun';$('profileSun').classList.add('selected');$('profileEarth').classList.remove('selected');renderDynamicPro({$,state,options:null});});
 $('profileEarth').addEventListener('click',()=>{currentTarget='earth';$('profileEarth').classList.add('selected');$('profileSun').classList.remove('selected');renderDynamicPro({$,state,options:null});});
 window.addEventListener('resize',()=>{renderDynamicPro({$,state,options:null});renderStressPro({$,state});});
}
export function renderDynamicPro({$,state,options}){
 if(!state.results?.rows?.length)return;
 const r=state.results.rows[state.index],dem=state.activeDem||state.dems.get(state.site.id)||makeDemoTerrain(state.site);
 const config={ox:options?.ox??+$('offsetEast').value,oy:options?.oy??+$('offsetNorth').value,height:options?.height??+$('observerHeight').value,uncertainty:options?.uncertainty??+$('uncertainty').value};
 const sun=terrainRayProfile(dem,{...config,...r.sun,maxDistanceM:state.results.horizon.reachM}),earth=terrainRayProfile(dem,{...config,...r.earth,maxDistanceM:state.results.horizon.reachM});
 // All status text is explicitly conditional on the current modeled horizon/ephemeris inputs.
 const first=r.sunMargin<0?{key:'Sun',ray:sun,target:r.sun,margin:r.sunMargin}:r.earthMargin<0?{key:'Earth',ray:earth,target:r.earth,margin:r.earthMargin}:null;
 const real=state.results.dataMode==='nasa+jpl';
 $('insightKind').textContent=real?'IMPORTED NASA/JPL':'ILLUSTRATIVE INPUTS';
 $('liveInsight').textContent=first?`${first.key} is obstructed along bearing ${format(first.target.az)}°`:'Both target centers clear the modeled terrain horizon';
 $('liveInsightSub').textContent=first?.ray.firstHit?
  `First sampled obstruction at ${format(first.ray.firstHit.d/1000,2)} km; modeled clearance ${format(first.margin,2)}°. Click the cross-section for details.`:
  `Sun clearance ${format(r.sunMargin,2)}°; Earth clearance ${format(r.earthMargin,2)}°. Numerical results use ${real?'imported NASA/JPL inputs':'illustrative inputs'}.`;
 $('modelBadge').textContent=state.mode==='globe'?'GLOBAL COLOR MODEL · VISUAL':$('colorMode').value==='elevation'?'ELEVATION · DEM':$('colorMode').value==='illumination'?'DIRECTIONAL LIGHT · VISUAL':'REGOLITH LIGHTING · VISUAL';
 $('sceneCaption').textContent=state.cesium?'CESIUM MOON · VISUAL TILES · SCIENCE FROM DEM':state.mode==='globe'?'NASA GLOBAL ORIENTATION MODEL · DOUBLE-CLICK TO ENTER SITE':'5 M LOCAL DETAIL + 80 M REGIONAL CONTEXT · SCIENCE FROM SOURCE DEM';
 $('sceneHost').classList.toggle('has-obstruction',!!first);
 renderProfileChart($,currentTarget==='sun'?sun:earth,currentTarget,dem.kind);
}
function renderProfileChart($,ray,target,kind){
 let {ctx,w,h}=chart($('profileCanvas'),230);const pts=ray.rows,pad={l:57,r:14,t:17,b:33};if(pts.length<3)return;
 const xmin=0,xmax=pts.at(-1).d/1000;
 const ymin=Math.min(...pts.map(p=>Math.min(p.ray,p.terrain))),ymax=Math.max(...pts.map(p=>Math.max(p.ray,p.terrain))),span=Math.max(1,ymax-ymin);
 const ylo=ymin-span*.10,yhi=ymax+span*.10;
 const x=d=>pad.l+(d/1000-xmin)/(xmax-xmin)*(w-pad.l-pad.r),y=v=>pad.t+(yhi-v)/(yhi-ylo)*(h-pad.t-pad.b);
 ctx.font='10px ui-monospace,monospace';ctx.lineWidth=1;
 for(let t=0;t<=4;t++){let elev=ylo+(yhi-ylo)*t/4;ctx.strokeStyle='#233e50';ctx.beginPath();ctx.moveTo(pad.l,y(elev));ctx.lineTo(w-pad.r,y(elev));ctx.stroke();ctx.fillStyle='#8ea9b9';ctx.fillText(format(elev,0)+'m',4,y(elev)+4);}
 for(let t=0;t<=4;t++){let d=t*xmax/4;ctx.fillStyle='#92b1bf';ctx.fillText(format(d,1)+'km',x(d)-14,h-9);}
 ctx.beginPath();ctx.moveTo(x(pts[0].d),y(pts[0].terrain));for(let i=1;i<pts.length;i++)ctx.lineTo(x(pts[i].d),y(pts[i].terrain));ctx.lineTo(x(pts.at(-1).d),h-pad.b);ctx.lineTo(pad.l,h-pad.b);ctx.closePath();ctx.fillStyle='#4562708a';ctx.fill();
 ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(x(p.d),y(p.terrain)):ctx.moveTo(x(p.d),y(p.terrain)));ctx.strokeStyle='#a3ced9';ctx.lineWidth=1.6;ctx.stroke();
 ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(x(p.d),y(p.ray)):ctx.moveTo(x(p.d),y(p.ray)));ctx.strokeStyle=target==='sun'?'#f6c06a':'#64c5fc';ctx.lineWidth=1.7;ctx.stroke();
 if(ray.firstHit){let p=ray.firstHit;ctx.beginPath();ctx.arc(x(p.d),y(p.terrain),4.5,0,2*Math.PI);ctx.fillStyle='#ff6d7b';ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.stroke();}
 const label=target==='sun'?'Sun':'Earth',hit=ray.firstHit;
 $('profileExplanation').textContent=hit?`${label} ray crosses the sampled terrain near ${format(hit.d/1000,2)} km from the observer, at ${format(ray.az)}° azimuth. This result covers ${format(ray.reachM/1000)} km and uses ${kind==='nasa'?'imported NASA terrain':'synthetic DEM'}; terrain beyond the crop is not evaluated.`:`${label} direction is unobstructed across the sampled ${format(ray.reachM/1000)} km terrain extent at ${format(ray.az)}° azimuth and ${format(ray.el,2)}° elevation. This does not guarantee visibility beyond the DEM footprint.`;
}
export function renderComparisonPro({$,state,options,recompute}){
 const result=compareSites(SITES,site=>({dem:state.dems.get(site.id)||makeDemoTerrain(site),ephem:state.ephemerides.get(site.id)||null}),options);
 state.compare=result;
 $('comparisonGrid').innerHTML=result.map(row=>{
  if(!row.valid)return `<button type="button" class="comparison-site" data-site="${row.id}"><span class="site-header">${esc(row.name)}<span class="site-id">${row.code}</span></span><span class="site-error">${esc(row.error)}</span></button>`;
  return `<button type="button" class="comparison-site ${row.id===state.site.id?'selected':''}" data-site="${row.id}"><span class="site-header">${esc(row.name)}<span class="site-id">${row.code}</span></span><span class="site-kpis"><span><label>SUN ACCESS</label><strong>${format(row.sunPct)}%</strong></span><span><label>LONGEST SHADOW</label><strong>${format(row.darkH)}h</strong></span></span><span class="site-foot ${row.feasible?'':'no'}">${row.feasible?'NOMINAL PASS':'EXCEEDS LIMIT'} · ${row.stable}/${row.scenarioCount} tested scenarios · ${row.mode==='nasa+jpl'?'NASA/JPL':'DEMO'}</span></button>`;
 }).join('');
 $('comparisonGrid').querySelectorAll('[data-site]').forEach(btn=>btn.addEventListener('click',()=>{
  const site=SITES.find(s=>s.id===btn.dataset.site);if(!site)return;state.site=site;$('siteSelect').value=site.id;recompute(false);
 }));
}
export function renderStressPro({$,state}){
 if(!state.stress?.length)return;
 let tests=state.stress,valid=tests.filter(x=>x.valid),pass=valid.filter(x=>x.feasible).length;
 $('scenarioSummary').textContent=`${pass}/${valid.length} evaluable scenarios satisfy BOTH interruption limits${valid.length!==tests.length?`; ${tests.length-valid.length} outside data coverage`:''}. This is a fixed stress-test set, NOT a probability.`;
 const {ctx,w,h}=chart($('stressCanvas'),195);const left=40,right=12,top=18,bottom=39,plotH=h-top-bottom,group=(w-left-right)/tests.length,bar=group*.55;
 for(let i=0;i<=4;i++){let yy=top+plotH*(1-i/4);ctx.strokeStyle='#294254';ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();ctx.fillStyle='#92aabc';ctx.font='10px ui-monospace,monospace';ctx.fillText(i*25+'%',5,yy+3);}
 tests.forEach((t,i)=>{const x=left+i*group+(group-bar)/2,y=top+plotH*(1-(t.valid?t.sunPct:0)/100);
  ctx.fillStyle=!t.valid?'#536878':t.feasible?'#47c6bb':'#c98b62';if(t.valid)ctx.fillRect(x,y,bar,plotH*t.sunPct/100);else ctx.fillRect(x,top+plotH-3,bar,3);
  ctx.fillStyle='#b0c6d6';ctx.font='10px ui-monospace,monospace';ctx.fillText(String(i+1).padStart(2,'0'),x+bar/2-6,h-13);
 });
}
