from pathlib import Path
from PIL import Image
import hashlib, json, shutil, xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright
r=Path(__file__).resolve().parents[3]; a=r/'assets/branding'; lab=r/'tools/motion-lab'; m=json.loads((r/'approved-manifest.json').read_text())
for old,item in m.items(): assert hashlib.sha256((r/item['path']).read_bytes()).hexdigest()==item['sha256'],old
print('Approved hashes:',len(m))
for f in a.rglob('*.svg'):ET.parse(f)
for n in [16,24,32,48,64,128,256,512,1024]:
 with Image.open(a/'icons'/f'kosmos-{n}.png') as im:assert im.size==(n,n) and im.mode=='RGBA' and im.getchannel('A').getextrema()==(0,255),n
print('Icon sizes and alpha: 9/9; SVG XML valid.')
for f in (a/'logos').glob('*.png'):
 with Image.open(f) as im:assert im.mode=='RGBA' and im.getchannel('A').getextrema()==(0,255),f
states=['standby','awakening','listening','thinking','executing','speaking','confirmation','success','notification','warning','error','sleeping']
for state in states:
 for ext in ['gif','webp']:
  with Image.open(a/'animations'/state/f'{state}.{ext}') as im:
   assert im.is_animated and im.size==(320,320)
   if ext=='webp':
    for i in range(im.n_frames):im.seek(i);assert im.convert('RGBA').getpixel((0,0))[3]==0
   else:
    for i in range(im.n_frames):im.seek(i);assert im.convert('RGB').getpixel((0,0))==(13,9,18)
 print(state,'GIF + WebP decoded')
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox']);page=b.new_page(viewport={'width':1280,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.set_content((lab/'index.html').read_text());page.locator('#desktop-preview').check();assert 'desktop-preview' in page.locator('#stage').get_attribute('class');page.locator('#bg').select_option('light');page.wait_for_function('document.getElementById("stage").classList.contains("desktop-preview")');page.locator('#final-tools summary').click();page.wait_for_function('document.getElementById("pose-inspector").textContent.includes("amplitude")');page.locator('#desktop-preview').uncheck();page.locator('#bg').select_option('void');page.locator('[data-state=thinking]').click();page.wait_for_function('KosmosLab.snapshot().mode==="thinking"&&!KosmosLab.snapshot().transition');assert not errors,errors
 page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(a/'previews/lab-final.png'),full_page=True);b.close()
print('Final lab diagnostics and desktop positioning pass; no JS errors.')
