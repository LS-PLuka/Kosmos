/* Kosmos — Phase A. One shared cubic geometry, fixed coordinate system. */
(function(root){
'use strict';
const PALETTE={void:'#0D0912',nebula:'#25192D',cosmic:'#683A79',nova:'#BE6BB7',starlight:'#F4EAF7'};
const VIEW=320, DURATION=1200, BREATH=3200;
// Cubic anchors traced from the approved board. Start at upper tapered tip;
// follow inside contour to lower tip, then outside contour back to start.
const rawStandby=[
 [1065,148],
 [1117,124,1168,112,1172,151],
 [1177,189,1123,239,1083,266],
 [1042,294,992,319,971,313],
 [956,309,954,301,957,286],
 [938,317,957,342,1008,323],
 [1063,305,1128,253,1160,213],
 [1190,178,1207,139,1188,120],
 [1164,94,1110,116,1065,148]
];
const rawCore=[
 [1452,172],
 [1510,136,1599,111,1605,158],
 [1613,193,1568,244,1523,276],
 [1479,306,1420,321,1408,287],
 [1397,260,1435,216,1466,196],
 [1416,222,1369,275,1377,306],
 [1386,345,1454,327,1515,290],
 [1571,255,1638,190,1638,145],
 [1639,97,1564,95,1452,172]
];
// Optical orbital box centers from the approved board. One common scale.
const scale=0.92;
function normalize(arr,cx,cy){return arr.map(seg=>seg.map((v,i)=>(v-(i%2?cy:cx))*scale+160));}
const A=normalize(rawStandby,1073.5,220), B=normalize(rawCore,1507,219);
const whiteA=[(1066-1073.5)*scale+160,(236-220)*scale+160,74*scale,49.5*scale];
const whiteB=[(1502-1507)*scale+160,(223.5-219)*scale+160,28.5*scale,0];
// Gradient stops sampled approximately from approved raster, with official Nova
// and Starlight used as anchors. Violet endpoint is already present in the board.
const colorA=['#AD70BD','#B16EB9'], colorB=['#893DB7',PALETTE.nova];
const clamp=(t)=>Math.max(0,Math.min(1,t));
const mix=(a,b,t)=>a+(b-a)*t;
const ease=(t)=>{t=clamp(t);return t*t*t*(t*(6*t-15)+10);};
function color(a,b,t){return '#'+[1,3,5].map(i=>Math.round(mix(parseInt(a.slice(i,i+2),16),parseInt(b.slice(i,i+2),16),t)).toString(16).padStart(2,'0')).join('');}
const n=(v)=>Number(v.toFixed(4));
function shape(m,breath=0){m=clamp(m);breath=clamp(breath)*(1-m);
 const p=A.map((seg,j)=>seg.map((v,i)=>mix(v,B[j][i],m)));
 const w=whiteA.map((v,i)=>mix(v,whiteB[i],m));
 w[2]*=1+breath*.008;w[3]*=1+breath*.008;
 const orbit='M'+p[0].map(n).join(' ')+' '+p.slice(1).map(seg=>'C'+seg.map(n).join(' ')).join(' ')+' Z';
 const [x,y,R,r]=w.map(n);
 function circle(rad){return `M ${n(x-rad)} ${y} a ${rad} ${rad} 0 1 0 ${n(2*rad)} 0 a ${rad} ${rad} 0 1 0 ${n(-2*rad)} 0 Z`;}
 const ring=circle(R)+(r>0.001?' '+circle(r):'');
 return {orbit,ring,cut:n(5.5*(1-m)),c1:color(colorA[0],colorB[0],m),c2:color(colorA[1],colorB[1],m),white:PALETTE.starlight,m};
}
function svg(m,breath=0,bg=null,px=320){const s=shape(m,breath);return `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 320 320" role="img" aria-label="Kosmos"><defs><linearGradient id="orbit-gradient" gradientUnits="userSpaceOnUse" x1="50" y1="250" x2="270" y2="75"><stop stop-color="${s.c1}"/><stop offset="1" stop-color="${s.c2}"/></linearGradient><mask id="orbit-clearance" maskUnits="userSpaceOnUse" maskContentUnits="userSpaceOnUse" x="0" y="0" width="320" height="320" style="mask-type:luminance"><rect width="320" height="320" fill="white"/><path d="${s.orbit}" fill="black" stroke="black" stroke-width="${s.cut}" stroke-linejoin="round"/></mask></defs>${bg?`<rect width="320" height="320" fill="${bg}"/>`:''}<path d="${s.ring}" fill-rule="evenodd" fill="${s.white}" mask="url(#orbit-clearance)"/><path d="${s.orbit}" fill="url(#orbit-gradient)"/></svg>`;}
function frame(state,t){if(state==='standby')return {m:0,breath:(1-Math.cos(2*Math.PI*t/BREATH))/2};const k=ease(t/DURATION);return {m:state==='sleeping'?1-k:k,breath:0};}
const api={PALETTE,VIEW,DURATION,BREATH,shape,svg,frame,ease};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.KosmosGeometry=api;
})(typeof globalThis!=='undefined'?globalThis:this);
