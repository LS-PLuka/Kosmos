/* Phase C: motion profiles and event policy; no changes to approved geometry. */
(function(root){'use strict';
const M=typeof module!=='undefined'&&module.exports?require('./motion'):root.KosmosMotion;
const states=['confirmation','success','notification','warning','error'];
const durations={confirmation:3600,success:1500,notification:1400,warning:2200,error:2000};
const isEvent=s=>states.includes(s)&&s!=='confirmation';
const canRepeat=s=>s==='warning'||s==='error';
// Compact raised-cosine envelopes, zero value and velocity at both edges.
function pulse(t,start,end){if(t<=start||t>=end)return 0;return Math.sin(Math.PI*(t-start)/(end-start))**2;}
function params(s,t,repeat=false){const D=durations[s];if(!D)return M.zero();
 if(s==='confirmation'){const p=2*Math.PI*t/D,b=(1-Math.cos(p))/2;return [.055*b,-.04*b,-.065*b,0,.035*b,.032*Math.sin(p)];}
 const p=repeat&&canRepeat(s)?((t%D)+D)%D/D:M.clamp(t/D);
 switch(s){
 case 'success':{const a=pulse(p,0,.65),b=pulse(p,.30,.95);return [.29*a,.085*a-.025*b,.115*a-.035*b,.025*b,-.09*b,.06*a-.04*b];}
 case 'notification':{const a=pulse(p,0,.33),b=pulse(p,.37,.75),v=a+.78*b;return [.13*v,.045*v,.10*v,0,.08*v,.05*v];}
 case 'warning':{const a=pulse(p,0,.30),b=pulse(p,.30,.69),c=pulse(p,.09,.42);return [.14*a+.10*b,-.105*c+.07*b,-.12*c+.085*b,.045*(a-b),.13*(a+b),-.075*c];}
 case 'error':{const a=pulse(p,0,.55),b=pulse(p,.38,.89);return [-.27*a+.055*b,-.08*a+.028*b,-.13*a+.045*b,.115*a-.035*b,.12*a-.035*b,-.13*a+.04*b];}
 default:return M.zero();}}
function pose(s,t,repeat=false){return M.pose(1,0,params(s,t,repeat));}
function destination(policy,previous){if(policy==='previous')return ['standby','core','listening','thinking','executing','speaking','confirmation'].includes(previous)?previous:'core';return ['standby','core','listening','thinking','executing','speaking','confirmation'].includes(policy)?policy:null;}
const api={states,durations,isEvent,canRepeat,params,pose,destination};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.KosmosEvents=api;
})(typeof globalThis!=='undefined'?globalThis:this);
