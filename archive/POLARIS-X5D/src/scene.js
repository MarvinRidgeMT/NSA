// Self-contained WebGL2 lunar visualization. Procedural globe is explicitly labelled illustrative.
// Cesium lunar 3D Tiles can be enabled from the UI with a user's ion token.
import {sampleHeight,radians,scenarioDelta} from './science.js';
const VS=`#version 300 es
in vec3 aPosition;in vec3 aNormal;in vec3 aColor;
uniform mat4 uMVP;uniform vec3 uLight;
out vec3 vColor;out float vLight;
void main(){gl_Position=uMVP*vec4(aPosition,1.0);vColor=aColor;vec3 n=normalize(aNormal);vLight=.30+.70*max(dot(n,normalize(uLight)),0.0);}`;
const FS=`#version 300 es
precision highp float;in vec3 vColor;in float vLight;out vec4 fragColor;
void main(){vec3 c=vColor*vLight;fragColor=vec4(pow(c,vec3(.87)),1.0);}`;
function compile(gl,type,s){let sh=gl.createShader(type);gl.shaderSource(sh,s);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(sh));return sh;}
function program(gl){let p=gl.createProgram();gl.attachShader(p,compile(gl,gl.VERTEX_SHADER,VS));gl.attachShader(p,compile(gl,gl.FRAGMENT_SHADER,FS));gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));return p;}
function normalize(v){let m=Math.hypot(...v)||1;return v.map(x=>x/m);}
function cross(a,b){return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];}
function subtract(a,b){return a.map((x,i)=>x-b[i]);}
function perspective(fov,aspect,near,far){let f=1/Math.tan(fov/2),nf=1/(near-far);return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*nf,-1,0,0,2*far*near*nf,0]);}
function lookAt(eye,target,up=[0,1,0]){let z=normalize(subtract(eye,target)),x=normalize(cross(up,z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-x.reduce((a,v,i)=>a+v*eye[i],0),-y.reduce((a,v,i)=>a+v*eye[i],0),-z.reduce((a,v,i)=>a+v*eye[i],0),1]);}
function mul(a,b){let r=new Float32Array(16);for(let c=0;c<4;c++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)r[c*4+row]+=a[k*4+row]*b[c*4+k];return r;}
function mesh(gl,vertices,indices,mode=gl.TRIANGLES){let vao=gl.createVertexArray();gl.bindVertexArray(vao);let buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);let stride=9*4;for(let i=0;i<3;i++){gl.enableVertexAttribArray(i);gl.vertexAttribPointer(i,3,gl.FLOAT,false,stride,i*12);}let ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint32Array(indices),gl.STATIC_DRAW);gl.bindVertexArray(null);return {vao,buf,ib,count:indices.length,mode};}
function clearMesh(gl,m){if(!m)return;gl.deleteVertexArray(m.vao);gl.deleteBuffer(m.buf);gl.deleteBuffer(m.ib);}
function sphereMesh(gl){const vertices=[],indices=[],N=180,M=96,R=8;
 function bump(lat,lon){let s=.025*Math.sin(26*lon+7*Math.sin(lat*13)) *Math.cos(32*lat)+.018*Math.sin(lon*42+lat*54)+.028*Math.cos(lat*30-lon*17);
 const craters=[[.5,.2,.2,.05],[-1.4,-.3,.26,.07],[2.1,-.6,.15,.034],[-.3,.8,.19,.045],[2.7,.1,.2,.055],[-2,.75,.13,.04],[-.9,-.8,.18,.04],[1.5,1.1,.23,.04]];
 for(const [cl,ct,rad,dep] of craters){let dist=Math.sqrt((lat-ct)**2+(Math.cos(lat)*(Math.atan2(Math.sin(lon-cl),Math.cos(lon-cl))))**2);s-=dep*Math.exp(-Math.pow(dist/rad,4));s+=.48*dep*Math.exp(-Math.pow((dist-rad)/(.22*rad),2));}return s;}
 for(let j=0;j<=M;j++)for(let i=0;i<=N;i++){let lat=-Math.PI/2+Math.PI*j/M,lon=2*Math.PI*i/N,d=[Math.cos(lat)*Math.cos(lon),Math.sin(lat),Math.cos(lat)*Math.sin(lon)],h=bump(lat,lon),r=R*(1+h),p=d.map(a=>a*r);let c=.40+.35*Math.sin(lon*9+lat*13)*Math.cos(lat*16)+.1*Math.sin(lon*23-lat*11);let b=.52+Math.max(0,c)*.26;vertices.push(...p,...d,b*.86,b*.92,b);}
 for(let j=0;j<M;j++)for(let i=0;i<N;i++){let a=j*(N+1)+i,b=a+N+1;indices.push(a,b,a+1,b,b+1,a+1);}
 return mesh(gl,vertices,indices);}
