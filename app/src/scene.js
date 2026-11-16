// POLARIS X source-backed 3D scene.
// Display relief, materials, shadows and the global Moon are visual aids. Numerical
// visibility remains in science.js and always uses source elevations in metres.
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import nasaMoonBytes from '../assets/nasa/NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb';
import {sampleHeight,radians,scenarioDelta,terrainRayProfile,localOffsetToGrid,localDirectionToGrid} from './science.js';

const TRUE_SCALE_Z_METERS=1000;
const ENHANCED_RELIEF_Z_METERS=420; // Explicit visual option: 1000/420 = 2.38x relief.
const GLOBAL_RADIUS=8;
const COLORS={sun:0xf4bd55,earth:0x65c8ff,teal:0x73f3d7,impact:0xff596b,coverage:0x88a4b3};

const finite=(value,fallback=0)=>Number.isFinite(value)?value:fallback;
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
function terrainHeight(d,x,y,uncertainty=0){
 const h=sampleHeight(d,x,y);
 return Number.isFinite(h)?h+uncertainty*scenarioDelta(x,y,d.seed||17):NaN;
}
function sourceBounds(d){return {x0:d.originX,x1:d.originX+(d.n-1)*d.spacing,y0:d.originY,y1:d.originY+(d.n-1)*d.spacing};}
function contains(bounds,x,y,pad=0){return x>=bounds.x0-pad&&x<=bounds.x1+pad&&y>=bounds.y0-pad&&y<=bounds.y1+pad;}
function disposeObject(root){
 if(!root)return;
 root.traverse?.(node=>{node.geometry?.dispose?.();const materials=Array.isArray(node.material)?node.material:[node.material];for(const material of materials){if(!material)continue;for(const value of Object.values(material))if(value?.isTexture)value.dispose();material.dispose?.();}});
 root.removeFromParent?.();
}
function palette(z,min,max,mode,slope,x=0,y=0){
 const q=clamp((z-min)/Math.max(1,max-min),0,1);
 if(mode==='elevation'){
  const low=new THREE.Color(0x172a46),mid=new THREE.Color(0x4c9aa3),high=new THREE.Color(0xd7c7a0);
  return q<.55?low.lerp(mid,q/.55):mid.lerp(high,(q-.55)/.45);
 }
 if(mode==='illumination')return new THREE.Color(0x8b774f).multiplyScalar(.96-slope*.23);
 const low=new THREE.Color(0x545b5a),high=new THREE.Color(0xaaa28e);
 const grain=.5+.5*Math.sin(x*.021+Math.sin(y*.014)*1.9)*Math.cos(y*.017-x*.006);
 return low.lerp(high,clamp(.22+q*.52-slope*.12,0,1)).multiplyScalar(.91+grain*.10-slope*.05);
}
function smoothstep(value){const t=clamp(value,0,1);return t*t*(3-2*t);}
function buildTerrainMesh(d,{reference,zMeters=TRUE_SCALE_Z_METERS,uncertainty=0,mode='natural',maxResolution=401,cutout=null,opacity=1,context=false,edgeBlendDem=null,edgeBlendWidthM=0}={}){
 const N=Math.min(d.n,maxResolution),stride=(d.n-1)/(N-1),count=N*N,positions=new Float32Array(count*3),heights=new Float32Array(count),colorSize=edgeBlendDem?4:3,colors=new Float32Array(count*colorSize);
 const bounds=sourceBounds(d);
 let min=Infinity,max=-Infinity;
 for(let j=0;j<N;j++)for(let i=0;i<N;i++){
  const x=d.originX+i*stride*d.spacing,y=d.originY+j*stride*d.spacing;let h=terrainHeight(d,x,y,uncertainty);
  if(edgeBlendDem&&edgeBlendWidthM>0){const contextHeight=terrainHeight(edgeBlendDem,x,y,0),edgeDistance=Math.min(x-bounds.x0,bounds.x1-x,y-bounds.y0,bounds.y1-y),mix=smoothstep(edgeDistance/edgeBlendWidthM);if(Number.isFinite(contextHeight))h=contextHeight*(1-mix)+h*mix;}
  const k=j*N+i;heights[k]=finite(h,reference);min=Math.min(min,heights[k]);max=Math.max(max,heights[k]);
 }
 const at=(i,j)=>heights[clamp(j,0,N-1)*N+clamp(i,0,N-1)];
 for(let j=0;j<N;j++)for(let i=0;i<N;i++){
  const k=j*N+i,x=d.originX+i*stride*d.spacing,y=d.originY+j*stride*d.spacing,h=heights[k];
  const dx=(at(i+1,j)-at(i-1,j))/Math.max(1,2*stride*d.spacing),dy=(at(i,j+1)-at(i,j-1))/Math.max(1,2*stride*d.spacing),slope=clamp(Math.hypot(dx,dy),0,1);
  positions.set([x/1000,(h-reference)/zMeters,y/1000],k*3);
  const c=palette(h,min,max,mode,slope,x,y),edgeDistance=Math.min(x-bounds.x0,bounds.x1-x,y-bounds.y0,bounds.y1-y),alpha=edgeBlendDem?smoothstep(edgeDistance/edgeBlendWidthM):1;colors.set(colorSize===4?[c.r,c.g,c.b,alpha]:[c.r,c.g,c.b],k*colorSize);
 }
 const indices=[];
 for(let j=0;j<N-1;j++)for(let i=0;i<N-1;i++){
  const cx=d.originX+(i+.5)*stride*d.spacing,cy=d.originY+(j+.5)*stride*d.spacing;
  if(cutout&&contains(cutout,cx,cy,-Math.max(d.spacing*1.5,10)))continue;
  const a=j*N+i,b=a+N;indices.push(a,b,a+1,a+1,b,b+1);
 }
 const geometry=new THREE.BufferGeometry();
 geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));
 geometry.setAttribute('color',new THREE.BufferAttribute(colors,colorSize));
 geometry.setIndex(indices);geometry.computeVertexNormals();geometry.computeBoundingSphere();
 const material=new THREE.MeshStandardMaterial({vertexColors:true,roughness:.96,metalness:0,emissive:0x0a0f11,emissiveIntensity:.25,side:THREE.DoubleSide,transparent:opacity<1||!!edgeBlendDem,opacity,alphaTest:edgeBlendDem?.06:0,depthWrite:!edgeBlendDem,polygonOffset:!!edgeBlendDem,polygonOffsetFactor:-1,polygonOffsetUnits:-1});
 // The blended local footprint must not cast its rectangular coverage edge into
 // the regional context. Directional normals still provide time-linked relief.
 const mesh=new THREE.Mesh(geometry,material);mesh.castShadow=false;mesh.receiveShadow=true;mesh.renderOrder=context?0:1;
 mesh.userData={triangles:indices.length/3,resolution:N,spacing:d.spacing,source:d.source,context,verticalScale:zMeters===TRUE_SCALE_Z_METERS?1:TRUE_SCALE_Z_METERS/zMeters,visualEdgeBlendM:edgeBlendDem?edgeBlendWidthM:0};
 return mesh;
}
function buildBoundary(d,reference,color,zMeters=TRUE_SCALE_Z_METERS,uncertainty=0,edgeBlendDem=null){
 const b=sourceBounds(d),points=[],segments=72;
 const edge=(x0,y0,x1,y1)=>{for(let i=0;i<segments;i++){const t=i/(segments-1),x=x0+(x1-x0)*t,y=y0+(y1-y0)*t,h=edgeBlendDem?terrainHeight(edgeBlendDem,x,y,0):terrainHeight(d,x,y,uncertainty);points.push(new THREE.Vector3(x/1000,(finite(h,reference)-reference)/zMeters+.012,y/1000));}};
 edge(b.x0,b.y0,b.x1,b.y0);edge(b.x1,b.y0,b.x1,b.y1);edge(b.x1,b.y1,b.x0,b.y1);edge(b.x0,b.y1,b.x0,b.y0);
 return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color,transparent:true,opacity:.26,depthTest:true}));
}
function cylinderBetween(a,b,radius,color,opacity=1){
 const delta=new THREE.Vector3().subVectors(b,a),length=delta.length(),geometry=new THREE.CylinderGeometry(radius,radius,length,10,1,false),material=new THREE.MeshBasicMaterial({color,transparent:opacity<1,opacity,depthTest:true});
 const object=new THREE.Mesh(geometry,material);object.position.copy(a).add(b).multiplyScalar(.5);object.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());return object;
}
function addBox(group,size,position,color){const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),new THREE.MeshStandardMaterial({color,roughness:.82,metalness:.08}));mesh.position.set(...position);mesh.castShadow=false;mesh.receiveShadow=false;group.add(mesh);return mesh;}
function buildStation(scale){
 const group=new THREE.Group(),metal=0x8e9695,ivory=0xc5c8be,panel=0x143845,gold=0xae772a;
 addBox(group,[.34,.08,.30].map(v=>v*scale),[0,.04*scale,0],metal);addBox(group,[.25,.22,.21].map(v=>v*scale),[0,.18*scale,0],ivory);
 addBox(group,[.62,.025,.24].map(v=>v*scale),[-.43*scale,.19*scale,0],panel);addBox(group,[.62,.025,.24].map(v=>v*scale),[.43*scale,.19*scale,0],panel);
 addBox(group,[.035,.42,.035].map(v=>v*scale),[0,.50*scale,0],metal);addBox(group,[.17,.035,.06].map(v=>v*scale),[0,.72*scale,0],gold);return group;
}
const prefersReducedMotion=()=>typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches;
const easeInOutCubic=k=>k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
function angularPoint(latDeg,lonDeg,radius){const lat=radians(latDeg),lon=radians(lonDeg),c=Math.cos(lat);return new THREE.Vector3(radius*c*Math.sin(lon),radius*Math.sin(lat),radius*c*Math.cos(lon));}
function latitudeRing(latDeg,radius,color,opacity=.35){const points=[];for(let i=0;i<=180;i++)points.push(angularPoint(latDeg,i*2,radius));return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color,transparent:true,opacity}));}

