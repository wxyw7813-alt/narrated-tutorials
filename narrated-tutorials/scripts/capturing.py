"""Narration-first real browser capture, with continuous-frame video and evidence."""
from pathlib import Path
import json
import math
import shutil
import urllib.parse
import captions
import visuals

ROOT=Path(__file__).resolve().parents[1]
ACTIONS={'click','fill','press','select','check','uncheck','hover','scroll','navigate','expect_text'}

def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def relative(base,value):
    p=Path(value).expanduser();return (p if p.is_absolute() else base/p).resolve()

def validate(data,allow_external=False):
    if data.get('schema_version')!=1 or not isinstance(data.get('steps'),list) or not data['steps']:
        raise ValueError('Browser plan needs schema_version=1 and nonempty steps')
    url=urllib.parse.urlsplit(data.get('url',''))
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:
        raise ValueError('Use an HTTP(S) browser URL without embedded credentials')
    if not allow_external and url.hostname not in ('localhost','127.0.0.1','::1'):
        raise ValueError('External website capture needs --allow-external for the requested URL')
    if not data.get('voice') and any(not s.get('audio') for s in data['steps']):
        raise ValueError('Choose a voice before generating a narrated browser capture')
    viewport=data.get('viewport',{'width':1280,'height':720})
    if not isinstance(viewport,dict) or any(not isinstance(viewport.get(k),int) or isinstance(viewport.get(k),bool) or not low<=viewport[k]<=high for k,low,high in (('width',640,1920),('height',360,1200))):
        raise ValueError('Use a viewport between 640×360 and 1920×1200')
    fps=data.get('capture_fps',10)
    if not isinstance(fps,int) or isinstance(fps,bool) or not 5<=fps<=20:raise ValueError('capture_fps must be 5–20')
    for step in data['steps']:
        if not step.get('title') or not step.get('narration'):raise ValueError('Each capture step needs title and narration')
        if not isinstance(step.get('actions',[]),list):raise ValueError('Step actions must be an array')
        for action in step.get('actions',[]):
            if action.get('type') not in ACTIONS:raise ValueError('Unsupported capture action: '+str(action.get('type')))
            if action.get('type') not in ('navigate','scroll','expect_text'):
                target=action.get('target',{})
                if not isinstance(target,dict) or sum(k in target for k in ('role','label','placeholder','test_id','text','css'))!=1:
                    raise ValueError('Capture action needs exactly one locator strategy')
                if target.get('role') and not target.get('name'):raise ValueError('Role locator also needs a visible name')
            if action.get('type')=='fill' and ('value' in action)==('value_env' in action):raise ValueError('Fill needs either value or value_env')
    return data