function terrainMesh(gl,dem,uncertainty=0){const N=Math.min(dem.n,133),stride=(dem.n-1)/(N-1),vertices=[],indices=[],zScale=1/650;
 function h(i,j){let x=dem.originX+i*stride*dem.spacing,y=dem.originY+j*stride*dem.spacing;let v=sampleHeight(dem,x+1e-3,y+1e-3);return Number.isFinite(v)?v+uncertainty*scenarioDelta(x,y,dem.seed||17):0;}
 for(let j=0;j<N;j++)for(let i=0;i<N;i++){const x=(dem.originX+i*stride*dem.spacing)/1000,y=(dem.originY+j*stride*dem.spacing)/1000,z=h(i,j),dhx=(h(Math.min(N-1,i+1),j)-h(Math.max(0,i-1),j))/(Math.max(1,(Math.min(N-1,i+1)-Math.max(0,i-1))*stride*dem.spacing)),dhy=(h(i,Math.min(N-1,j+1))-h(i,Math.max(0,j-1)))/(Math.max(1,(Math.min(N-1,j+1)-Math.max(0,j-1))*stride*dem.spacing));let normal=normalize([-dhx*1000/650,1,-dhy*1000/650]);let normalized=(z+450)/1300;let v=.23+.44*Math.max(0,Math.min(1,normalized)),blue=.32+.35*Math.max(0,Math.min(1,normalized));vertices.push(x,z*zScale,y,...normal,v*.9,v,blue);}
 for(let j=0;j<N-1;j++)for(let i=0;i<N-1;i++){let a=j*N+i,b=a+N;indices.push(a,b,a+1,a+1,b,b+1);}
 return mesh(gl,vertices,indices);}
