/* Phase D: presentation and diagnostics only. */
const desktopPreview=document.getElementById('desktop-preview'),stageD=document.getElementById('stage'),inspectorD=document.getElementById('pose-inspector');
desktopPreview.addEventListener('change',()=>stageD.classList.toggle('desktop-preview',desktopPreview.checked));
// Observe class changes so the original background selector still works.
new MutationObserver(()=>{if(stageD.classList.contains('desktop-preview')!==desktopPreview.checked)stageD.classList.toggle('desktop-preview',desktopPreview.checked)}).observe(stageD,{attributes:true,attributeFilter:['class']});
setInterval(()=>{if(!inspectorD.parentElement.open)return;const s=KosmosLab.snapshot();inspectorD.textContent=JSON.stringify({state:s.mode,m:s.current.m,breath:s.current.breath,d:s.current.d,amplitude:s.amplitude,transition:s.transition,event:s.event,periodMs:KosmosMotion.periods[s.mode]??KosmosEvents.durations[s.mode]??(s.mode==='standby'?KosmosGeometry.BREATH:KosmosGeometry.DURATION)},null,2)},150);
