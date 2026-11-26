"""Screenshot coordinates, animated teaching pointer and click highlights.

These overlays illustrate actions; they never click the user's real desktop.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def templates():
    return json.loads((ROOT/'assets/templates.json').read_text())['templates']

def settings(overrides=None,template=None):
    result = json.loads((ROOT/'assets/style-default.json').read_text())
    if template:
        chosen=next((t for t in templates() if t['id']==template),None)
        if chosen is None:raise ValueError('Unknown template: '+str(template))
        result.update(chosen['style'])
    result.update(overrides or {})
    if not isinstance(result['fps'], int) or not 10 <= result['fps'] <= 30:
        raise ValueError('style.fps must be an integer from 10 to 30')
    for key, low, high in [('tail_seconds',0,5),('pointer_scale',.5,2),('click_seconds',.1,2)]:
        number = float(result[key])
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError('Invalid style setting: ' + key)
        result[key] = number
    return result

def image_placement(size,height=670):
    from PIL import Image, ImageOps
    # Must match the screenshot area in studio.make_card.
    w, h = ImageOps.contain(Image.new('L',size), (1720,height)).size
    return (1920-w)//2, 248+(height-h)//2, w, h

def image_point(x,y,size,height=670):
    x,y=float(x),float(y)
    if not math.isfinite(x) or not math.isfinite(y) or not 0 <= x <= size[0] or not 0 <= y <= size[1]:
        raise ValueError('Visual target is outside source image')
    left,top,w,h=image_placement(size,height)
    return left+x*w/size[0],top+y*h/size[1]

def review_regions(scene,base,style):
    """Map explicitly important UI regions and numbered markers to final pixels."""
    size=None
    if scene.get('image'):
        from PIL import Image
        source=Path(scene['image']);source=source if source.is_absolute() else base/source
        with Image.open(source) as im:size=im.size
    protected=[];markers=[]
    for i,region in enumerate(scene.get('protected_regions',[]),1):
        x,y,w,h=[float(region[k]) for k in ('x','y','width','height')]
        if not all(math.isfinite(v) for v in (x,y,w,h)) or w<=0 or h<=0:raise ValueError('Invalid protected region')
        space=region.get('space','image' if size else 'frame')
        if space=='image':
            if size is None:raise ValueError('Image-space protected region needs scene.image')
            a,b=image_point(x,y,size,style.get('picture_height',670));c,d=image_point(x+w,y+h,size,style.get('picture_height',670))
            x,y,w,h=a,b,c-a,d-b
        elif space!='frame':raise ValueError('Protected region space must be image or frame')
        if x<0 or y<0 or x+w>1920 or y+h>1080:raise ValueError('Protected region is outside final frame')
        protected.append({'label':str(region.get('label',f'region-{i}')),'x':x,'y':y,'width':w,'height':h})
    if size:
        for marker in scene.get('callouts',[]):
            x,y=image_point(marker['x'],marker['y'],size,style.get('picture_height',670))
            markers.append({'x':x-27,'y':y-27,'width':54,'height':54})
    return protected,markers

def pointer_plan(scene,seconds,base,style=None):
    config=scene.get('pointer')
    if not config:
        return []
    space=config.get('space','image' if scene.get('image') else 'frame')
    if space not in ('image','frame'):
        raise ValueError('pointer.space must be image or frame')
    if space=='image':
        from PIL import Image
        if not scene.get('image'):
            raise ValueError('Image-space pointer requires scene.image')
        source=Path(scene['image']).expanduser()
        with Image.open(source if source.is_absolute() else base/source) as im:
            size=im.size
    keys=config.get('keyframes',[])
    if not keys or len(keys)>40:
        raise ValueError('Use 1–40 pointer keyframes per scene')
    result=[]
    for k in keys:
        if ('at' in k)==('time' in k):
            raise ValueError('Each pointer keyframe needs either at (fraction) or time (seconds)')
        t=float(k['time']) if 'time' in k else float(k['at'])*seconds
        if not math.isfinite(t) or not 0 <= t <= seconds or (result and t<=result[-1]['time']):
            raise ValueError('Pointer times must increase strictly inside scene duration')
        if space=='image':
            x,y=image_point(k['x'],k['y'],size,(style or {}).get('picture_height',670))
        else:
            x,y=float(k['x']),float(k['y'])
            if not math.isfinite(x) or not math.isfinite(y) or not 0<=x<=1920 or not 0<=y<=1080:
                raise ValueError('Pointer target is outside 1920×1080 frame')
        result.append({'time':t,'x':x,'y':y,'click':bool(k.get('click',False))})
    return result

def position_at(plan,t,axis):
    if t<=plan[0]['time']:
        return plan[0][axis]
    for a,b in zip(plan,plan[1:]):
        if t<=b['time']:
            u=(t-a['time'])/(b['time']-a['time']);s=u*u*(3-2*u)
            return a[axis]+(b[axis]-a[axis])*s
    return plan[-1][axis]

def expression(plan,axis):
    expr=f'{plan[-1][axis]:.4f}'
    for a,b in reversed(list(zip(plan,plan[1:]))):
        u=f'((t-{a["time"]:.6f})/{b["time"]-a["time"]:.6f})'
        value=f'{a[axis]:.4f}+({b[axis]-a[axis]:.4f})*(3*pow({u},2)-2*pow({u},3))'
        expr=f'if(lt(t,{b["time"]:.6f}),{value},{expr})'
    return f'if(lt(t,{plan[0]["time"]:.6f}),{plan[0][axis]:.4f},{expr})'

def cursor_assets(work,style):
    from PIL import Image, ImageDraw
    scale=style['pointer_scale'];aa=3
    w,h=round(64*scale),round(84*scale)
    im=Image.new('RGBA',(w*aa,h*aa))
    d=ImageDraw.Draw(im)
    points=[(0,0),(0,53),(14,40),(27,68),(38,63),(25,36),(48,36)]
    points=[(round((x*scale+4)*aa),round((y*scale+4)*aa)) for x,y in points]
    d.polygon([(x+aa,y+aa) for x,y in points],fill=(0,0,0,80))
    d.polygon(points,fill='white',outline='#17243a',width=round(2*scale*aa))
    im.resize((w,h),Image.Resampling.LANCZOS).save(work/'teaching-cursor.png')
    size=round(108*scale);ring=Image.new('RGBA',(size*aa,size*aa));d=ImageDraw.Draw(ring)
    d.ellipse((9*aa,9*aa,(size-9)*aa,(size-9)*aa),outline=style['highlight'],width=5*aa)
    ring.resize((size,size),Image.Resampling.LANCZOS).save(work/'click-ring.png')
    return work/'teaching-cursor.png',work/'click-ring.png',size

def video_filters(vf,plan,style,ring_size):
    """Inputs 0 video, 1 audio, 2 cursor PNG, 3 ring PNG if click events exist."""
    filters=[f'[0:v]{vf}[base]'];last='base'
    clicks=[k for k in plan if k['click']]
    if clicks:
        filters.append('[3:v]split='+str(len(clicks))+''.join(f'[r{i}]' for i in range(len(clicks))))
        for i,key in enumerate(clicks):
            end=key['time']+style['click_seconds']
            filters.append(f'[{last}][r{i}]overlay=x={key["x"]-ring_size/2:.4f}:y={key["y"]-ring_size/2:.4f}:enable=\'between(t,{key["time"]:.6f},{end:.6f})\':format=auto[c{i}]')
            last=f'c{i}'
    filters.append(f'[{last}][2:v]overlay=x=\'{expression(plan,"x")}-4\':y=\'{expression(plan,"y")}-4\':format=auto,format=yuv420p[marked]')
    return ';'.join(filters)
