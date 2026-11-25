"""Trace the approved wordmark bitmap; render all vectors using Chromium (SVG luminance masks)."""
from pathlib import Path
import cv2, numpy as np, json, shutil
from skimage.measure import find_contours
from scipy.ndimage import gaussian_filter
from PIL import Image
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[3]; a=root/'assets/branding'
im=np.array(Image.open(a/'reference/approved-brand-board.png').convert('RGB').crop((120,100,845,340)))
r,g,b=im.astype(float).transpose(2,0,1); y=np.indices(r.shape)[0]
# Separate bright lettering, purple orbit and lavender slogan. No font substitution.
word=(g>155)&(r>175)&((b-g)<45)&(y<187)
orb=(r>75)&(b>95)&((b-g)>25)&(y<187)&~word
slogan=(r>115)&(b>130)&(y>=187)
def trace(mask):
 # Subpixel iso-contours remove raster staircase artifacts, without changing layout.
 field=gaussian_filter(mask.astype(float),.60)
 result=[]
 for c in find_contours(field,.48):
  c=c[:,::-1].astype('float32')
  if cv2.contourArea(c)<.8:continue
  p=cv2.approxPolyDP(c,.18,True).reshape(-1,2)
  if len(p)<3:continue
  result.append('M'+' L'.join(f'{x:.2f} {y:.2f}' for x,y in p)+' Z')
 return ' '.join(result)
paths={k:trace(v) for k,v in [('word',word),('orbit',orb),('slogan',slogan)]}
(a/'logos/wordmark-contours.json').write_text(json.dumps({'source':'reference/approved-brand-board.png','crop':[120,100,845,340],'paths':paths},indent=2))
for variant,fg,secondary,orbcol,bg in [('dark','#F4EAF7','#CDB6D6',None,None),('light','#0D0912','#25192D',None,None),('mono-white','#F4EAF7','#F4EAF7','#F4EAF7',None),('mono-black','#000000','#000000','#000000',None)]:
 for tagline in (True,False):
  name='kosmos-'+variant+('-tagline' if tagline else '')
  vb='12 4 702 228' if tagline else '12 4 702 183'; h=228 if tagline else 183
  defs='<defs><linearGradient id="orbit" gradientUnits="userSpaceOnUse" x1="104" y1="180" x2="273" y2="22"><stop stop-color="#AD70BD"/><stop offset="1" stop-color="#B16EB9"/></linearGradient></defs>'
  svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="702" height="{h}" viewBox="{vb}" role="img" aria-label="Kosmos">{defs}<path fill-rule="evenodd" fill="{fg}" d="{paths["word"]}"/><path fill-rule="evenodd" fill="{orbcol or "url(#orbit)"}" d="{paths["orbit"]}"/>'+(f'<path fill-rule="evenodd" fill="{secondary}" d="{paths["slogan"]}"/>' if tagline else '')+'</svg>'
  (a/'logos'/f'{name}.svg').write_text(svg)
# Monochrome variants of the approved vector: keep the real clearance mask intact.
for name, color in [('white','#F4EAF7'),('black','#000000')]:
 src=(a/'symbols/institutional.svg').read_text().replace('fill="#F4EAF7" mask=',f'fill="{color}" mask=').replace('fill="url(#orbit-gradient)"',f'fill="{color}"')
 (a/'symbols'/f'institutional-mono-{name}.svg').write_text(src)
# Light variant only for static institutional applications, not active motion.
(a/'symbols/institutional-light.svg').write_text((a/'symbols/institutional.svg').read_text().replace('fill="#F4EAF7" mask=','fill="#0D0912" mask='))
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox']); page=browser.new_page()
 def render(src,dst,w,h):
  page.set_viewport_size({'width':w,'height':h}); page.set_content('<style>html,body{margin:0;background:transparent}svg{display:block;width:100vw;height:100vh}</style>'+src);page.screenshot(path=str(dst),omit_background=True)
 for f in (a/'logos').glob('*.svg'):
  h=456 if 'tagline' in f.stem else 366;render(f.read_text(),f.with_suffix('.png'),1404,h)
 for f in (a/'symbols').glob('*.svg'):
  if f.stem!='institutional':render(f.read_text(),f.with_suffix('.png'),1024,1024)
 for n in [16,24,32,48,64,128,256,512,1024]:
  render((a/'symbols/institutional.svg').read_text(),a/'icons'/f'kosmos-{n}.png',n,n)
 for n in [16,24,32,48,64]:
  for c in ['white','black']:render((a/'symbols'/f'institutional-mono-{c}.svg').read_text(),a/'icons'/f'tray-{c}-{n}.png',n,n)
 render((a/'core/core.svg').read_text(),a/'core/core-1024.png',1024,1024)
 browser.close()
shutil.copy2(a/'symbols/institutional.svg',a/'icons/favicon.svg')
Image.open(a/'icons/kosmos-64.png').save(a/'icons/favicon.ico',sizes=[(16,16),(32,32),(48,48),(64,64)])
for size,name in [(512,'github-avatar'),(1024,'app-icon-void')]:
 im=Image.new('RGBA',(size,size),'#0D0912');im.alpha_composite(Image.open(a/'icons'/f'kosmos-{size}.png'));im.convert('RGB').save(a/'icons'/f'{name}.png')
print('Brand vectors and icons generated.')
