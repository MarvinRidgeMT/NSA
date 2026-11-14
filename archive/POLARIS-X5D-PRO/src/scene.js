// POLARIS X — lightweight standalone WebGL2 engine.
// Visual-only relief and shadow preview use the same DEM but are not a validated photometric solution.
import {sampleHeight,radians,degrees,scenarioDelta,terrainRayProfile} from './science.js';
const VS=`#version 300 es
in vec3 aPosition; in vec3 aNormal; in vec3 aColor;
uniform mat4 uMVP; uniform vec3 uLight; uniform float uAmbient;
out vec3 vColor; out float vIlluminance;
void main(){
 gl_Position=uMVP*vec4(aPosition,1.0);
 vColor=aColor;
 vec3 n=normalize(aNormal);
 vIlluminance=uAmbient+(1.0-uAmbient)*max(0.,dot(n,normalize(uLight)));
}`;
const FS=`#version 300 es
precision highp float;
in vec3 vColor; in float vIlluminance;
out vec4 fragColor;
void main(){vec3 c=vColor*vIlluminance;fragColor=vec4(pow(c,vec3(.85)),1.);}`;
function shader(gl,type,src){let s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
function makeProgram(gl){let p=gl.createProgram();gl.attachShader(p,shader(gl,gl.VERTEX_SHADER,VS));gl.attachShader(p,shader(gl,gl.FRAGMENT_SHADER,FS));gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));return p;}
const norm=v=>{let m=Math.hypot(...v)||1;return v.map(x=>x/m);};
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
function perspective(fov,ratio,n,f){let a=1/Math.tan(fov/2),q=1/(n-f);return new Float32Array([a/ratio,0,0,0,0,a,0,0,0,0,(f+n)*q,-1,0,0,2*f*n*q,0]);}
function lookAt(eye,target,up=[0,1,0]){let z=norm(sub(eye,target)),x=norm(cross(up,z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-x.reduce((s,v,i)=>s+v*eye[i],0),-y.reduce((s,v,i)=>s+v*eye[i],0),-z.reduce((s,v,i)=>s+v*eye[i],0),1]);}
function multiply(a,b){let r=new Float32Array(16);for(let c=0;c<4;c++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)r[c*4+row]+=a[k*4+row]*b[c*4+k];return r;}
function mesh(gl,vertices,indices,mode=gl.TRIANGLES){
 const vao=gl.createVertexArray();gl.bindVertexArray(vao);let vb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vb);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);
 for(let k=0;k<3;k++){gl.enableVertexAttribArray(k);gl.vertexAttribPointer(k,3,gl.FLOAT,false,36,k*12);}
 let ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint32Array(indices),gl.STATIC_DRAW);gl.bindVertexArray(null);
 return {vao,vb,ib,count:indices.length,mode};
}
function erase(gl,m){if(!m)return;gl.deleteVertexArray(m.vao);gl.deleteBuffer(m.vb);gl.deleteBuffer(m.ib);}
function globe(gl){
 let vert=[],ind=[],L=220,B=130,R=8;
 // Procedural preview only: real globe is available through the Cesium Moon switch.
 let craterCenters=[];for(let k=0;k<66;k++){
  const z=(Math.sin(k*91.37)+1)/2;
  craterCenters.push([((k*2.3999632)%(2*Math.PI))-Math.PI,Math.asin(2*z-1),.035+.09*((k*13)%19)/19,.008+.018*((k*17)%13)/13]);
 }
 function surface(lat,lon){let h=.015*Math.sin(lon*25+lat*9)*Math.cos(lat*34)+.01*Math.cos(lon*52+lat*18)+.008*Math.sin(71*lat-13*lon);
  for(const [cl,ct,rad,dep] of craterCenters){const d=Math.hypot(lat-ct,Math.cos(lat)*Math.atan2(Math.sin(lon-cl),Math.cos(lon-cl)));if(d>rad*1.7)continue;h-=dep*Math.exp(-Math.pow(d/(rad*.75),4));h+=dep*.36*Math.exp(-Math.pow((d-rad)/(rad*.18),2));}
  return h;
 }
 for(let j=0;j<=B;j++)for(let i=0;i<=L;i++){
  const lat=Math.PI*(j/B-.5),lon=2*Math.PI*i/L,n=[Math.cos(lat)*Math.cos(lon),Math.sin(lat),Math.cos(lat)*Math.sin(lon)],h=surface(lat,lon),p=n.map(v=>v*R*(1+h));
  const sea=Math.sin(2.8*lat+1.2*Math.cos(lon*2))+.6*Math.sin(5*lon-4*lat);
  const grey=sea>0.7?.43:.69;const v=grey+Math.sin(63*lon+43*lat)*.025;
  vert.push(...p,...n,v,v*.98,v*.92);
 }
 for(let j=0;j<B;j++)for(let i=0;i<L;i++){let a=j*(L+1)+i,b=a+L+1;ind.push(a,b,a+1,b,b+1,a+1);}
 return mesh(gl,vert,ind);
}
function hillColor(value,mode){
 if(mode==='elevation'){
  const q=Math.max(0,Math.min(1,(value+800)/1700));
  return q<.5?[.13+q*.2,.25+q*.65,.42+q*.32]:[.24+(q-.5)*.94,.58+(q-.5)*.56,.58-(q-.5)*.29];
 }
 if(mode==='illumination')return [.78,.66,.44];
 const t=Math.max(0,Math.min(1,(value+780)/1800));
 return [.38+t*.31,.39+t*.31,.43+t*.27];
}
function isShadowed(d,x,y,z,sky,uncertainty){
 if(!sky?.sun)return false;
 const {az,el}=sky.sun;if(el< -7)return true;
 const a=radians(az),east=Math.sin(a),north=Math.cos(a),tan=Math.tan(radians(el));
 const step=Math.max(d.spacing*1.3,140),length=(d.n-2)*d.spacing*.38;
 for(let t=step;t<length;t+=step){
  let xx=x+east*t,yy=y+north*t,h=sampleHeight(d,xx,yy);
  if(!Number.isFinite(h))break;
  h+=uncertainty*scenarioDelta(xx,yy,d.seed||17);
  const ray=z+t*tan+t*t/(2*1737400);
  if(h>ray+.8)return true;
 }
 return false;
}
function terrain(gl,d,uncertainty,sky,mode){
 const N=Math.min(d.n,137),step=(d.n-1)/(N-1),vert=[],ind=[],zScale=1/650;
 const elev=(i,j)=>{
  let x=d.originX+i*step*d.spacing,y=d.originY+j*step*d.spacing;
  let h=sampleHeight(d,Math.min(x,d.originX+(d.n-1)*d.spacing-.0001),Math.min(y,d.originY+(d.n-1)*d.spacing-.0001));
  if(!Number.isFinite(h))h=0;
  return h+uncertainty*scenarioDelta(x,y,d.seed||17);
 };
 for(let j=0;j<N;j++)for(let i=0;i<N;i++){
  const x=d.originX+i*step*d.spacing,y=d.originY+j*step*d.spacing,z=elev(i,j);
  let dx=(elev(Math.min(N-1,i+1),j)-elev(Math.max(0,i-1),j))/(Math.max(1,(Math.min(N-1,i+1)-Math.max(0,i-1))*step*d.spacing));
  let dy=(elev(i,Math.min(N-1,j+1))-elev(i,Math.max(0,j-1)))/(Math.max(1,(Math.min(N-1,j+1)-Math.max(0,j-1))*step*d.spacing));
  const normal=norm([-dx*1000/650,1,-dy*1000/650]);
  let col=hillColor(z,mode),shadow=isShadowed(d,x,y,z,sky,uncertainty);
  if(shadow){let factor=mode==='illumination'?.14:.28;col=col.map(v=>v*factor);}
  else if(mode==='illumination')col=[.97,.76,.40];
  vert.push(x/1000,z*zScale,y/1000,...normal,...col);
 }
 for(let j=0;j<N-1;j++)for(let i=0;i<N-1;i++){let a=j*N+i,b=a+N;ind.push(a,b,a+1,a+1,b,b+1);}
 return mesh(gl,vert,ind);
}
function wires(gl,lines){let vertices=[],indices=[];
 for(const l of lines){for(const p of [l.a,l.b])vertices.push(...p,0,1,0,...l.color);const k=vertices.length/9;indices.push(k-2,k-1);}
 return mesh(gl,vertices,indices,gl.LINES);
}
export class LunarScene{
 constructor(canvas,onIssue){
  this.canvas=canvas;this.onIssue=onIssue;this.mode='local';this.colorMode='natural';this.yaw=-.58;this.pitch=.69;this.radius=34;this.ox=0;this.oy=0;this.height=2;this.uncertainty=0;this.sky=null;this.showRays=true;this.exaggeration=1000/650;this.drag=false;this.busy=false;
  const gl=canvas.getContext('webgl2',{alpha:true,antialias:true,depth:true,preserveDrawingBuffer:true});if(!gl){onIssue('WebGL2 is unavailable. Check Chrome GPU settings.');return;}this.gl=gl;
  try{this.program=makeProgram(gl);this.moon=globe(gl);}catch(e){onIssue(e.message);return;}
  this.uniform={mvp:gl.getUniformLocation(this.program,'uMVP'),light:gl.getUniformLocation(this.program,'uLight'),ambient:gl.getUniformLocation(this.program,'uAmbient')};
  gl.enable(gl.DEPTH_TEST);gl.enable(gl.CULL_FACE);gl.cullFace(gl.BACK);gl.clearColor(0,0,0,0);
  canvas.addEventListener('pointerdown',e=>{this.drag=true;this.last=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointerup',()=>this.drag=false);canvas.addEventListener('pointercancel',()=>this.drag=false);
  canvas.addEventListener('pointermove',e=>{if(!this.drag)return;this.yaw+=(e.clientX-this.last[0])*.006;this.pitch=Math.max(-1.48,Math.min(1.48,this.pitch+(e.clientY-this.last[1])*.006));this.last=[e.clientX,e.clientY];});
  canvas.addEventListener('wheel',e=>{e.preventDefault();this.radius=Math.max(this.mode==='globe'?10:5,Math.min(125,this.radius*Math.exp(e.deltaY*.001)));},{passive:false});
  this.loop=()=>{this.render();this.raf=requestAnimationFrame(this.loop);};this.loop();
 }
 setTerrain(d,uncertainty=0){this.dem=d;this.uncertainty=uncertainty;this.rebuild();this.updateRays();}
 setMode(m){this.mode=m;this.preset(m==='globe'?'orbit':'oblique');this.updateRays();}
 setSun(s){this.sky=s;if(this.dem&&this.mode==='local')this.rebuild();this.updateRays();}
 setAnalysis(horizon){this.horizon=horizon;this.updateRays();}
 setObserver(ox,oy,height){this.ox=ox;this.oy=oy;this.height=height;this.updateRays();}
 setColorMode(v){if(!['natural','elevation','illumination'].includes(v))return;this.colorMode=v;this.rebuild();}
 setRays(show){this.showRays=show;this.updateRays();}
 rebuild(){if(!this.gl||!this.dem||this.busy)return;this.busy=true;try{erase(this.gl,this.surface);this.surface=terrain(this.gl,this.dem,this.uncertainty,this.sky,this.colorMode);}catch(e){this.onIssue(e.message);}finally{this.busy=false;}}
 updateRays(){if(!this.gl||!this.dem)return;erase(this.gl,this.rays);let lines=[];
  const base=sampleHeight(this.dem,this.ox,this.oy);if(!Number.isFinite(base))return;
  const y=(base+this.height)/650+.07,marker=[this.ox/1000,y,this.oy/1000],cyan=[.31,.99,.87];
  const cross=(dx,dy,dz,color)=>lines.push({a:[marker[0]-dx,marker[1]-dy,marker[2]-dz],b:[marker[0]+dx,marker[1]+dy,marker[2]+dz],color});
  cross(.30,0,0,cyan);cross(0,.34,0,cyan);cross(0,0,.30,cyan);
  if(this.showRays&&this.sky&&this.mode==='local')for(const [key,color] of [['sun',[1,.76,.3]],['earth',[.38,.77,1]]]){
   const v=this.sky[key],profile=terrainRayProfile(this.dem,{ox:this.ox,oy:this.oy,height:this.height,az:v.az,el:v.el,uncertainty:this.uncertainty,maxDistanceM:8500});
   const distance=Math.min(profile.firstHit?.d||8000,8000),az=radians(v.az),el=radians(v.el),d=distance/1000;
   const end=[marker[0]+d*Math.cos(el)*Math.sin(az),marker[1]+distance*Math.sin(el)/650,marker[2]+d*Math.cos(el)*Math.cos(az)];
   lines.push({a:marker,b:end,color:profile.firstHit?[.98,.32,.39]:color});
   if(profile.firstHit){
    const t=.14;lines.push({a:[end[0]-t,end[1]+t,end[2]],b:[end[0]+t,end[1]-t,end[2]],color:[1,.33,.40]});
    lines.push({a:[end[0]-t,end[1]-t,end[2]],b:[end[0]+t,end[1]+t,end[2]],color:[1,.33,.40]});
   }
  }
  this.rays=wires(this.gl,lines);
 }
 preset(p){
  if(p==='top'){this.yaw=0;this.pitch=1.46;this.radius=32;}
  else if(p==='horizon'){this.yaw=-.7;this.pitch=.14;this.radius=20;}
  else if(p==='orbit'){this.yaw=-2.35;this.pitch=-.33;this.radius=23;}
  else{this.yaw=-.62;this.pitch=.68;this.radius=32;}
 }
 zoom(dir){this.radius=Math.max(this.mode==='globe'?10:5,Math.min(125,this.radius*dir));}
 reset(){this.preset(this.mode==='globe'?'orbit':'oblique');}
 render(){
  if(!this.gl||!this.program)return;const gl=this.gl,w=this.canvas.clientWidth,h=this.canvas.clientHeight;if(!w||!h)return;
  const dpr=Math.min(devicePixelRatio||1,2),nw=Math.round(w*dpr),nh=Math.round(h*dpr);
  if(this.canvas.width!==nw||this.canvas.height!==nh){this.canvas.width=nw;this.canvas.height=nh;}
  gl.viewport(0,0,nw,nh);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(this.program);
  const cp=Math.cos(this.pitch),eye=[this.radius*cp*Math.sin(this.yaw),this.radius*Math.sin(this.pitch),this.radius*cp*Math.cos(this.yaw)],mv=lookAt(eye,[0,0,0]),proj=perspective(.71,w/h,.06,350);
  gl.uniformMatrix4fv(this.uniform.mvp,false,multiply(proj,mv));
  let sun=this.sky?.sun;const a=radians(sun?.az??135),e=radians(sun?.el??19);
  // ENU in scene coordinates: x=east, display y=up, z=north.
  const light=norm([Math.sin(a)*Math.cos(e),Math.sin(e)*this.exaggeration,Math.cos(a)*Math.cos(e)]);
  gl.uniform3fv(this.uniform.light,light);gl.uniform1f(this.uniform.ambient,this.mode==='globe'?.30:.55);
  const draw=m=>{if(!m)return;gl.bindVertexArray(m.vao);gl.drawElements(m.mode,m.count,gl.UNSIGNED_INT,0);gl.bindVertexArray(null);};
  if(this.mode==='globe')draw(this.moon);
  else{draw(this.surface);gl.disable(gl.DEPTH_TEST);gl.uniform1f(this.uniform.ambient,1);draw(this.rays);gl.enable(gl.DEPTH_TEST);}
 }
 snapshot(){return this.canvas.toDataURL('image/png');}
 destroy(){cancelAnimationFrame(this.raf);if(this.gl){for(const m of [this.surface,this.rays,this.moon])erase(this.gl,m);this.gl.deleteProgram(this.program);}}
}
