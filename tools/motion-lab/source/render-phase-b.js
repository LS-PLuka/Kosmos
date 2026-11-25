const fs=require('fs'),M=require('./motion');const frames={};
for(const state of M.states){const count=Math.round(M.periods[state]*30/1000);frames[state]=Array.from({length:count},(_,i)=>{const t=i*M.periods[state]/count;return M.svg(M.pose(1,0,M.params(state,t,M.simulatedAudio(state,t))));});}fs.writeFileSync(process.argv[2],JSON.stringify(frames));