function lineMesh(gl,lines){const verts=[],idx=[];for(let i=0;i<lines.length;i++){const l=lines[i];for(const p of [l.a,l.b]){verts.push(...p,0,1,0,...l.color);}idx.push(2*i,2*i+1);}return mesh(gl,verts,idx,gl.LINES);}
export class LunarScene {
 constructor(canvas,onIssue){this.canvas=canvas;this.onIssue=onIssue;this.mode='local';this.yaw=-.65;this.pitch=.7;this.radius=32;this.light=[1,2,1];this.drag=false;this.sky=null;this.horizon=null;this.ox=0;this.oy=0;this.height=2;
  const gl=canvas.getContext('webgl2',{alpha:true,antialias:true,depth:true,preserveDrawingBuffer:true});if(!gl){onIssue('WebGL2 unavailable. Check chrome://gpu hardware acceleration.');return;}this.gl=gl;
  try{this.shader=program(gl);this.globe=sphereMesh(gl);}catch(e){onIssue(e.message);return;}
  this.loc={pos:gl.getAttribLocation(this.shader,'aPosition'),mvp:gl.getUniformLocation(this.shader,'uMVP'),light:gl.getUniformLocation(this.shader,'uLight')};
  gl.enable(gl.DEPTH_TEST);gl.enable(gl.CULL_FACE);gl.cullFace(gl.BACK);gl.clearColor(0,0,0,0);
  canvas.addEventListener('pointerdown',e=>{this.drag=true;canvas.setPointerCapture(e.pointerId);this.last=[e.clientX,e.clientY];});
  canvas.addEventListener('pointerup',()=>this.drag=false);
  canvas.addEventListener('pointermove',e=>{if(!this.drag)return;this.yaw+=(e.clientX-this.last[0])*.008;this.pitch=Math.max(-1.5,Math.min(1.5,this.pitch+(e.clientY-this.last[1])*.008));this.last=[e.clientX,e.clientY];});
  canvas.addEventListener('wheel',e=>{e.preventDefault();this.radius=Math.max(this.mode==='globe'?11:7,Math.min(75,this.radius*Math.exp(e.deltaY*.001)));},{passive:false});
  this.animate=()=>{this.render();this.raf=requestAnimationFrame(this.animate);};this.animate();
 }
 setTerrain(d,uncertainty=0){if(!this.gl)return;clearMesh(this.gl,this.terrain);this.terrain=terrainMesh(this.gl,d,uncertainty);this.dem=d;this.updateRays();}
 setMode(m){this.mode=m;this.radius=m==='globe'?23:32;this.pitch=m==='globe'?-.7:.75;this.yaw=m==='globe'?-2.3:-.6;this.updateRays();}
 setSun(s){this.sky=s;this.updateRays();}
 setObserver(ox,oy,height){this.ox=ox;this.oy=oy;this.height=height;this.updateRays();}
 updateRays(){if(!this.gl||!this.dem)return;clearMesh(this.gl,this.rays);const base=sampleHeight(this.dem,this.ox,this.oy)||0;let p=[this.ox/1000,(base+this.height)/650+.14,this.oy/1000];let lines=[];if(this.sky&&this.mode==='local')for(let [name,color] of [['sun',[1,.74,.27]],['earth',[.32,.76,1]]]){let v=this.sky[name],a=radians(v.az),e=radians(v.el);lines.push({a:p,b:[p[0]+9*Math.cos(e)*Math.sin(a),p[1]+9*Math.sin(e),p[2]+9*Math.cos(e)*Math.cos(a)],color});}this.rays=lineMesh(this.gl,lines);}
 zoom(dir){this.radius=Math.max(this.mode==='globe'?11:7,Math.min(75,this.radius*dir));}
 reset(){this.setMode(this.mode);}
 render(){if(!this.gl||!this.shader)return;let gl=this.gl,w=this.canvas.clientWidth,h=this.canvas.clientHeight;if(!w||!h)return;const dpr=Math.min(devicePixelRatio||1,2);let nw=Math.round(w*dpr),nh=Math.round(h*dpr);if(this.canvas.width!==nw||this.canvas.height!==nh){this.canvas.width=nw;this.canvas.height=nh;}gl.viewport(0,0,nw,nh);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(this.shader);let cosP=Math.cos(this.pitch),eye=[this.radius*cosP*Math.sin(this.yaw),this.radius*Math.sin(this.pitch),this.radius*cosP*Math.cos(this.yaw)],pv=mul(perspective(.78,w/h,.05,250),lookAt(eye,[0,0,0]));gl.uniformMatrix4fv(this.loc.mvp,false,pv);gl.uniform3fv(this.loc.light,this.light);function draw(m){if(!m)return;gl.bindVertexArray(m.vao);gl.drawElements(m.mode,m.count,gl.UNSIGNED_INT,0);gl.bindVertexArray(null);}
  if(this.mode==='globe')draw(this.globe);else{draw(this.terrain);gl.disable(gl.DEPTH_TEST);draw(this.rays);gl.enable(gl.DEPTH_TEST);}
 }
 snapshot(){return this.canvas.toDataURL('image/png');}
 destroy(){cancelAnimationFrame(this.raf);if(this.gl){for(const m of [this.terrain,this.rays,this.globe])clearMesh(this.gl,m);this.gl.deleteProgram(this.shader);}}
}