export class LunarScene{
 constructor(canvas,onIssue){
  this.canvas=canvas;this.onIssue=onIssue;this.mode='local';this.colorMode='natural';this.reliefMode='true';this.zMeters=TRUE_SCALE_Z_METERS;this.height=2;this.ox=0;this.oy=0;this.uncertainty=0;this.showRays=true;this.cinematic=true;this.site={lat:-89.4632,lon:-137.49,name:'Connecting Ridge'};
  try{
   this.renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,preserveDrawingBuffer:false,powerPreference:'high-performance'});/* drawing buffer is not preserved between frames (saves a full-frame copy per frame); captures call render() and read the canvas in the same task */
   this.renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.18;this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  }catch(error){onIssue(error.message);return;}
  this.gl=this.renderer.getContext();this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(42,1,.015,600);this.controls=new OrbitControls(this.camera,canvas);this.controls.enableDamping=true;this.controls.dampingFactor=.065;this.controls.screenSpacePanning=true;this.controls.zoomToCursor=true;
  this.controls.addEventListener('start',()=>{this.lastInteraction=performance.now();this.cancelFlight('pointer');});this.onKey=e=>{if(e.key==='Escape')this.cancelFlight('escape');};window.addEventListener('keydown',this.onKey);this.controls.addEventListener('change',()=>this.lastInteraction=performance.now());this.lastInteraction=performance.now();
  this.localGroup=new THREE.Group();this.globalGroup=new THREE.Group();this.scene.add(this.localGroup,this.globalGroup);
  this.ambient=new THREE.AmbientLight(0xa6bbbf,.24);this.fill=new THREE.HemisphereLight(0xa8bdc7,0x050708,.38);this.sunLight=new THREE.DirectionalLight(0xffe0a3,2.65);this.sunLight.castShadow=true;this.sunLight.shadow.mapSize.set(2048,2048);this.sunLight.shadow.bias=-.00008;this.sunLight.shadow.normalBias=.012;Object.assign(this.sunLight.shadow.camera,{left:-4,right:4,top:4,bottom:-4,near:.1,far:120});this.sunLight.shadow.camera.updateProjectionMatrix();this.scene.add(this.ambient,this.fill,this.sunLight,this.sunLight.target);
  this.loadingMoon=new THREE.Mesh(new THREE.SphereGeometry(GLOBAL_RADIUS,96,64),new THREE.MeshStandardMaterial({color:0x454b50,roughness:1,metalness:0}));this.globalGroup.add(this.loadingMoon);
  this.globalGroup.add(latitudeRing(-80,GLOBAL_RADIUS*1.006,COLORS.teal,.30),latitudeRing(-85,GLOBAL_RADIUS*1.008,COLORS.teal,.65));
  this.globalReady=false;this.loadGlobalMoon();this.setSite(this.site);this.preset('oblique');
  canvas.addEventListener('dblclick',()=>{if(this.mode==='globe')document.getElementById('localMode')?.click();});
  this.loop=(now=performance.now())=>{this.stepFlight(now);this.trackFrame(now);if(this.cinematic&&!this.flight&&this.mode==='globe'&&performance.now()-this.lastInteraction>2500){this.controls.autoRotate=true;this.controls.autoRotateSpeed=.18;}else this.controls.autoRotate=false;this.controls.update();this.render();this.raf=requestAnimationFrame(this.loop);};this.loop();
 }
 loadGlobalMoon(){
  const bytes=nasaMoonBytes,buffer=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),loader=new GLTFLoader();
  loader.parse(buffer,'',gltf=>{
   const model=gltf.scene,box=new THREE.Box3().setFromObject(model),sphere=box.getBoundingSphere(new THREE.Sphere()),scale=GLOBAL_RADIUS/sphere.radius;model.scale.setScalar(scale);model.position.copy(sphere.center).multiplyScalar(-scale);
   model.traverse(node=>{if(!node.isMesh)return;node.castShadow=false;node.receiveShadow=false;const materials=Array.isArray(node.material)?node.material:[node.material];for(const material of materials){if(material.map)material.map.colorSpace=THREE.SRGBColorSpace;if('roughness' in material)material.roughness=1;if('metalness' in material)material.metalness=0;material.needsUpdate=true;}});
   this.globalMoon=model;this.globalGroup.add(model);disposeObject(this.loadingMoon);this.loadingMoon=null;this.globalReady=true;this.updateGlobalHud();
  },error=>{this.globalReady=false;this.onIssue(`NASA Moon model could not be decoded: ${error.message||error}`);this.updateGlobalHud();});
 }
 updateGlobalHud(){const badge=document.getElementById('globalModelStatus');if(badge)badge.textContent=this.globalReady?'NASA SVS LRO TOPO GLB · LOADED':'NASA TOPO MODEL · LOADING';}
 setSite(site){
  this.site=site||this.site;disposeObject(this.siteMarker);const group=new THREE.Group(),p=angularPoint(this.site.lat,this.site.lon,GLOBAL_RADIUS*1.012),tip=p.clone().setLength(GLOBAL_RADIUS*1.14);
  group.add(cylinderBetween(p,tip,.025,COLORS.teal));const dot=new THREE.Mesh(new THREE.SphereGeometry(.09,18,12),new THREE.MeshBasicMaterial({color:COLORS.teal}));dot.position.copy(tip);group.add(dot);this.globalGroup.add(group);this.siteMarker=group;
 }
 setTerrain(primary,uncertainty=0,context=null){this.visualDem=primary;this.contextDem=context;this.uncertainty=uncertainty;this.referenceZ=finite(sampleHeight(primary,0,0),0);this.rebuild();if(this.mode==='local')this.preset('oblique');this.updateRays();}
 setScienceTerrain(dem){this.scienceDem=dem;this.updateRays();}
 applyMode(mode){this.mode=mode;this.localGroup.visible=mode==='local';this.globalGroup.visible=mode==='globe';this.updateRays();this.updateGlobalHud();this.updateModeHud();}
 // Global -> local is a two-stage, cancelable flight: descend toward the selected site on the NASA global
 // model, then swap to the local source terrain from overhead and settle on the oblique footprint view.
 // Pointer drag, Escape or another preset cancels it and completes the mode change instantly.
 setMode(mode,animate=false){
  if(animate&&this.mode==='globe'&&mode==='local'&&this.camera&&!prefersReducedMotion()){
   const d=angularPoint(this.site.lat,this.site.lon,1),finish=()=>{this.applyMode('local');this.preset('oblique');};
   this.flyTo({position:d.clone().multiplyScalar(GLOBAL_RADIUS*1.16),target:d.clone().multiplyScalar(GLOBAL_RADIUS),up:this.camera.up.clone(),min:.1,max:70},1500,()=>{this.applyMode('local');const r=this.fitRadius||8;this.camera.up.set(0,1,0);this.camera.position.set(0,r*3.4,.002);this.controls.target.set(0,-.03,0);this.controls.update();this.preset('oblique',true);},finish);
   return;
  }
  this.cancelFlight();this.applyMode(mode);this.preset(mode==='globe'?'orbit':'oblique');
 }
 setSun(sky){this.sky=sky;const sun=sky?.sun,dem=this.scienceDem||this.contextDem||this.visualDem;if(sun&&dem){const horizontal=localDirectionToGrid(dem,sun.az),el=radians(sun.el),verticalScale=TRUE_SCALE_Z_METERS/this.zMeters,direction=new THREE.Vector3(horizontal.x*Math.cos(el),Math.sin(el)*verticalScale,horizontal.y*Math.cos(el)).normalize();this.sunLight.position.copy(direction.multiplyScalar(60));this.sunLight.target.position.set(0,0,0);this.sunLight.intensity=sun.el<-4?.35:2.55;}this.updateRays();}
 setAnalysis(horizon){this.horizon=horizon;this.updateRays();}
 setObserver(ox,oy,height){this.ox=ox;this.oy=oy;this.height=height;this.updateRays();}
 setColorMode(mode){if(!['natural','elevation','illumination'].includes(mode))return;this.colorMode=mode;this.rebuild();this.updateRays();}
 setReliefMode(mode){if(!['true','enhanced'].includes(mode)||mode===this.reliefMode)return;this.reliefMode=mode;this.zMeters=mode==='enhanced'?ENHANCED_RELIEF_Z_METERS:TRUE_SCALE_Z_METERS;this.rebuild();this.updateRays();this.preset('oblique');}
 setRays(show){this.showRays=show;this.updateRays();}
 setCinematic(active){this.cinematic=!!active;this.lastInteraction=performance.now();}
 rebuild(){
  if(!this.visualDem)return;disposeObject(this.terrainRoot);const root=new THREE.Group();let triangles=0;
  if(this.contextDem&&this.contextDem!==this.visualDem){const contextMesh=buildTerrainMesh(this.contextDem,{reference:this.referenceZ,zMeters:this.zMeters,mode:this.colorMode,maxResolution:401,opacity:.94,context:true});root.add(contextMesh,buildBoundary(this.contextDem,this.referenceZ,COLORS.coverage,this.zMeters));triangles+=contextMesh.userData.triangles;}
  const seamBlendM=this.contextDem?Math.max(this.visualDem.spacing*60,240):0,primaryMesh=buildTerrainMesh(this.visualDem,{reference:this.referenceZ,zMeters:this.zMeters,uncertainty:this.uncertainty,mode:this.colorMode,maxResolution:401,edgeBlendDem:this.contextDem,edgeBlendWidthM:seamBlendM}),primaryBoundary=buildBoundary(this.visualDem,this.referenceZ,COLORS.teal,this.zMeters,this.uncertainty,this.contextDem);primaryBoundary.material.opacity=.18;root.add(primaryMesh,primaryBoundary);triangles+=primaryMesh.userData.triangles;
  this.terrainRoot=root;this.localGroup.add(root);const primarySpanKm=this.visualDem.spacing*(this.visualDem.n-1)/1000;this.spanKm=(this.contextDem||this.visualDem).spacing*((this.contextDem||this.visualDem).n-1)/1000;
  // The default local camera frames the scientific 5 m footprint as the hero.
  // The 80 m crop remains rendered around it and is reachable by zooming out.
  this.fitRadius=clamp(this.contextDem?Math.max(primarySpanKm*1.05,this.spanKm*.055):this.spanKm*.69,1.6,34);
  const spacing=this.contextDem?`${this.visualDem.spacing} M + ${this.contextDem.spacing} M LOD`:`${this.visualDem.spacing} M SOURCE GRID`;
  this.localStatsText=`${spacing} · ${Math.round(triangles/1000)}K TRIANGLES`;
  this.localCoverageText=this.contextDem?`LOCAL ${this.visualDem.spacing} M / REGIONAL ${this.contextDem.spacing} M · BOUNDARY + VISUAL SEAM BLEND`:`${this.visualDem.spacing} M DATASET · ${this.spanKm.toFixed(1)} KM COVERAGE`;
  this.localScaleText=this.spanKm>12?'SCALE 5 KM':this.spanKm>4?'SCALE 1 KM':'SCALE 250 M';this.updateModeHud();
 }
 updateModeHud(){
  const stats=document.getElementById('meshStats'),coverage=document.getElementById('coverageHud'),scale=document.getElementById('scaleHud');
  if(this.mode==='globe'){if(stats)stats.textContent='2.02M VERTICES · 1.02M TRIANGLES';if(coverage)coverage.textContent='NASA SVS LRO 8K COLOR + HEIGHT MAP';if(scale)scale.textContent='MOON RADIUS 1,737.4 KM';}
  else{if(stats&&this.localStatsText)stats.textContent=this.localStatsText;if(coverage&&this.localCoverageText)coverage.textContent=this.localCoverageText;if(scale&&this.localScaleText)scale.textContent=this.localScaleText;}
 }
 updateRays(){
  disposeObject(this.instrumentRoot);this.hits={sun:null,earth:null};this.observerOrigin=null;if(!this.visualDem)return;const root=new THREE.Group(),visualOffset=localOffsetToGrid(this.visualDem,this.ox,this.oy),visualBounds=sourceBounds(this.visualDem),visual=contains(visualBounds,visualOffset.x,visualOffset.y)?this.visualDem:(this.contextDem||this.visualDem),observer=localOffsetToGrid(visual,this.ox,this.oy),base=terrainHeight(visual,observer.x,observer.y,this.uncertainty),groundY=(finite(base,this.referenceZ)-this.referenceZ)/this.zMeters;
  const primarySpanKm=this.visualDem.spacing*(this.visualDem.n-1)/1000,stationScale=clamp(primarySpanKm*.018,.035,.085),station=buildStation(stationScale);station.scale.setScalar(this.markerScale||1);station.position.set(observer.x/1000,groundY+.004,observer.y/1000);root.add(station);
  const origin=new THREE.Vector3(observer.x/1000,groundY+this.height/this.zMeters,observer.y/1000),node=new THREE.Mesh(new THREE.SphereGeometry(clamp(stationScale*.055,.012,.035)*(this.markerScale||1),18,12),new THREE.MeshBasicMaterial({color:COLORS.teal}));node.position.copy(origin);root.add(node);this.observerOrigin=origin.clone();
  const dem=this.scienceDem||this.contextDem||this.visualDem;
  if(this.showRays&&this.sky&&this.mode==='local')for(const [key,color] of [['sun',COLORS.sun],['earth',COLORS.earth]]){
   const target=this.sky[key],profile=terrainRayProfile(dem,{ox:this.ox,oy:this.oy,height:this.height,az:target.az,el:target.el,uncertainty:this.uncertainty,maxDistanceM:Math.min(16000,(dem.n-2)*dem.spacing*.48)}),point=profile.firstHit||profile.rows.at(-1),start=profile.rows[0],end=new THREE.Vector3(point.x/1000,origin.y+(point.ray-start.ray)/this.zMeters,point.y/1000);
   root.add(cylinderBetween(origin,end,clamp(stationScale*.016,.006,.018)*Math.max(this.markerScale||1,.25),color,.92));if(profile.firstHit)this.hits[key]={point:end.clone(),distanceM:profile.firstHit.d??null};
   if(profile.firstHit){const impact=new THREE.Mesh(new THREE.SphereGeometry(clamp(stationScale*.095,.022,.055)*(this.markerScale||1),20,14),new THREE.MeshBasicMaterial({color:COLORS.impact,transparent:true,opacity:.95}));impact.position.copy(end);root.add(impact);}
   else{const arrow=new THREE.Mesh(new THREE.ConeGeometry(clamp(stationScale*.045,.014,.032),clamp(stationScale*.15,.05,.12),12),new THREE.MeshBasicMaterial({color}));arrow.position.copy(end);arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),end.clone().sub(origin).normalize());root.add(arrow);}
  }
  this.instrumentRoot=root;this.localGroup.add(root);
 }
 presetPose(name){
  const up=new THREE.Vector3(0,1,0);
  if(name==='orbit'){const d=angularPoint(this.site.lat,this.site.lon,1),u=Math.abs(d.z)<.92?new THREE.Vector3(0,0,1):new THREE.Vector3(0,1,0);return {position:d.multiplyScalar(23),target:new THREE.Vector3(),up:u,min:10,max:70};}
  const r=this.fitRadius||8,min=Math.max(.35,r*.20),max=Math.max(6,r*4.5),t=new THREE.Vector3(0,-.03,0);
  if(name==='top')return {position:new THREE.Vector3(0,r*1.35,.001),target:t,up,min,max};
  if(name==='horizon')return {position:new THREE.Vector3(r*.22,r*.075,r*.43),target:t,up,min,max};
  if(name==='regional'){const R=Math.max((this.spanKm||r*2)*.5,r);return {position:new THREE.Vector3(R*.62,R*.7,R*1.02),target:t,up,min,max:Math.max(max,R*3)};}
  if(name==='obstruction'){
   // Side-on close-up of the first sampled terrain hit of a blocked target ray (Earth first, then Sun).
   const hit=this.hits?.earth||this.hits?.sun,o=this.observerOrigin;if(!hit||!o)return null;
   const mid=o.clone().lerp(hit.point,.5),h=new THREE.Vector3(hit.point.x-o.x,0,hit.point.z-o.z),len=Math.max(h.length(),.02),side=new THREE.Vector3(-h.z,0,h.x).normalize(),dist=Math.max(len*2.4,.22);
   return {position:mid.clone().add(side.multiplyScalar(dist)).add(new THREE.Vector3(0,dist*.32,0)),target:mid,up,min:.02,max,target3:this.hits.earth?'earth':'sun'};
  }
  return {position:new THREE.Vector3(r*.72,r*.66,r*.82),target:t,up,min,max};
 }
 preset(name,animate=false){
  if(!this.camera||!this.controls)return false;
  const pose=this.presetPose(name);if(!pose)return false;
  // schematic markers are tens of metres wide; in the 70 m obstruction close-up they would hide the terrain, so shrink them (visual only)
  const ms=name==='obstruction'?.12:1;if(ms!==(this.markerScale||1)){this.markerScale=ms;this.updateRays();}
  this.activePreset=name;this.camera.near=this.mode==='globe'?.05:(name==='obstruction'?.002:.01);this.camera.far=600;this.camera.updateProjectionMatrix();
  if(animate&&!prefersReducedMotion())this.flyTo(pose,1300);
  else{this.cancelFlight();this.camera.position.copy(pose.position);this.camera.up.copy(pose.up);this.controls.target.copy(pose.target);this.controls.minDistance=pose.min;this.controls.maxDistance=pose.max;this.controls.update();}
  this.lastInteraction=performance.now();return pose;
 }
 flyTo(pose,ms=1300,onDone=null,onCancel=null){
  this.cancelFlight();
  this.flight={fromP:this.camera.position.clone(),fromT:this.controls.target.clone(),fromU:this.camera.up.clone(),to:pose,t0:performance.now(),ms,onDone,onCancel};
  this.controls.enableDamping=false;this.controls.minDistance=0;this.controls.maxDistance=Infinity;document.body.classList.add('camera-flying');
 }
 stepFlight(now){
  const f=this.flight;if(!f)return;const k=Math.min(1,Math.max(0,(now-f.t0)/f.ms)),e=easeInOutCubic(k);
  const target=f.fromT.clone().lerp(f.to.target,e),a=f.fromP.clone().sub(f.fromT),b=f.to.position.clone().sub(f.to.target);
  // log-distance interpolation keeps zoom speed perceptually even across orbit-to-surface scales
  const dist=Math.exp(Math.log(Math.max(a.length(),1e-6))*(1-e)+Math.log(Math.max(b.length(),1e-6))*e),dir=a.normalize().lerp(b.normalize(),e);
  if(dir.lengthSq()<1e-8)dir.copy(b);dir.normalize();
  this.camera.position.copy(target).add(dir.multiplyScalar(dist));this.camera.up.copy(f.fromU).lerp(f.to.up,e).normalize();this.controls.target.copy(target);
  if(k>=1){this.flight=null;this.finishFlight(f.to);f.onDone?.();}
 }
 finishFlight(pose){this.controls.enableDamping=true;this.controls.minDistance=pose.min;this.controls.maxDistance=pose.max;document.body.classList.remove('camera-flying');}
 cancelFlight(reason){
  const f=this.flight;if(!f)return false;this.flight=null;
  const d=this.camera.position.distanceTo(this.controls.target);this.controls.enableDamping=true;this.controls.minDistance=Math.min(f.to.min,d);this.controls.maxDistance=Math.max(f.to.max,d);document.body.classList.remove('camera-flying');
  f.onCancel?.();if(reason)this.onFlightCancel?.(reason);return true;
 }
 trackFrame(now){const p=this.perf||(this.perf={last:now,samples:[]}),dt=now-p.last;p.last=now;if(dt>0&&dt<1000){p.samples.push(dt);if(p.samples.length>300)p.samples.shift();}}
 resetPerf(){this.perf=null;}
 getPerf(){
  const s=[...(this.perf?.samples||[])].sort((a,b)=>a-b),mean=s.reduce((a,b)=>a+b,0)/(s.length||1),info=this.renderer?.info,mem=typeof performance!=='undefined'?performance.memory:null;
  return {mode:this.mode,frames:s.length,meanFrameMs:+mean.toFixed(2),p95FrameMs:+(s[Math.floor(s.length*.95)]||0).toFixed(2),maxFrameMs:+(s.at(-1)||0).toFixed(2),fps:s.length?+(1000/mean).toFixed(1):null,drawCalls:info?.render.calls??null,trianglesDrawn:info?.render.triangles??null,geometries:info?.memory.geometries??null,textures:info?.memory.textures??null,jsHeapMB:mem?+(mem.usedJSHeapSize/1048576).toFixed(1):null,pixelRatio:this.renderer?.getPixelRatio()??null};
 }
 zoom(factor){if(!this.camera||!this.controls)return;const offset=this.camera.position.clone().sub(this.controls.target).multiplyScalar(factor);this.camera.position.copy(this.controls.target).add(offset);this.controls.update();}
 reset(){this.preset(this.mode==='globe'?'orbit':'oblique');}
 render(){if(!this.renderer)return;const w=this.canvas.clientWidth,h=this.canvas.clientHeight;if(!w||!h)return;const size=this.renderer.getSize(new THREE.Vector2());if(size.x!==w||size.y!==h){this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();}this.renderer.render(this.scene,this.camera);}
 snapshot(){return this.canvas.toDataURL('image/png');}
 destroy(){cancelAnimationFrame(this.raf);window.removeEventListener('keydown',this.onKey);this.controls?.dispose();disposeObject(this.localGroup);disposeObject(this.globalGroup);this.renderer?.dispose();}
}
