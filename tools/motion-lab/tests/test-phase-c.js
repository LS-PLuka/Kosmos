const assert=require('node:assert/strict'),G=require('./geometry'),M=require('./motion'),E=require('./events');
const neutral=M.pose(1);let paths=0;
for(const s of E.states){const D=E.durations[s];assert(E.pose(s,0).d.every(x=>x===0));assert(E.params(s,D).every(x=>Math.abs(x)<1e-10));assert.deepEqual(M.shape(E.pose(s,0)),G.shape(1));
 for(let i=0;i<=500;i++){const p=E.pose(s,D*i/500),sh=M.shape(p),xy=sh.orbit.match(/[-+]?(?:\d*\.\d+|\d+\.?\d*)/g).map(Number);assert(xy.every(x=>Number.isFinite(x)&&x>0&&x<320));assert.deepEqual(xy.slice(0,2),xy.slice(-2));assert(!/NaN|Infinity/.test(sh.ring));assert.equal(sh.c1,G.shape(1).c1);assert.equal(sh.c2,G.shape(1).c2);paths++;}
 if(E.canRepeat(s))for(let i=0;i<100;i++)assert(E.params(s,D*i/100,true).every((x,j)=>Math.abs(x-E.params(s,D+D*i/100,true)[j])<1e-10));
 if(E.isEvent(s))assert(E.pose(s,D*2).d.every(x=>x===0));}
assert(E.params('success',450)[0]>.25);assert(E.params('error',500)[0]<-.20);assert(E.params('notification',.165*1400)[0]>.12);assert(E.params('notification',.35*1400)[0]===0);assert(E.params('notification',.56*1400)[0]>.09);assert(E.params('confirmation',1800)[2]<0);assert(E.destination('previous','thinking')==='thinking');assert(E.destination('hold','thinking')===null);
for(const a of [...M.states,...E.states])for(const b of [...M.states,...E.states]){const get=s=>E.states.includes(s)?E.pose(s,550):M.pose(1,0,M.params(s,550,.7));assert(M.blend(get(a),get(b),0).d.every((x,i)=>x===get(a).d[i]));assert(M.blend(get(a),get(b),1).d.every((x,i)=>Math.abs(x-get(b).d[i])<1e-10));}
console.log(`${paths} finite closed paths, neutral endpoints, repeat seams, motion signatures, 81 transition pairs, event destinations.`);
