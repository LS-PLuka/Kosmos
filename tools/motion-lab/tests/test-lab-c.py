from pathlib import Path
from playwright.sync_api import sync_playwright
import shutil
root=Path(__file__).resolve().parent.parent
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox']);page=b.new_page(viewport={'width':1280,'height':950});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.clock.install();page.set_content((root/'previews/playground-phase-c.html').read_text());page.clock.pause_at(page.evaluate('Date.now()')+100)
 def snap():return page.evaluate('KosmosLab.snapshot()')
 def advance(ms):page.clock.run_for(ms)
 def click(sel):page.locator(sel).evaluate('(e)=>e.click()')
 def select(sel,value):page.locator(sel).evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("change"));}',value)
 def req(s):
  a,z=page.evaluate('(s)=>{let a=KosmosLab.snapshot();KosmosLab.requestState(s);return [a,KosmosLab.snapshot()]}',s);assert a['current']==z['current'],(s,a,z)
 def expect(s):assert snap()['mode']==s and not snap()['transition'],snap()
 req('thinking');advance(1800);expect('thinking');req('confirmation');advance(500);expect('confirmation');advance(7500);expect('confirmation');click('#approve');advance(500);expect('executing');req('confirmation');advance(500);click('#decline');advance(1600);expect('standby')
 # One-shot from standby auto-awakens, then returns through sleeping.
 click('#proactive');advance(1750);expect('notification');advance(1450);assert snap()['mode'] in ['core','sleeping','standby'];advance(1500);expect('standby')
 req('executing');advance(1800);click('#complete');advance(500);expect('success');advance(2050);expect('executing');select('#event-return','speaking');click('#fail');advance(500);expect('error');advance(2550);expect('speaking')
 select('#event-return','hold');click('#warn');advance(2800);expect('warning');assert snap()['event']['done'] and all(abs(v)<1e-10 for v in snap()['current']['d']);click('#repeat-alert');advance(4800);expect('warning');assert snap()['event']['repeat'];click('#repeat-alert');advance(2400);assert snap()['event']['done'];
 for s in ['success','notification','warning','error','confirmation','standby','listening','core']:
  req(s);advance(170)
 advance(1700);expect('core')
 # Verify all requested flows and explicit decisions, polling modes in simulated time.
 for name,order,decision in [('approve',['thinking','confirmation','executing'],'#approve'),('decline',['confirmation','sleeping','standby'],'#decline'),('success',['executing','success','speaking'],None),('error',['executing','error','speaking'],None),('notification',['standby','awakening','notification','speaking'],None),('warning',['standby','awakening','warning','speaking'],None),('sleep',['speaking','sleeping','standby'],None)]:
  select('#scenario',name);click('#play-scenario');seen=[];did=False
  for i in range(130):
   a=snap();m=a['mode'];
   if not seen or m!=seen[-1]:seen.append(m)
   if decision and m=='confirmation' and not a['transition'] and not did:click(decision);did=True;advance(100);continue
   if not a['sequence'] and not a['transition'] and (not decision or did):break
   advance(100)
  cursor=-1
  for m in order:cursor=seen.index(m,cursor+1)
  expect(order[-1]);print(name,seen,flush=True)
 assert not errors,errors
 req('confirmation');advance(1800);page.screenshot(path=str(root/'previews/lab-phase-c.png'),full_page=True);print('Phase C: all seven flows, indefinite confirmation, decisions, event return/hold/repeat, interruptions; no page errors.');b.close()
