// Resilient Canvas2D terrain projection when WebGL2 is blocked by the browser/VM.
// This is a projected DEM visual fallback, not a new scientific calculation engine.
import {sampleHeight,scenarioDelta,terrainRayProfile,radians} from './science.js';
const bound=(x,a,b)=>Math.max(a,Math.min(b,x));
export class FallbackScene{
 constructor(canvas){
  this.canvas=canvas;this.ctx=canvas.getContext('2d');this.mode='local';this.colorMode='natural';this.zMeters=1000;this.yaw=-.65;this.pitch=.68;this.radius=32;this.showRays=true;this.ox=0;this.oy=0;this.height=2;this.uncertainty=0;this.sky=null;this.gl=null;
  let drag=false,last=[];
  canvas.addEventListener('pointerdown',e=>{drag=true;last=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointerup',()=>drag=false);
  canvas.addEventListener('pointermove',e=>{if(!drag)return;this.yaw+=(e.clientX-last[0])*.006;this.pitch=bound(this.pitch+(e.clientY-last[1])*.006,.12,1.48);last=[e.clientX,e.clientY];this.render();});
  canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom(Math.exp(e.deltaY*.001));},{passive:false});
  this.handleResize=()=>this.render();window.addEventListener('resize',this.handleResize);
 }
 setTerrain(d,uncertainty=0){this.dem=d;this.uncertainty=uncertainty;this.render();}
 setSun(s){this.sky=s;this.render();}
 setAnalysis(h){this.horizon=h;this.render();}
 setObserver(ox,oy,height){this.ox=ox;this.oy=oy;this.height=height;this.render();}
 setMode(m){this.mode=m;this.preset(m==='globe'?'orbit':'oblique');this.render();}
 setColorMode(m){this.colorMode=m;this.render();}
 setReliefMode(m){this.zMeters=m==='enhanced'?420:1000;this.render();}
 setRays(show){this.showRays=show;this.render();}
 preset(p){this.pitch=p==='top'?1.48:p==='horizon'?.18:p==='orbit'?.6:.7;this.yaw=p==='orbit'?-.9:-.65;this.radius=p==='horizon'?23:32;this.render();}
 zoom(factor){this.radius=bound(this.radius*factor,7,110);this.render();}
 reset(){this.preset(this.mode==='globe'?'orbit':'oblique');}
 snapshot(){return this.canvas.toDataURL('image/png');}
 destroy(){window.removeEventListener('resize',this.handleResize);}
 project(x,z,h,cx,cy,scale){
  // Local east,north,up represented in display-space x,y,vertical (not a geodetic map).
  let a=this.yaw,s=this.pitch;
  const right=x*Math.cos(a)-z*Math.sin(a),depth=x*Math.sin(a)+z*Math.cos(a);
  return [cx+right*scale,cy+depth*Math.sin(s)*scale-h/this.zMeters*Math.cos(s)*scale];
 }
 render(){
  if(!this.ctx)return;const c=this.canvas,ctx=this.ctx,w=c.clientWidth||1000,h=c.clientHeight||520,dpr=Math.min(window.devicePixelRatio||1,2);
  if(c.width!==Math.round(w*dpr)||c.height!==Math.round(h*dpr)){c.width=w*dpr;c.height=h*dpr;}
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  if(this.mode==='globe'){this.drawGlobe(ctx,w,h);return;}
  if(!this.dem)return;
  const d=this.dem,N=Math.min(64,d.n),stride=(d.n-1)/(N-1),span=(d.n-1)*d.spacing/1000;
  const scale=Math.min(w*.78,h*1.18)/(span)*32/this.radius;
  const cx=w*.53,cy=h*.55;
  const values=[];
  for(let j=0;j<N;j++)for(let i=0;i<N;i++){
   const x=(d.originX+i*stride*d.spacing)/1000,z=(d.originY+j*stride*d.spacing)/1000;
   const actual=sampleHeight(d,Math.min(x*1000,d.originX+(d.n-1)*d.spacing-.1),Math.min(z*1000,d.originY+(d.n-1)*d.spacing-.1));
   const alt=(Number.isFinite(actual)?actual:0)+this.uncertainty*scenarioDelta(x*1000,z*1000,d.seed||17);
   values.push({x,z,alt,p:this.project(x,z,alt,cx,cy,scale)});
  }
  const quads=[];
  for(let j=0;j<N-1;j++)for(let i=0;i<N-1;i++){
   let a=j*N+i,b=a+1,e=a+N,f=e+1;
   quads.push({ps:[values[a],values[b],values[f],values[e]],depth:(values[a].z+values[b].z+values[f].z+values[e].z)/4,avg:(values[a].alt+values[b].alt+values[f].alt+values[e].alt)/4});
  }
  quads.sort((a,b)=>a.depth*Math.cos(this.yaw)-b.depth*Math.cos(this.yaw));
  for(const q of quads){
   let {ps,avg}=q,low=bound((avg+700)/1700,0,1),slope=Math.abs(ps[0].alt-ps[2].alt)/(d.spacing*stride);
   let shade=.59+.25*bound(1-slope,0,1);
   if(this.colorMode==='elevation')ctx.fillStyle=`hsl(${204-160*low} 43% ${25+34*low}%)`;
   else if(this.colorMode==='illumination')ctx.fillStyle=this.sky?.sun?.el<0?'#202d3b':`hsl(${40+4*low} 55% ${26+34*shade}%)`;
   else{let c=Math.floor((.28+.38*low)*255*shade);ctx.fillStyle=`rgb(${c},${c+2},${c+10})`;}
   ctx.beginPath();ctx.moveTo(...ps[0].p);for(let k=1;k<4;k++)ctx.lineTo(...ps[k].p);ctx.closePath();ctx.fill();
  }
  if(this.showRays&&this.sky){
   let base=sampleHeight(d,this.ox,this.oy),obs=this.project(this.ox/1000,this.oy/1000,base+this.height,cx,cy,scale);
   for(const [key,colour] of [['sun','#f5b94f'],['earth','#61c6ff']]){
    const sky=this.sky[key],az=radians(sky.az),el=radians(sky.el);
    const result=terrainRayProfile(d,{ox:this.ox,oy:this.oy,height:this.height,az:sky.az,el:sky.el,uncertainty:this.uncertainty,maxDistanceM:7000});
    const distance=Math.min(result.firstHit?.d||7000,7000);
    const end=this.project(this.ox/1000+Math.sin(az)*distance/1000,this.oy/1000+Math.cos(az)*distance/1000,base+this.height+distance*Math.tan(el),cx,cy,scale);
    ctx.strokeStyle=result.firstHit?'#fd6373':colour;ctx.lineWidth=2.5;
    ctx.beginPath();ctx.moveTo(...obs);ctx.lineTo(...end);ctx.stroke();
    ctx.fillStyle=result.firstHit?'#ff6f78':colour;ctx.beginPath();ctx.arc(...end,4,0,Math.PI*2);ctx.fill();
   }
   ctx.fillStyle='#60f3e2';ctx.beginPath();ctx.arc(...obs,4,0,Math.PI*2);ctx.fill();
  }
  ctx.font='700 10px ui-monospace,monospace';ctx.fillStyle='#b3cbd7';ctx.fillText('SOFTWARE TERRAIN PROJECTION',20,h-68);ctx.font='10px ui-monospace,monospace';ctx.fillStyle='#7b98a8';ctx.fillText('WebGL2 blocked · DEM coordinates + celestial rays remain interactive',20,h-52);
 }
 drawGlobe(ctx,w,h){
  const rad=Math.min(w,h)*.38,r=ctx.createRadialGradient(w*.43,h*.30,rad*.12,w*.53,h*.55,rad);
  r.addColorStop(0,'#b5bcc2');r.addColorStop(.52,'#7c858b');r.addColorStop(1,'#192332');
  ctx.fillStyle=r;ctx.beginPath();ctx.arc(w*.54,h*.51,rad,0,Math.PI*2);ctx.fill();
  ctx.save();ctx.beginPath();ctx.arc(w*.54,h*.51,rad,0,Math.PI*2);ctx.clip();
  for(let k=0;k<240;k++){let ang=k*2.399963,dist=Math.sqrt((k*59%241)/241)*rad*.97,x=w*.54+Math.cos(ang)*dist,y=h*.51+Math.sin(ang)*dist,rr=2+(k*17)%22;
   ctx.beginPath();ctx.ellipse(x,y,rr,rr*.55,ang,0,Math.PI*2);ctx.fillStyle='#2d3a443c';ctx.fill();ctx.strokeStyle='#d5d9d422';ctx.lineWidth=2;ctx.stroke();}
  ctx.restore();ctx.fillStyle='#abc0d0';ctx.font='700 10px ui-monospace,monospace';ctx.fillText('ILLUSTRATIVE GLOBE · Enable CESIUM MOON for NASA LRO terrain',20,h-40);
 }
}