async def capture(a,resolve_voice,synthesize,command,tool,probe,digest):
    manifest=Path(a.manifest).resolve();base=manifest.parent
    data=validate(json.loads(manifest.read_text()),a.allow_external)
    out=Path(a.output).resolve()
    if (out/'project.json').exists() and not a.overwrite:raise ValueError('Capture project already exists; use a new output or --overwrite')
    node=shutil.which('node')
    if not node:raise ValueError('Node 20+ is required only for optional browser capture')
    # Fail before generating narration if capture dependencies are unavailable.
    command([node,ROOT/'scripts/capture.mjs','--doctor'])
    out.mkdir(parents=True,exist_ok=True);work=out/'work';work.mkdir(exist_ok=True)
    # A failed replacement must never leave an earlier successful project to render.
    for name in ('project.json','capture-provenance.json'):
        (out/name).unlink(missing_ok=True)
    narration=out/'narration';narration.mkdir(exist_ok=True)
    clips=out/'clips';clips.mkdir(exist_ok=True)
    settings=captions.config(data.get('subtitles'),data.get('language','zh-CN'))
    timing_settings={**settings,'mode':'single'} if settings['mode']=='off' else settings
    style=visuals.settings(data.get('style'),data.get('template'))
    voice=resolve_voice(data.get('voice',{}));prepared=[];audio_records=[];mapped=[]
    for i,step in enumerate(data['steps']):
        if step.get('audio'):
            source=relative(base,step['audio']);length=float(probe(source)['format']['duration'])
            cues=captions.supplied(step,timing_settings,length)
            origin=step.get('audio_origin','provided-unknown');timing='provided-audio-aligned-captions';record={'provider':'provided-audio','sha256':digest(source)}
        else:
            source,cues,timing,record=await captions.generate(step,timing_settings,voice,base,work,a.allow_online,synthesize,command,tool('ffmpeg'))
            origin='synthetic'
        audio=narration/f'{i+1:03}.wav'
        command([tool('ffmpeg'),'-v','error','-y','-i',source,'-ac','1','-ar','48000','-c:a','pcm_s16le',audio])
        length=float(probe(audio)['format']['duration'])
        minimum=float(step.get('hold_seconds',0))
        if not math.isfinite(minimum) or minimum<0:raise ValueError('hold_seconds must be finite and nonnegative')
        hold=max(length+style['tail_seconds'],minimum,.3)
        actions=[]
        for action in step.get('actions',[]):
            action=dict(action)
            if 'caption' in action:
                index=int(action.pop('caption'))-1;edge=action.pop('edge','start')
                if not 0<=index<len(cues) or edge not in ('start','end'):raise ValueError('Action caption reference is invalid')
                if 'at_seconds' in action:raise ValueError('Do not mix caption and at_seconds')
                action['at_seconds']=cues[index][edge]+float(action.pop('offset',0))
                if not 0<=action['at_seconds']<=hold:raise ValueError('Action caption time is outside its scene')
            actions.append(action)
        prepared.append({'title':step['title'],'hold_seconds':hold,'actions':actions})
        audio_records.append({'origin':origin,'timing':timing,'voice_provenance':record,'audio_sha256':digest(audio)})
        mapped.append({'title':step['title'],'narration':step['narration'],'captions':cues,'audio':audio.relative_to(out).as_posix(),'audio_origin':origin,'caption_timing_origin':timing})
    job={'url':data['url'],'viewport':data.get('viewport',{'width':1280,'height':720}),'fps':data.get('capture_fps',10),'output':str(out),'steps':prepared}
    private_job=work/'prepared-capture.json';dump(private_job,job)
    args=[node,ROOT/'scripts/capture.mjs','--job',private_job]
    if a.allow_external:args.append('--allow-external')
    if a.headed:args.append('--headed')
    command(args)
    log=json.loads((out/'capture-log.json').read_text())
    if log.get('status')!='passed' or len(log['steps'])!=len(mapped):raise RuntimeError('Browser capture did not finish all steps')
    for i,(scene,captured) in enumerate(zip(mapped,log['steps'])):
        entries=captured['frames']
        if len(entries)<2 or captured.get('status')!='passed':raise RuntimeError('Capture step has insufficient recorded evidence')
        seconds=math.ceil(float(captured['duration_seconds'])*style['fps'])/style['fps']
        concat=[]
        for j,frame in enumerate(entries):
            source=(out/frame['file']).resolve()
            if not source.is_relative_to(out) or not source.is_file():raise ValueError('Capture frame path is outside its output')
            t=float(frame['at_ms'])/1000
            end=float(entries[j+1]['at_ms'])/1000 if j+1<len(entries) else seconds
            if end<=t:raise RuntimeError('Capture frame timestamps must increase')
            # All frame paths are recorder-generated, never shell-interpolated user paths.
            concat.extend(["file '"+source.name+"'",'duration '+f'{end-t:.8f}'])
        concat.append("file '"+Path(entries[-1]['file']).name+"'")
        frame_dir=(out/entries[0]['file']).parent;listing=frame_dir/'frames.ffconcat';listing.write_text('\n'.join(concat)+'\n')
        clip=clips/f'{i+1:03}.mp4'
        command([tool('ffmpeg'),'-v','error','-y','-f','concat','-safe','1','-i',listing,'-vf',f'fps={style["fps"]},format=yuv420p','-t',str(seconds),'-an','-c:v','libx264','-preset','veryfast','-crf','20',clip])
        actual=float(probe(clip)['format']['duration'])
        if abs(actual-seconds)>1/style['fps']+.001:raise RuntimeError('Recorded clip duration does not match the capture clock')
        scene.update(video=clip.relative_to(out).as_posix(),min_seconds=actual,capture_warnings=captured.get('warnings',[]))
        if data['steps'][i].get('protect_targets',True):
            width,height=log['viewport']['width'],log['viewport']['height'];scale=min(1920/width,1080/height);left=(1920-width*scale)/2;top=(1080-height*scale)/2
            scene['protected_regions']=[{'label':str(t['label']),'space':'frame','x':left+t['x']*scale,'y':top+t['y']*scale,'width':t['width']*scale,'height':t['height']*scale} for t in captured['targets']]
        audio_records[i].update(capture_clip_sha256=digest(clip),screenshot_sha256=digest(out/captured['screenshot']),recorded_seconds=actual)
    project={'schema_version':1,'title':data.get('title','真实网页操作教程'),'language':data.get('language','zh-CN'),'template':data.get('template','software-guide'),'voice':data.get('voice',{}),'style':data.get('style',{}),'subtitles':data.get('subtitles',{'mode':'single'}),'source_note':'Playwright 在独立浏览器中实际操作并连续采集网页画面；指针与点击光圈为教学覆盖层。不是桌面软件录屏。','scenes':mapped}
    dump(out/'project.json',project);dump(out/'capture-provenance.json',{'schema_version':1,'recording_status':'passed','method':log['capture_method'],'requested_fps':log['requested_fps'],'source_url':log['source_url'],'voice_records':audio_records,'source_note':project['source_note']})
    print(json.dumps({'project':str(out/'project.json'),'capture_log':str(out/'capture-log.json'),'screenshots':[str(out/s['screenshot']) for s in log['steps']],'note':'Capture succeeded. Generate a scene preview or render this project; inspect action timing warnings and the final review page.'},ensure_ascii=False,indent=2))
