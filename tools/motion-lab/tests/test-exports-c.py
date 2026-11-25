from pathlib import Path
from PIL import Image,ImageChops
root=Path(__file__).resolve().parent.parent
D={'confirmation':3600,'success':1500,'notification':1400,'warning':2200,'error':2000}
for s,d in D.items():
 for ext in ('gif','webp'):
  with Image.open(root/'animations'/s/f'{s}.{ext}') as im:
   assert im.size==(320,320) and im.is_animated and im.n_frames>20
   assert im.info.get('loop',None)==(0 if s=='confirmation' else (None if ext=='gif' else 1)),(s,ext,im.info)
   first=im.convert('RGBA');total=0
   for i in range(im.n_frames):
    im.seek(i);im.load();total+=im.info.get('duration',0)
    if ext=='webp':assert im.convert('RGBA').getchannel('A').getextrema()==(0,255)
   expected=d+(0 if s=='confirmation' else 250)
   assert abs(total-expected)<=20,(s,ext,total,expected)
   if s!='confirmation':
    last=im.convert('RGBA');bg=Image.new('RGBA',first.size,(13,9,18,255));a=bg.copy();b=bg.copy();a.alpha_composite(first);b.alpha_composite(last)
    assert first.getchannel('A').tobytes()==last.getchannel('A').tobytes() and all(channel.getbbox() is None for channel in ImageChops.difference(a,b).split()),(s,ext,'endpoint')
   print(s,ext,im.n_frames,total,'ms')
