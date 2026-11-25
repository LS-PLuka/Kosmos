const fs=require('fs'),M=require('./motion'),E=require('./events');const frames={};
for(const s of E.states){const n=Math.round(E.durations[s]*30/1000),count=s==='confirmation'?n:n+1;frames[s]=Array.from({length:count},(_,i)=>M.svg(E.pose(s,i*E.durations[s]/n)));}fs.writeFileSync(process.argv[2],JSON.stringify(frames));
