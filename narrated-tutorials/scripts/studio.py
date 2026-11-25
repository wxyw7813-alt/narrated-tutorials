#!/usr/bin/env python3
"""Portable narrated tutorial builder. Python 3.11+, FFmpeg, Pillow, edge-tts.

Online preset speech is explicit; cloning uses a separately installed loopback
VoiceStudio service. No credentials, model weights or reference clips are bundled.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import html
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
import visuals
import captions

ROOT = Path(__file__).resolve().parents[1]
PRESETS = json.loads((ROOT / 'assets/voices.json').read_text())['presets']

def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def command(args):
    p = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed: {p.stderr[-2000:]}')
    return p.stdout

def tool(name):
    found = shutil.which(name)
    if not found:
        raise ValueError(f'{name} is missing. Install FFmpeg before rendering.')
    return found

def probe(path):
    return json.loads(command([tool('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]))

def duration(path):
    value = float(probe(path)['format']['duration'])
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Invalid media duration')
    return value

def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def model_digest(path):
    path = Path(path)
    if path.is_file():
        return digest(path)
    if not path.is_dir():
        raise ValueError('Local model path does not exist')
    files = sorted(p for p in path.rglob('*') if p.is_file() and '.cache' not in p.parts
                   and '.range-parts' not in p.parts and p.suffix in ('.json','.txt','.safetensors'))
    h = hashlib.sha256()
    for file in files:
        h.update(str(file.relative_to(path)).encode())
        h.update(digest(file).encode())
    return h.hexdigest()

def relative(base, path):
    p = Path(path).expanduser()
    return (p if p.is_absolute() else base / p).resolve()

def preset(name):
    for item in PRESETS:
        if item['id'] == name:
            return dict(item)
    raise ValueError('Unknown preset: ' + name)

def font_path(explicit=None):
    candidates = [explicit, os.environ.get('NARRATED_VIDEO_FONT'),
                  '/System/Library/Fonts/PingFang.ttc',
                  '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                  'C:/Windows/Fonts/msyh.ttc']
    for item in candidates:
        if item and Path(item).is_file():
            return str(item)
    raise ValueError('Set --font to a CJK-capable .ttf/.ttc font file.')

def wrap(text, font, width):
    result = []
    for para in text.split('\n'):
        line = ''
        for char in para:
            if font.getlength(line + char) > width and line:
                result.append(line.rstrip()); line = char.lstrip()
            else:
                line += char
        result.append(line)
    return result

def make_card(scene, path, base, fontfile, style=None):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    style=visuals.settings(style)
    im = Image.new('RGB', (1920, 1080), style['background'])
    d = ImageDraw.Draw(im)
    f = lambda n: ImageFont.truetype(fontfile, n)
    d.rectangle((0, 0, 1920, 14), fill=style['accent'])
    d.text((80, 42), scene.get('kind', '步骤讲解 / Step guide'), font=f(25), fill='#53657b')
    title = wrap(scene['title'], f(52), 1750)
    if len(title) > 2:
        raise ValueError('Scene title too long: ' + scene['title'])
    for i, line in enumerate(title):
        d.text((80, 90 + i * 65), line, font=f(52), fill=style['text'])
    top = 248
    if scene.get('image'):
        src = Image.open(relative(base, scene['image'])).convert('RGB')
        orig_w, orig_h = src.size
        height=style.get('picture_height',670)
        pic = ImageOps.contain(src, (1720, height))
        x,y,_,_=visuals.image_placement(src.size,height)
        im.paste(pic, (x, y))
        for box in scene.get('highlights',[]):
            a,b=visuals.image_point(box['x'],box['y'],src.size,height)
            c,e=visuals.image_point(float(box['x'])+float(box['width']),float(box['y'])+float(box['height']),src.size,height)
            if c<=a or e<=b:
                raise ValueError('Highlight width/height must be positive')
            d.rounded_rectangle((a,b,c,e),radius=8,outline=style['highlight'],width=5)
        for c in scene.get('callouts', []):
            cx, cy = float(c['x']), float(c['y'])
            if not 0 <= cx <= orig_w or not 0 <= cy <= orig_h:
                raise ValueError('Callout is outside source image')
            px, py = x + cx * pic.width / orig_w, y + cy * pic.height / orig_h
            r = 27
            d.ellipse((px-r, py-r, px+r, py+r), fill='#e5493b', outline='white', width=3)
            d.text((px, py), str(c['number']), anchor='mm', font=f(28), fill='white')
    else:
        y = top + 20
        for i, point in enumerate(scene.get('points', []), 1):
            lines = wrap(point, f(39), 1550)
            if y + 58 * len(lines) > (825 if style.get('caption_space') else 934):
                raise ValueError('Too much scene text; split into more scenes')
            d.rounded_rectangle((80, y, 140, y + 58), radius=13, fill='#e2eafe')
            d.text((110, y + 29), str(i), anchor='mm', font=f(31), fill='#244fca')
            for j, line in enumerate(lines):
                d.text((175, y + j * 58), line, font=f(39), fill=style['text'])
            y += len(lines) * 58 + 30
    footer = scene.get('footer', 'AI 合成旁白 · Synthetic narration')
    for i, line in enumerate(wrap(footer, f(24), 1750)[:2]):
        d.text((80, (850 if style.get('caption_space') else 975)+i*32), line, font=f(24), fill='#53657b')
    im.save(path)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('VoiceStudio redirect refused; keep audio on loopback.')

def local_url(url):
    parsed = urllib.parse.urlsplit(url)
    try:
        local = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
    except (ValueError, TypeError):
        local = False
    if parsed.scheme not in ('http', 'https') or not local or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('VoiceStudio URL must be a loopback origin, e.g. http://127.0.0.1:3900')
    return url.rstrip('/')

def local_request(url, endpoint, data=None, headers=None):
    url = local_url(url)
    heads = dict(headers or {})
    key = os.environ.get('OMNIVOICE_API_KEY')
    if key:
        heads['Authorization'] = 'Bearer ' + key
    req = urllib.request.Request(url + endpoint, data=data, headers=heads)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=900 if data else 10) as response:
            return response.read(), response.headers
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'VoiceStudio HTTP {exc.code}. Check its UI/model setup; no automatic retry was sent.') from None
    except urllib.error.URLError:
        raise RuntimeError('Cannot reach local VoiceStudio. Open the app and finish model setup first.') from None

def multipart(fields, sample):
    boundary = 'narrated-' + uuid.uuid4().hex
    body = bytearray()
    for key, value in fields.items():
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    # Send a fixed safe basename; the local source path stays private.
    body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="ref_audio"; filename="reference.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    body.extend(Path(sample).read_bytes())
    body.extend(f'\r\n--{boundary}--\r\n'.encode())
    return bytes(body), {'Content-Type': 'multipart/form-data; boundary=' + boundary}

def clone_reference(voice, base, work):
    if not str(voice.get('authorization', '')).strip():
        raise ValueError('Clone mode needs authorization: record that the sample is your own or permission was obtained.')
    ref = relative(base, voice['reference_audio'])
    if not 3 <= duration(ref) <= 20:
        raise ValueError('Use a clean 3–20 second reference clip; 5–15 seconds is a useful starting point.')
    if not str(voice.get('reference_text', '')).strip():
        raise ValueError('Provide the exact words spoken in reference_text.')
    if not voice.get('engine'):
        raise ValueError('Choose an installed cloning engine from vs-check; it is not auto-downloaded.')
    out = work / 'reference-normalized.wav'
    command([tool('ffmpeg'), '-v', 'error', '-y', '-i', ref, '-ac', '1', '-ar', '24000', out])
    return out

async def synthesize(text, voice, base, work, allow_online=False):
    """Returns audio path, timing cues, timing source, non-secret provenance."""
    engine = voice.get('provider', voice.get('engine', 'edge'))
    if engine == 'qwen-design':
        machine_file = ROOT/'local-engines.json'
        machine = json.loads(machine_file.read_text()).get('qwen-design',{}) if machine_file.is_file() else {}
        voice = {**machine,**voice}
        if not voice.get('model') or not voice.get('python'):
            raise ValueError('Qwen voice design needs local model/python paths; see references/qwen-design.md.')
    if engine == 'edge' and not allow_online:
        raise ValueError('Online speech sends narration text to Microsoft. Use --allow-online only when that is authorized.')
    ref = None
    if engine == 'voicestudio':
        local_url(voice.get('url', 'http://127.0.0.1:3900'))
        ref = clone_reference(voice, base, work)
    fingerprint = {'text': text, 'voice': {k:v for k,v in voice.items() if k not in ('authorization','reference_audio','python','model','voices')}, 'revision': 1}
    if ref:
        fingerprint['reference_sha256'] = digest(ref)
    for key in ('model', 'voices'):
        if voice.get(key):
            fingerprint[key + '_sha256'] = model_digest(relative(base, voice[key]))
    key = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    audio = work / (key + ('.mp3' if engine == 'edge' else '.wav'))
    meta = work / (key + '.json')
    try:
        if audio.exists() and meta.exists():
            data = json.loads(meta.read_text())
            if data.get('audio_sha256') == digest(audio):
                duration(audio)
                return audio, data['cues'], data['timing'], data['provenance']
        cues = []
        timing = 'scene-estimated'
        if engine == 'edge':
            import edge_tts
            speech = edge_tts.Communicate(text, voice=voice['voice'], rate=voice.get('rate', '+0%'),
                                          pitch=voice.get('pitch', '+0Hz'), boundary='SentenceBoundary')
            with audio.open('wb') as f:
                async for part in speech.stream():
                    if part['type'] == 'audio':
                        f.write(part['data'])
                    elif part['type'] == 'SentenceBoundary':
                        cues.append({'text':part['text'], 'start':part['offset']/1e7, 'end':(part['offset']+part['duration'])/1e7})
            timing = 'engine-sentence-boundary' if cues else timing
        elif engine == 'voicestudio':
            fields = {'text':text, 'language':voice.get('language','Auto'), 'ref_text':voice['reference_text'],
                      'engine':voice['engine'], 'speed':voice.get('speed',1), 'stream':'false'}
            body, heads = multipart(fields, ref)
            data, response = local_request(voice.get('url','http://127.0.0.1:3900'), '/generate', body, heads)
            if int(response.get('X-OmniVoice-Dropped-Chunks','0')):
                raise RuntimeError('VoiceStudio reports missing narration text; take rejected.')
            if 'audio/' not in response.get('Content-Type','') or not data.startswith(b'RIFF'):
                raise RuntimeError('Expected WAV from VoiceStudio /generate; check installed API version.')
            audio.write_bytes(data)
        elif engine == 'kokoro':
            textfile = work / (key + '.txt'); textfile.write_text(text, encoding='utf-8')
            # Keep a venv's launcher path: resolving its symlink loses site-packages.
            executable = Path(voice['python']).expanduser() if voice.get('python') else Path(sys.executable)
            python = str(executable if executable.is_absolute() else base / executable)
            command([python, ROOT/'scripts/kokoro_speech.py', '--model', relative(base, voice['model']),
                     '--voices', relative(base, voice['voices']), '--text-file', textfile, '--output', audio,
                     '--voice', voice.get('voice','af_heart'), '--speed', str(voice.get('speed',.98))])
        elif engine == 'qwen-design':
            executable = Path(voice['python']).expanduser()
            python = str(executable if executable.is_absolute() else base/executable)
            job = work/(key+'.job.json')
            dump(job,[{'id':voice.get('id'),'model':str(relative(base,voice['model'])),'text':text,
                       'instruct':voice['instruct'],'seed':voice.get('seed',42),
                       'temperature':voice.get('temperature',.7),'output':str(audio)}])
            try:
                command([python,ROOT/'scripts/qwen_design.py','--jobs',job])
            finally:
                job.unlink(missing_ok=True)
        else:
            raise ValueError('Unknown synthesis provider: ' + str(engine))
        length = duration(audio)
        if not cues:
            cues = [{'text':text, 'start':0, 'end':length}]
        public = {k:v for k,v in fingerprint.items() if k != 'text'}
        dump(meta, {'audio_sha256':digest(audio), 'cues':cues, 'timing':timing, 'provenance':public})
        return audio, cues, timing, public
    finally:
        if ref:
            ref.unlink(missing_ok=True)

def resolve_voice(config):
    voice = dict(config)
    if voice.get('preset'):
        voice = {**preset(voice['preset']), **voice}
    return voice

def load_manifest(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('scenes'), list) or not data['scenes']:
        raise ValueError('Manifest needs schema_version=1 and a nonempty scenes array.')
    for s in data['scenes']:
        if not s.get('title') or not s.get('narration'):
            raise ValueError('Every scene needs title and narration.')
        if s.get('video') and (s.get('image') or s.get('callouts')):
            raise ValueError('Video scenes do not support screenshot callouts; annotate source footage first.')
        for key in ('image', 'video', 'audio'):
            if s.get(key) and not relative(path.parent, s[key]).is_file():
                raise ValueError('Missing scene asset: ' + key)
        if s.get('audio_origin') not in (None, 'synthetic', 'human-recording', 'provided-unknown'):
            raise ValueError('audio_origin must be synthetic, human-recording or provided-unknown')
    return data, path.parent

async def render(a):
    data, base = load_manifest(a.manifest)
    voice = resolve_voice(data.get('voice',{}))
    out = Path(a.output).resolve()
    if (out/'video.mp4').exists() and not a.overwrite:
        raise ValueError('video.mp4 already exists; use a different output directory or --overwrite.')
    out.mkdir(parents=True, exist_ok=True)
    work = out/'work'; work.mkdir(exist_ok=True)
    font = font_path(a.font)
    style=visuals.settings(data.get('style'))
    subtitle_settings=captions.config(data.get('subtitles'),data.get('language','zh-CN'))
    if subtitle_settings['mode']!='off' and subtitle_settings['burn_in']:
        style.update(picture_height=600,caption_space=True)
    scenes, subs, clock = [], [], 0.0
    fps = style['fps']
    for i, scene in enumerate(data['scenes']):
        print(f'Scene {i+1}/{len(data["scenes"])}: {scene["title"]}', flush=True)
        linked_pointer=any('caption' in k for k in scene.get('pointer',{}).get('keyframes',[]))
        needs_timing=subtitle_settings['mode']!='off' or linked_pointer
        timing_settings={**subtitle_settings,'mode':'single'} if subtitle_settings['mode']=='off' else subtitle_settings
        if scene.get('audio'):
            audio = relative(base, scene['audio']); length = duration(audio)
            cues=captions.supplied(scene,timing_settings,length) if needs_timing else []
            timing, provenance = 'provided-audio-aligned-captions', {'provider':'provided-audio','sha256':digest(audio)}
            origin = scene.get('audio_origin', 'provided-unknown')
        else:
            if not needs_timing:
                audio, _, timing, provenance = await synthesize(scene['narration'],voice,base,work,a.allow_online);cues=[]
            else:
                audio,cues,timing,provenance=await captions.generate(scene,timing_settings,voice,base,work,a.allow_online,synthesize,command,tool('ffmpeg'))
            length = duration(audio)
            origin = 'synthetic'
        seconds = math.ceil((length + style['tail_seconds'])*fps)/fps
        # PCM intermediate audio has no AAC encoder padding per scene.
        # Encode AAC once after concatenation, so timestamps do not drift at cuts.
        clip = work/f'{i:03}.mov'
        if scene.get('video'):
            source = relative(base, scene['video'])
            offset = float(scene.get('video_start',0))
            if offset < 0 or offset >= duration(source):
                raise ValueError('video_start must lie inside source video')
            inputs = ['-ss',str(offset),'-i',str(source)]
            vf = f'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={seconds},format=yuv420p'
        else:
            card = work/f'{i:03}.png'
            display = dict(scene)
            if origin != 'synthetic':
                display.setdefault('footer', '外部提供旁白 · Provided narration')
            make_card(display,card,base,font,style)
            inputs = ['-loop','1','-framerate',str(fps),'-i',str(card)]
            vf = 'setsar=1,format=yuv420p'
        pointer_scene=captions.pointer_scene(scene,cues)
        plan=visuals.pointer_plan(pointer_scene,seconds,base,style) if style['pointer_enabled'] else []
        overlays=[]
        if plan:
            cursor,ring,ring_size=visuals.cursor_assets(work,style)
            overlays=['-loop','1','-framerate',str(fps),'-i',cursor]
            if any(k['click'] for k in plan):
                overlays+=['-loop','1','-framerate',str(fps),'-i',ring]
            graph=visuals.video_filters(vf,plan,style,ring_size)
            last='marked';next_input=4 if any(k['click'] for k in plan) else 3
        else:
            graph=f'[0:v]{vf}[base]';last='base';next_input=2
        if subtitle_settings['mode']!='off' and subtitle_settings['burn_in']:
            paths=captions.overlay_assets(cues,subtitle_settings,work,font)
            for path in paths:overlays+=['-loop','1','-framerate',str(fps),'-i',path]
            graph+=';'+captions.filter_chain(last,cues,next_input,fps);last='captioned'
        video_args=['-filter_complex',graph,'-map',f'[{last}]']
        command([tool('ffmpeg'),'-v','error','-y',*inputs,'-i',audio,*overlays,*video_args,'-map','1:a:0',
                 '-af','loudnorm=I=-18:TP=-2:LRA=10,apad','-t',str(seconds),
                 '-c:v','libx264','-preset','veryfast','-crf','22','-c:a','pcm_s16le','-ar','48000','-ac','1',clip])
        segment_duration=duration(clip)
        if abs(segment_duration-seconds)>.001:
            raise RuntimeError('Scene container duration differs from timeline; refusing subtitle drift.')
        subs.extend({**cue,'start':clock+cue['start'],'end':clock+cue['end']} for cue in cues)
        scenes.append({'title':scene['title'],'start':clock,'duration':seconds,'audio_duration':length,
                       'subtitle_timing':timing,'narration_origin':origin,'voice_provenance':provenance,'clip':clip.name,
                       'pointer_overlay':bool(plan),'pointer_keyframes':plan,'container_duration':segment_duration,'pointer_note':'Teaching overlay; not real mouse interaction' if plan else None})
        clock += seconds
    if subtitle_settings['mode']!='off':
        captions.exports(out,subs,subtitle_settings['mode']=='bilingual')
    # Copy to deterministic generated filenames before concat: no shell or path interpolation.
    concat = work/'concat.txt'; concat.write_text(''.join(f"file '{i:03}.mov'\n" for i in range(len(scenes))))
    lang = 'zho' if data.get('language','zh').startswith('zh') else 'eng'
    disclosure = 'AI synthetic narration' if all(s['narration_origin']=='synthetic' for s in scenes) else 'Narration sources recorded in provenance.json'
    final_temp = out/'video.partial.mp4'
    sub_inputs=[];sub_maps=[]
    kinds=['source','target','bilingual'] if subtitle_settings['mode']=='bilingual' else ['source'] if subtitle_settings['mode']=='single' else []
    for i,kind in enumerate(kinds):
        language=(subtitle_settings.get('source_language') or data.get('language','zh')) if kind=='source' else subtitle_settings['target_language']
        code='mul' if kind=='bilingual' else 'zho' if language.startswith('zh') else 'eng' if language.startswith('en') else 'und'
        default=not subtitle_settings['burn_in'] and kind==('bilingual' if subtitle_settings['mode']=='bilingual' else 'source')
        sub_inputs+=['-i',out/f'subtitles.{kind}.srt']
        sub_maps+=['-map',f'{i+1}:0','-metadata:s:s:'+str(i),'title='+kind,'-metadata:s:s:'+str(i),'language='+code,'-disposition:s:'+str(i),'default' if default else '0']
    command([tool('ffmpeg'),'-v','error','-y','-f','concat','-safe','1','-i',concat,*sub_inputs,
             '-map','0:v:0','-map','0:a:0',*sub_maps,'-c:v','copy','-c:a','aac','-b:a','128k',*(['-c:s','mov_text'] if kinds else []),
             '-af',f'aresample=48000:async=1:min_hard_comp=0.001:first_pts=0,apad=whole_len={round(clock*48000)},atrim=end_sample={round(clock*48000)},asetpts=N/SR/TB',
             '-metadata','comment='+disclosure,
             '-movflags','+faststart',final_temp])
    final_temp.replace(out/'video.mp4')
    info = probe(out/'video.mp4')
    actual = float(info['format']['duration'])
    expected={'video','audio'}|({'subtitle'} if kinds else set())
    if abs(actual-clock) > .4 or not expected <= {s['codec_type'] for s in info['streams']}:
        raise RuntimeError('Final duration/track validation failed')
    if subtitle_settings['mode']=='off':captions.clear_exports(out)
    record = {'schema_version':1,'style':style,'subtitles':subtitle_settings,'audio_pipeline':'PCM scene intermediates; timestamp gaps reconciled at cuts; AAC encoded once after joining','synthetic_narration':any(s['narration_origin']=='synthetic' for s in scenes),'seconds':actual,'planned_seconds':clock,
              'subtitle_note':'Caption units are timed from actual sentence PCM or explicitly provided aligned cues; bilingual lines share exact timestamps. No character-rate duration estimates.',
              'source_note':data.get('source_note','Scenes assembled from supplied materials; no live recording is implied.'),
              'scenes':scenes,'video_sha256':digest(out/'video.mp4')}
    dump(out/'provenance.json',record)
    (out/'chapters.txt').write_text('\n'.join(f'{int(s["start"])//60:02}:{int(s["start"])%60:02} {s["title"]}' for s in scenes),encoding='utf-8')
    subtitle_note='字幕已直接显示在画面上，另附 SRT / VTT 字幕文件。' if kinds and subtitle_settings['burn_in'] else '字幕可在支持字幕的播放器中选择；另附 SRT / VTT。' if kinds else '本视频未添加字幕。'
    (out/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>视频预览</title><style>body{font:17px/1.8 system-ui;max-width:1000px;margin:36px auto}video{width:100%}</style><h1>'+html.escape(data.get('title','教程视频'))+'</h1><p>'+html.escape(disclosure)+'</p><video controls src="video.mp4"></video><p>'+html.escape(record['source_note'])+'</p><p>'+subtitle_note+'</p>',encoding='utf-8')
    print(json.dumps({'video':str(out/'video.mp4'),'seconds':actual},ensure_ascii=False))

def listening_pack(a):
    """Export recorded synthetic previews without TTS, model setup or network."""
    bundled = ROOT/'assets/auditions'
    entries = json.loads((bundled/'samples.json').read_text())
    by_id = {x['id']:x for x in entries}
    selected = [v for v in PRESETS if (a.language=='all' or v['language'].startswith(a.language))
                and (not a.gender or v['gender']==a.gender)]
    if not selected:
        raise ValueError('No voices match the requested language/gender')
    ready = []
    for v in selected:
        entry = by_id.get(v['id'])
        signature = hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if not entry or entry.get('preset_sha256')!=signature:
            raise ValueError('Bundled preview is missing or outdated for '+v['id']+'; generate a new audition for this preset.')
        source = bundled/entry['file']
        if source.parent!=bundled or not source.is_file() or digest(source)!=entry.get('sha256'):
            raise ValueError('Bundled preview file is missing or damaged: '+v['id'])
        ready.append((v,entry,source))
    out = Path(a.output).resolve()
    if out==bundled.resolve():raise ValueError('Choose a project output directory; do not overwrite bundled previews')
    out.mkdir(parents=True,exist_ok=True)
    samples = []
    for v,entry,source in ready:
        dest = out/source.name
        if source.resolve()!=dest.resolve():shutil.copy2(source,dest)
        samples.append({k:v[k] for k in ('id','label','language','gender')} |
                       {'file':dest.name,'seconds':entry['seconds'],'audio':str(dest)})
    dump(out/'samples.json',samples)
    write_audition_page(out,samples)
    (out/'auditions.md').write_text('\n\n'.join(x['label']+'\n\n!['+x['label']+'](<'+x['audio']+'>)' for x in samples),encoding='utf-8')
    result={'page':str(out/'index.html'),'markdown':str(out/'auditions.md'),'samples':samples,
            'note':'AI synthetic previews. Present inline audio, wait for selection, then render. Playing these files does not send text or require a model.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

async def audition(a):
    out = Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    cache = out/'work'; cache.mkdir(exist_ok=True)
    selected = [preset(a.preset)] if a.preset else [v for v in PRESETS if v['engine'] in ('edge','qwen-design') and (a.language=='all' or v['language'].startswith(a.language))]
    samples = []
    for v in selected:
        if v['engine'] == 'kokoro':
            raise ValueError('For Kokoro audition, render one short scene with its model paths.')
        text = a.text or ('大家好。先看这段简短讲解，再选择你喜欢的声音。接下来，我们把操作步骤做成清楚易懂的教程视频。' if v['language'].startswith('zh') else 'Welcome. Listen to this short explanation and choose the voice you prefer. Next, we will turn a few simple steps into a clear tutorial video.')
        audio,cues,timing,provenance = await synthesize(text,v,out,cache,a.allow_online)
        dest = out/(v['id']+audio.suffix); shutil.copy2(audio,dest)
        samples.append({'id':v['id'],'label':v['label'],'language':v['language'],'gender':v['gender'],'file':dest.name,'seconds':duration(dest)})
        print(v['id'],flush=True)
    dump(out/'samples.json',samples)
    write_audition_page(out,samples)

def write_audition_page(out,samples):
    known = {v['id']:v for v in PRESETS}
    cards = ''.join('<section data-group="'+('zh' if x['id'].startswith('zh') else 'en')+'-'+known[x['id']]['gender']+'"><h2>'+html.escape(x['label'])+'</h2><p>'+html.escape(x['id'])+'</p><audio controls preload="none" src="'+html.escape(x['file'],quote=True)+'"></audio><button class="pick" data-preset="'+html.escape(x['id'],quote=True)+'">选这个声音</button></section>' for x in samples)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>中英文声线试听</title><style>body{font:17px/1.7 system-ui;max-width:900px;margin:40px auto;padding:0 20px;background:#f4f7fc;color:#17243a}section{background:white;padding:18px 24px;margin:16px 0;border:2px solid transparent;border-radius:16px}section.chosen{border-color:#315de8}audio{width:100%;display:block;margin:10px 0}h2{font-size:21px}button{font:inherit;cursor:pointer;border:1px solid #bdc9e1;border-radius:9px;padding:7px 15px;background:white;margin:4px}button:hover{background:#eaf0ff}#selection{background:#eaf0ff;padding:16px;border-radius:12px;white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>先试听，再选声音</h1><p>AI 合成声线；风格名称只是选择提示，效果以试听为准。中文女声 2 种，中文男声、英文女声和英文男声各 3 种。知晴、明朗、修远为本地 Qwen 设计的青年普通话预设，本套目录已选择保留；其他使用者可试听并按需调整。英文 Heart 为本地 Kokoro，其余为 Microsoft 在线预设。页面播放已生成的文件，不会重新发送文本。</p><nav><button data-filter="all">全部</button><button data-filter="zh-female">中文女声</button><button data-filter="zh-male">中文男声</button><button data-filter="en-female">English female</button><button data-filter="en-male">English male</button></nav><p id="selection">点击播放试听，再点击“选这个声音”。将显示的语句回复给 Codex，或下载配置文件附到对话中；此页面不会自动发消息。</p><p><a id="selection-download" hidden download="voice-selection.json">下载声线配置</a></p>'''+cards+'''<script>document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{document.querySelectorAll('section').forEach(s=>s.hidden=b.dataset.filter!=='all'&&s.dataset.group!==b.dataset.filter)});document.querySelectorAll('.pick').forEach(b=>b.onclick=()=>{document.querySelectorAll('section').forEach(s=>s.classList.remove('chosen'));b.closest('section').classList.add('chosen');document.getElementById('selection').textContent='把这句话发给 Codex：请用 $narrated-tutorials，声线选择 '+b.dataset.preset+'，制作我的教程视频。';const link=document.getElementById('selection-download');link.href='data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify({schema_version:1,voice:{preset:b.dataset.preset}},null,2));link.hidden=false});document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(o=>{if(o!==a)o.pause()})));</script></html>'''
    (out/'index.html').write_text(page,encoding='utf-8')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action',required=True)
    sub.add_parser('voices')
    q=sub.add_parser('listen',help='Export bundled audio previews without network or voice models');q.add_argument('--output',required=True);q.add_argument('--language',choices=['zh','en','all'],default='all');q.add_argument('--gender',choices=['female','male'])
    q=sub.add_parser('doctor'); q.add_argument('--font')
    q=sub.add_parser('vs-check');q.add_argument('--url',default='http://127.0.0.1:3900')
    q=sub.add_parser('audition');q.add_argument('--output',required=True);q.add_argument('--language',choices=['zh','en','all'],default='all');q.add_argument('--preset');q.add_argument('--text');q.add_argument('--allow-online',action='store_true')
    q=sub.add_parser('render');q.add_argument('manifest');q.add_argument('--output',required=True);q.add_argument('--font');q.add_argument('--allow-online',action='store_true');q.add_argument('--overwrite',action='store_true')
    a = p.parse_args()
    try:
        if a.action=='voices':
            print(json.dumps(PRESETS,ensure_ascii=False,indent=2))
        elif a.action=='listen':
            listening_pack(a)
        elif a.action=='doctor':
            import PIL
            import edge_tts
            print(json.dumps({'python':sys.version.split()[0],'ffmpeg':tool('ffmpeg'),'ffprobe':tool('ffprobe'),'font':font_path(a.font),'pillow':PIL.__version__,'edge_tts':edge_tts.__version__},ensure_ascii=False,indent=2))
        elif a.action=='vs-check':
            raw,headers=local_request(a.url,'/engines');print(raw.decode())
        elif a.action=='audition':
            asyncio.run(audition(a))
        elif a.action=='render':
            asyncio.run(render(a))
    except (ValueError,KeyError,RuntimeError,OSError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
