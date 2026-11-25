/* Phase B: additive, zero-at-rest deformation of Phase A geometry. */
(function(root){'use strict';
const G=typeof module!=='undefined'&&module.exports?require('./geometry.js'):root.KosmosGeometry;
const TAU=2*Math.PI, clamp=x=>Math.max(0,Math.min(1,x)), mix=(a,b,t)=>a+(b-a)*t;
const states=['listening','thinking','executing','speaking'];
const periods={listening:4800,thinking:3200,executing:1600,speaking:4800};
const zero=()=>[0,0,0,0,0,0]; // nucleus, longitudinal, transverse, alternation, thickness, tips
const wave=(p,k=1,offset=0)=>Math.sin(TAU*(p*k+offset));
function simulatedAudio(state,t){const p=((t%4800)+4800)%4800/4800;
 const bursts=state==='speaking'?[[.07,.055,.82],[.18,.045,.54],[.29,.07,.92],[.46,.05,.68],[.60,.08,.96],[.77,.045,.45],[.87,.06,.74]]:[[.12,.08,.64],[.32,.06,.82],[.48,.045,.40],[.72,.09,.72],[.88,.045,.48]];
 let out=0;for(const [c,w,a] of bursts){const d=Math.min(Math.abs(p-c),1-Math.abs(p-c));if(d<w)out+=a*Math.pow(Math.cos(Math.PI*d/(2*w)),2);}
 return clamp(out);}
function params(state,t,a=0){a=clamp(a);const p=t/(periods[state]||3200),s=wave(p),c=wave(p,1,.25);
 switch(state){
 case 'listening':return [.015*(1+c)/2+.18*a, .015+.055*a, .012*s+.10*a, .014*s, .025+.10*a, .025*s+.05*a];
 case 'thinking':return [.022*s,.018*c,.045*wave(p,2),.15*s,.045*wave(p,1,.15),.11*wave(p,1,.25)];
 case 'executing':{const beat=Math.pow((1-Math.cos(TAU*p))/2,2),echo=Math.pow((1-Math.cos(TAU*(p-.19)))/2,3);return [.045*beat,.12*beat-.025,.14*beat-.025,.045*wave(p,2),.23*echo-.04,.09*beat];}
 case 'speaking':return [.025*s+.37*a,.018*s+.065*a,.025*c+.19*a,.055*wave(p,3)*a,.16*a,.055*wave(p,2)+.10*a];
 default:return zero();}}
function pose(m=1,breath=0,d=zero()){return {m,breath,d:[...d]};}
function blend(a,b,t){return pose(mix(a.m,b.m,t),mix(a.breath,b.breath,t),a.d.map((v,i)=>mix(v,b.d[i],t)));}
const num=/[-+]?(?:\d*\.\d+|\d+\.?\d*)/g, round=x=>Number(x.toFixed(4));
function shape(p){const s=G.shape(p.m,p.breath);if(p.d.every(x=>x===0)||p.m===0)return s;
 const [n,ax,tr,alt,th,tip]=p.d.map(x=>x*p.m), cx=160,cy=160;
 // Fixed diagonal basis (no angular animation). Changes are along/perpendicular to the orbit.
 const ux=.78,uy=-Math.sqrt(1-.78*.78),vx=-uy,vy=ux;
 let k=0,values=s.orbit.match(num).map(Number),out=[];
 // Signed radial expansion on inner and outer contour, tapered to both shared tips.
 const weights=[0,-.45,-1,-1,-1,-1,-1,-1,-1,-1,-1,-.45,0,.45,1,1,1,1,1,1,1,1,1,.45,0];
 for(let i=0;i<values.length;i+=2){let x=values[i]-cx,y=values[i+1]-cy,u=x*ux+y*uy,v=x*vx+y*vy;
  const side=Math.tanh(u/80),end=Math.min(1,Math.abs(u)/125),rad=1+th*(weights[k++]||0)*.22;
  const U=u*(1+ax+alt*side*.50)*rad;
  const V=v*(1+tr-alt*side*.65)*rad+tip*end*end*12;
  out.push(round(cx+U*ux+V*vx),round(cy+U*uy+V*vy));}
 let i=0;s.orbit=s.orbit.replace(num,()=>String(out[i++]));
 const a=s.ring.match(num).map(Number); // original arc path; adjust radii about original center
 const R=a[2],x=a[0]+R,y=a[1],r=R*(1+n);const circle=z=>`M ${round(x-z)} ${y} a ${round(z)} ${round(z)} 0 1 0 ${round(2*z)} 0 a ${round(z)} ${round(z)} 0 1 0 ${round(-2*z)} 0 Z`;
 s.ring=circle(r)+(a.length>16?' '+circle(a[18]*(1+n)):'');return s;
}
function svg(p,bg=null,px=320){const base=G.shape(p.m,p.breath),s=shape(p);return G.svg(p.m,p.breath,bg,px).split(`d="${base.orbit}"`).join(`d="${s.orbit}"`).replace(`d="${base.ring}"`,`d="${s.ring}"`);}
const api={states,periods,simulatedAudio,params,pose,blend,shape,svg,zero,clamp};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.KosmosMotion=api;
})(typeof globalThis!=='undefined'?globalThis:this);
