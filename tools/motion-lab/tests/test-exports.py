from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parent.parent
for state,count in [('listening',144),('thinking',96),('executing',48),('speaking',144)]:
    for ext in ('gif','webp'):
        path=root/'animations'/state/f'{state}.{ext}'
        with Image.open(path) as im:
            assert im.n_frames==count and im.size==(320,320) and im.info['loop']==0
            duration=0
            for i in range(count):
                im.seek(i);im.load();duration+=im.info['duration']
                if ext=='webp':assert im.convert('RGBA').getpixel((0,0))[3]==0
            assert duration==round(count*1000/30)
            print(state,ext,count,duration,'ms')
