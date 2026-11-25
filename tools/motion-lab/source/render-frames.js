const fs=require('fs'),path=require('path'),G=require('./geometry.js');
const root=path.resolve(__dirname,'..');
for (const [name,m] of [['institutional',0],['core',1]]) fs.writeFileSync(path.join(root,'core/static',name+'.svg'),G.svg(m));
const frames={};for(const state of ['standby','awakening','sleeping']){const count=state==='standby'?96:37;frames[state]=Array.from({length:count},(_,i)=>{const t=state==='standby'?i*G.BREATH/count:i*G.DURATION/(count-1);const f=G.frame(state,t);return G.svg(f.m,f.breath);});}
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(frames));
