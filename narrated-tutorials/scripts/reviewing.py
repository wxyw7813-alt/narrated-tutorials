"""Readable storyboard previews and evidence-based checks for rendered videos.

Automatic timing/geometry checks are kept separate from human sound/meaning review.
No code or styling is copied from reference projects.
"""
from pathlib import Path
import html
import json
import math
import re

CSS='''body{font:16px/1.7 system-ui,-apple-system,sans-serif;background:#f4f7fc;color:#17243a;max-width:1160px;margin:32px auto;padding:0 24px}h1{line-height:1.3}section,article{background:white;border-radius:14px;padding:20px 24px;margin:20px 0}img,video{max-width:100%;border-radius:8px}video{width:100%}a{color:#315de8}.frames{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.frames img{width:100%}.ok{color:#18734b}.warning{color:#9c5d00}.error{color:#b52332}.muted{color:#52647b}code{background:#eef2fa;padding:2px 5px}textarea{width:100%;box-sizing:border-box;min-height:90px}button,select{font:inherit;padding:8px 14px;margin:4px;border-radius:8px;border:1px solid #bfcbe0;background:white;cursor:pointer}.caption{padding:8px 12px;border-left:3px solid #bfcee9;margin:10px 0}.time{font-size:14px;color:#52647b}label{display:block;margin:8px 0}@media(max-width:700px){.frames{grid-template-columns:1fr}}'''

def escape(value):return html.escape(str(value))
def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def page(title,body):return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>'+CSS+'</style>'+body+'</html>'

