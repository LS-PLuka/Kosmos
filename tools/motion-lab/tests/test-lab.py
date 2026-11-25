from pathlib import Path
from playwright.sync_api import sync_playwright
import math, shutil
root=Path(__file__).resolve().parent.parent
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']);ctx=b.new_context(viewport={'width':1280,'height':1000});page=ctx.new_page();errors=[];page.on('pageerror',lambda e: errors.append(str(e)));page.set_content((root/'previews/playground-phase-b.html').read_text());
 # The sandbox blocks file and localhost navigations. Supply a controlled local
 # Web Audio stream to exercise the analyser and permission workflow instead.
 page.evaluate("""Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:async()=>{const c=new AudioContext();await c.resume();const o=c.createOscillator(),gain=c.createGain(),d=c.createMediaStreamDestination();gain.gain.value=.12;o.connect(gain).connect(d);o.start();window.__testAudio={c,o};return d.stream;}}})""");
 def snap():return page.evaluate('KosmosLab.snapshot()')
 def until(state,timeout=5000):page.wait_for_function('(s)=>KosmosLab.snapshot().mode===s&&!KosmosLab.snapshot().transition',arg=state,timeout=timeout)
 page.locator('[data-state=listening]').click();until('listening');page.locator('#audio-source').select_option('manual');page.locator('#audio').evaluate('(e)=>{e.value=100;e.dispatchEvent(new Event("input"))}');page.wait_for_function('KosmosLab.snapshot().amplitude>.97');assert snap()['current']['d'][0]>.15
 # Snapshot immediately after invoking a transition, before any animation frame.
 for state in ['thinking','executing','speaking','standby','listening','standby','core']:
  before,after=page.evaluate('(s)=>{let a=KosmosLab.snapshot();KosmosLab.requestState(s);return [a,KosmosLab.snapshot()]}',state);assert before['current']==after['current'];page.wait_for_timeout(100)
 until('core');page.locator('#sleep').click();page.wait_for_timeout(250);page.locator('#activate').click();until('core');page.locator('#rest').click();until('standby');
 page.locator('#scrub').evaluate('(e)=>{e.value=420;e.dispatchEvent(new Event("input"))}');assert abs(snap()['current']['m']-.42)<1e-6;page.locator('#size').evaluate('(e)=>{e.value=64;e.dispatchEvent(new Event("input"))}');assert page.locator('#symbol').evaluate('(e)=>e.style.width')=='64px';page.locator('#bg').select_option('checker');assert 'checker' in page.locator('#stage').get_attribute('class');page.locator('#bg').select_option('void');page.locator('#size').evaluate('(e)=>{e.value=320;e.dispatchEvent(new Event("input"))}');
 page.locator('#audio-source').select_option('auto');page.locator('[data-state=speaking]').click();until('speaking');page.wait_for_function('KosmosLab.snapshot().amplitude>.15');
 page.locator('#audio-source').select_option('mic');page.wait_for_function('KosmosLab.snapshot().audioMode==="mic"',timeout=10000);page.wait_for_function('KosmosLab.snapshot().amplitude>.02',timeout=5000);page.locator('#mic-stop').click();assert snap()['audioMode']=='manual';
 # Exercise permission error branch without accessing a physical device.
 page.evaluate('()=>{navigator.mediaDevices.getUserMedia=()=>Promise.reject(new DOMException("denied","NotAllowedError"));}');page.locator('#audio-source').select_option('mic');page.wait_for_function('document.getElementById("mic-status").textContent.includes("não autorizado")');assert snap()['audioMode']=='manual';
 page.locator('#audio-source').select_option('auto');page.locator('#full-flow').click();seen=[]
 for i in range(200):
  s=snap();
  if not seen or seen[-1]!=s['mode']:seen.append(s['mode'])
  if not s['sequence']:break
  page.wait_for_timeout(100)
 for state in ['awakening','listening','thinking','executing','speaking','sleeping','standby']:assert state in seen,(state,seen)
 cursor=-1
 for state in ['awakening','listening','thinking','executing','speaking','sleeping','standby']:
  cursor=seen.index(state,cursor+1)
 assert not snap()['sequence'];assert not errors,errors
 page.locator('[data-state=thinking]').click();until('thinking');page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(root/'previews/lab-phase-b.png'),full_page=True);print('Chromium: state transitions, interruption, scrub, size, backgrounds, manual/auto/mic (virtual), denied permission, flow:',seen);b.close()
