"""Export real GIF and transparent WebP frames with Chromium's SVG renderer.
Requires Python Pillow + playwright; Chromium available on PATH.
Run from any directory: python source/export-phase-c.py
"""
import io,json,subprocess,shutil,tempfile
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as tmp:
    data=Path(tmp)/'frames.json'
    subprocess.run(['node',str(ROOT/'source/render-phase-c.js'),str(data)],check=True)
    frames=json.loads(data.read_text())
SIZE=320
VOID=(13,9,18,255)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':SIZE,'height':SIZE},device_scale_factor=1)
    page.set_content('<style>html,body{margin:0;background:transparent;overflow:hidden}svg{display:block}</style><main></main>')
    def render(svg):
        page.locator('main').evaluate('(el,s)=>el.innerHTML=s',svg)
        return Image.open(io.BytesIO(page.screenshot(omit_background=True,animations='disabled'))).convert('RGBA')
    for state,svgs in frames.items():
        target=ROOT/'animations'/state
        target.mkdir(exist_ok=True,parents=True)
        imgs=[render(s) for s in svgs]
        # 30 fps average. Endpoint holds allow the one-shot GIF to settle.
        durations=[round((i+1)*1000/30)-round(i*1000/30) for i in range(len(imgs))]
        if state!='confirmation':durations[-1]=250
        dark=[]
        for img in imgs:
            bg=Image.new('RGBA',img.size,VOID);bg.alpha_composite(img);dark.append(bg.convert('RGB'))
        # shared palette avoids per-frame color shifts
        strip=Image.new('RGB',(SIZE,SIZE*len(dark)))
        for i,img in enumerate(dark):strip.paste(img,(0,i*SIZE))
        pal=strip.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
        gif=[im.quantize(palette=pal,dither=Image.Dither.NONE) for im in dark]
        gif_durations=[10*(round(sum(durations[:i+1])/10)-round(sum(durations[:i])/10)) for i in range(len(durations))]
        opts={'loop':0} if state=='confirmation' else {}
        gif[0].save(target/f'{state}.gif',save_all=True,append_images=gif[1:],duration=gif_durations,disposal=2,optimize=False,**opts)
        imgs[0].save(target/f'{state}.webp',save_all=True,append_images=imgs[1:],duration=durations,loop=0 if state=='confirmation' else 1,lossless=True,method=4)
        print(state,len(imgs),sum(durations),flush=True)
    browser.close()