def contact_sheet(items,out,fontfile):
    from PIL import Image,ImageDraw,ImageFont,ImageOps
    columns=3;cell_w=360;cell_h=250
    im=Image.new('RGB',(columns*cell_w,max(1,math.ceil(len(items)/columns))*cell_h),'#eef2fa')
    draw=ImageDraw.Draw(im);font=ImageFont.truetype(str(fontfile),19)
    for i,(path,label) in enumerate(items):
        x=i%columns*cell_w;y=i//columns*cell_h
        with Image.open(path) as src:thumb=ImageOps.contain(src.convert('RGB'),(344,194))
        im.paste(thumb,(x+(cell_w-thumb.width)//2,y+8))
        # Keep titles legible; the full title is present in the HTML report.
        label=str(label)
        while font.getlength(label)>338:label=label[:-2]+'…'
        draw.text((x+10,y+210),label,font=font,fill='#17243a')
    im.save(out)

def storyboard(data,base,out,fontfile,make_card,command,ffmpeg):
    import visuals,captions
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    frames=out/'frames';frames.mkdir(exist_ok=True)
    style=visuals.settings(data.get('style'),data.get('template'))
    subtitles=captions.config(data.get('subtitles'),data.get('language','zh-CN'))
    if subtitles['mode']!='off' and subtitles['burn_in']:style.update(picture_height=600,caption_space=True)
    cards=[];tiles=[]
    for i,scene in enumerate(data['scenes'],1):
        image=frames/f'{i:03}.png'
        if scene.get('video'):
            source=Path(scene['video']);source=source if source.is_absolute() else base/source
            command([ffmpeg,'-v','error','-y','-ss',str(scene.get('video_start',0)),'-i',source,'-frames:v','1',image])
        else:make_card(scene,image,base,fontfile,style)
        tiles.append((image,f'{i}. {scene["title"]}'))
        paired=''.join('<div class="caption">'+escape(c['text'])+('<br>'+escape(c['translation']) if c.get('translation') else '')+'</div>' for c in scene.get('captions',[]))
        cards.append('<article><h2>'+escape(i)+'. '+escape(scene['title'])+'</h2><img src="frames/'+image.name+'"><p><strong>旁白：</strong>'+escape(scene['narration'])+'</p>'+paired+'</article>')
    contact_sheet(tiles,out/'contact-sheet.png',fontfile)
    label=next((x['label'] for x in visuals.templates() if x['id']==data.get('template','software-guide')),'自定义')
    body='<h1>'+escape(data.get('title','分镜预览'))+'</h1><p>静态分镜预览 · 模板：'+escape(label)+'。未生成新配音；画面中的字幕和动态指针将在样片中检查。</p><p>改项目 JSON 的 template/style/scenes 后重新运行 storyboard；用 preview 只生成选定分镜的有声样片。</p><img src="contact-sheet.png">'+''.join(cards)
    (out/'index.html').write_text(page('分镜预览',body),encoding='utf-8')
    dump(out/'storyboard.json',{'schema_version':1,'template':data.get('template','software-guide'),'scene_count':len(cards),'render_mode':'static-storyboard','generated_narration':False})
    return {'storyboard':str(out/'index.html'),'contact_sheet':str(out/'contact-sheet.png')}

def build(out,probe,command,ffmpeg,digest,fontfile):
    """Check actual exported media; create keyframes, contact sheet and review HTML."""
    out=Path(out).resolve();meta=json.loads((out/'provenance.json').read_text());video=out/'video.mp4'
    checks=[]
    def check(code,ok,detail,severity='error'):
        checks.append({'code':code,'status':'pass' if ok else severity,'detail':detail})
    info=probe(video);streams=info['streams'];duration=float(info['format']['duration']);fps=int(meta['style']['fps'])
    check('video_hash',digest(video)==meta['video_sha256'],'视频与制作记录的散列一致。')
    visual=next((s for s in streams if s['codec_type']=='video'),{})
    check('dimensions',visual.get('width')==1920 and visual.get('height')==1080,'输出画面应为 1920×1080。')
    check('audio_track',any(s['codec_type']=='audio' for s in streams),'存在旁白音轨。')
    check('duration',abs(duration-float(meta['planned_seconds']))<=max(.06,1/fps+.02),'成片时长与制作时间轴一致。')
    try:
        command([ffmpeg,'-v','error','-i',video,'-f','null','-']);check('decode',True,'成片已完整解码。')
    except RuntimeError:check('decode',False,'成片解码失败，先修复媒体再交付。')
    mode=meta['subtitles']['mode'];timeline=[]
    if mode!='off':
        p=out/'caption-timeline.json'
        if p.is_file():timeline=json.loads(p.read_text())
        valid=bool(timeline);previous=0
        for cue in timeline:
            try:
                a=float(cue['start']);b=float(cue['end'])
                valid=valid and math.isfinite(a) and math.isfinite(b) and 0<=a<b<=duration+.001 and a>=previous-.001 and bool(str(cue['text']).strip())
                previous=b
            except (KeyError,TypeError,ValueError):valid=False
        check('caption_range',valid,'字幕必须非空、顺序正确，并在成片时间范围内。')
        kinds=('source','target','bilingual') if mode=='bilingual' else ('source',)
        check('caption_files',all((out/f'subtitles.{k}.{ext}').is_file() for k in kinds for ext in ('srt','vtt')),'按当前模式检查字幕导出文件。')
        if mode=='bilingual':check('translations',all(str(c.get('translation','')).strip() for c in timeline),'每句双语字幕有配对译文。')
        counts=[sum(s['start']-.001<=c['start']<s['start']+s['duration']-.001 for c in timeline) for s in meta['scenes']]
        check('caption_coverage',all(n>0 for n in counts),'每个分镜至少有一句字幕。')
    check('scene_cuts',all(abs(s['duration']-s.get('container_duration',s['duration']))<=.001 for s in meta['scenes']),'逐段容器时长与时间轴一致。')
    onsets=[]
    measured=[c for c in timeline if any(s.get('subtitle_timing')=='measured-sentence-audio' and s['start']-.001<=c['start']<s['start']+s['duration']-.001 for s in meta['scenes'])]
    if measured:
        import captions
        work=out/'work';work.mkdir(exist_ok=True);wav=work/'review-final-audio.wav'
        command([ffmpeg,'-v','error','-y','-i',video,'-vn','-ac','1','-ar','48000','-c:a','pcm_s16le',wav])
        samples=captions.pcm(wav)
        for i,cue in enumerate(measured,1):
            a=max(0,round((cue['start']-.08)*48000));b=min(len(samples),round((cue['start']+.25)*48000))
            try:
                start,_=captions.speech_span(samples[a:b]);delta=(a+start)/48000-cue['start']
                onsets.append({'caption_start':cue['start'],'onset_error_seconds':delta})
                check(f'audio_onset_{i}',abs(delta)<=.05,f'实际音轨与第 {i} 个已测时语句的起点差：{delta*1000:+.0f} ms。')
            except ValueError:check(f'audio_onset_{i}',False,'此句起点无法从音频能量可靠核对，请人工试听。','warning')
    for i,scene in enumerate(meta['scenes'],1):
        pointer=scene.get('pointer_keyframes',[])
        valid=all(0<=k['x']<=1920 and 0<=k['y']<=1080 and 0<=k['time']<=scene['duration'] for k in pointer)
        check(f'pointer_{i}',valid,f'第 {i} 步指针坐标与时间范围。')
        if meta['subtitles']['burn_in'] and mode!='off':
            for region in scene.get('protected_regions',[]):
                overlap=region['y']+region['height']>898 and region['y']<1080
                check(f'protected_caption_{i}_{region["label"]}',not overlap,f'第 {i} 步重要区域「{region["label"]}」是否与画面字幕区重叠。','warning')
        for n,marker in enumerate(scene.get('marker_regions',[]),1):
            for region in scene.get('protected_regions',[]):
                overlap=marker['x']<region['x']+region['width'] and marker['x']+marker['width']>region['x'] and marker['y']<region['y']+region['height'] and marker['y']+marker['height']>region['y']
                check(f'marker_{i}_{n}_{region["label"]}',not overlap,f'第 {i} 步编号与重要区域「{region["label"]}」的遮挡检查。','warning')
        for note in scene.get('capture_warnings',[]):check(f'capture_{i}',False,str(note),'warning')
    # Export actual beginning/middle/end evidence, not just the unrendered source cards.
    requests=[];scene_requests=[]
    last_frame=max(0,math.floor(duration*fps)-1)
    for scene in meta['scenes']:
        local=[c for c in timeline if scene['start']-.001<=c['start']<scene['start']+scene['duration']-.001]
        start=scene['start'];end=start+scene['duration']
        times=[start+.01,(local[0]['start']+local[0]['end'])/2 if local else start+.1,(start+end)/2,(local[-1]['start']+local[-1]['end'])/2 if local else max(start,end-.15),max(start,end-1/fps)]
        indices=sorted(set(min(last_frame,max(0,int(t*fps))) for t in times))
        scene_requests.append(indices);requests.extend(indices)
    indices=sorted(set(requests));frames=out/'review-frames';frames.mkdir(exist_ok=True)
    # Do not leave old generated evidence after overwriting a shorter video.
    for p in frames.glob('frame-*.jpg'):p.unlink()
    select='+'.join(f'eq(n,{n})' for n in indices)
    command([ffmpeg,'-v','error','-y','-i',video,'-vf','select='+select.replace(',','\\,'),'-fps_mode','vfr','-q:v','3',frames/'frame-%04d.jpg'])
    images=sorted(frames.glob('frame-*.jpg'))
    if len(images)!=len(indices):raise RuntimeError('Review frame extraction did not match the requested timeline')
    image_map=dict(zip(indices,images));tiles=[];cards=[]
    for i,(scene,selected) in enumerate(zip(meta['scenes'],scene_requests),1):
        representative=image_map[selected[len(selected)//2]];tiles.append((representative,f'{i}. {scene["title"]}'))
        strip=''.join('<a href="#player" onclick="document.querySelector(\'video\').currentTime='+str(n/fps)+'"><img src="review-frames/'+image_map[n].name+'" alt="第 '+str(i)+' 步，'+f'{n/fps:.2f}'+' 秒"></a>' for n in selected)
        cues=[c for c in timeline if scene['start']-.001<=c['start']<scene['start']+scene['duration']-.001]
        lines=''.join('<div class="caption"><span class="time">'+f'{c["start"]:.2f}–{c["end"]:.2f} s</span><br>'+escape(c['text'])+('<br>'+escape(c.get('translation','')) if mode=='bilingual' else '')+'</div>' for c in cues)
        cards.append('<article><h2>'+str(i)+'. '+escape(scene['title'])+'</h2><p class="time">'+f'{scene["start"]:.2f}–{scene["start"]+scene["duration"]:.2f} s'+'</p><div class="frames">'+strip+'</div><p><strong>旁白：</strong>'+escape(scene.get('narration','见字幕原文'))+'</p>'+lines+'</article>')
    contact_sheet(tiles,out/'contact-sheet.png',fontfile)
    manual=[{'id':'terms','label':'旁白没有漏字，软件名、命令和术语读音正确。'},{'id':'readability','label':'字幕、截图与按钮文字清晰，没有重要内容被遮挡。'},{'id':'pointer_meaning','label':'指针指向旁白提到的真实操作位置。'},{'id':'actions','label':'真实录制的步骤和结果正确；示意画面已明确标注。'},{'id':'listening','label':'声音自然、语调和节奏符合这次需求。'}]
    state='error' if any(c['status']=='error' for c in checks) else 'needs_attention' if any(c['status']=='warning' for c in checks) else 'automatic_checks_passed'
    report={'schema_version':1,'video_sha256':meta['video_sha256'],'render_mode':meta.get('render_mode','full'),'automatic_status':state,'automatic_checks':checks,'audio_onsets':onsets,'manual_status':'pending','manual_checks':manual,'scene_count':len(meta['scenes']),'limitations':['时间范围、媒体与几何检查不等于语音识别或语义理解。','没有标记 protected_regions 时，按钮遮挡仍需人工检查。','未完成的人声音色、术语读音和指针语义检查不能自动判为通过。']}
    dump(out/'review.json',report)
    results=''.join('<li class="'+('ok' if c['status']=='pass' else c['status'])+'">'+('通过' if c['status']=='pass' else '需检查')+' · '+escape(c['detail'])+'</li>' for c in checks)
    form=''.join('<label><input type="checkbox" data-check="'+x['id']+'"> '+escape(x['label'])+'</label>' for x in manual)
    script='''<script>document.querySelector('#save-feedback').onclick=()=>{const checks=Array.from(document.querySelectorAll('[data-check]')).map(x=>({id:x.dataset.check,confirmed:x.checked}));const body={schema_version:1,video_sha256:document.body.dataset.hash,manual_checks:checks,notes:document.querySelector('textarea').value};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'}));a.download='review-feedback.json';a.click();URL.revokeObjectURL(a.href)};</script>'''
    body='<body data-hash="'+escape(meta['video_sha256'])+'"><h1>视频验收与关键帧总览</h1><p>自动检查：'+escape(state)+'；<strong>人工检查：待确认</strong>。自动通过不表示声音、术语或操作含义已经验收。</p><video id="player" controls src="video.mp4"></video><section><h2>自动检查结果</h2><ul>'+results+'</ul></section><section><h2>人工试听与画面检查</h2>'+form+'<textarea placeholder="记录需要修改的分镜、时间点和原因"></textarea><button id="save-feedback">下载检查反馈</button><p class="muted">勾选和备注保留在当前页面；下载文件后才能作为检查记录保存，不会自动发给助手。</p></section><section><h2>全片关键帧</h2><img src="contact-sheet.png"></section>'+''.join(cards)+script+'</body>'
    (out/'review.html').write_text(page('视频验收',body),encoding='utf-8')
    return {'review':str(out/'review.html'),'automatic_status':state,'manual_status':'pending','contact_sheet':str(out/'contact-sheet.png')}
