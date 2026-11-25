const assert=require('node:assert/strict'),G=require('./geometry'),M=require('./motion');
for(let i=0;i<=100;i++){const p=i/100;assert.deepEqual(M.shape(M.pose(p)),G.shape(p));}
for(const state of M.states){const period=M.periods[state];for(let i=0;i<300;i++){const t=period*i/300,a=M.simulatedAudio(state,t),p=M.pose(1,0,M.params(state,t,a)),s=M.shape(p);assert(!/NaN|Infinity/.test(s.orbit+s.ring));const xy=s.orbit.match(/[-+]?(?:\d*\.\d+|\d+\.?\d*)/g).map(Number);assert.deepEqual(xy.slice(0,2),xy.slice(-2));assert(xy.every(x=>x>0&&x<320));}const a=M.params(state,0,M.simulatedAudio(state,0)),b=M.params(state,period,M.simulatedAudio(state,period));assert(a.every((x,i)=>Math.abs(x-b[i])<1e-10));}
for(const state of ['listening','speaking'])assert(M.params(state,0,1)[0]>M.params(state,0,0)[0]);
console.log('Geometry: exact phase A at zero deformation; 1,200 finite closed paths; cycle endpoints; audio response.');
