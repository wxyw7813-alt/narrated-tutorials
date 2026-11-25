"""Single/bilingual captions driven by actual PCM audio, never character-rate timing."""
from array import array
from pathlib import Path
import hashlib
import html
import json
import math
import re
import sys
import wave
from PIL import Image,ImageDraw,ImageFont

def config(raw=None,source_language=None):
    target='zh' if str(source_language or '').startswith('en') else 'en'
    result={'mode':'single','burn_in':True,'gap_seconds':.12,'source_language':source_language,'target_language':target,'max_font_size':40}
    result.update(raw or {})
    if result['mode'] not in ('single','bilingual','off'):
        raise ValueError('subtitles.mode must be single, bilingual or off')
    if not 0<=float(result['gap_seconds'])<=1:
        raise ValueError('subtitles.gap_seconds must be 0–1')
    if not 24<=int(result['max_font_size'])<=50:
        raise ValueError('subtitles.max_font_size must be 24–50')
    return result

def normalize(text):
    return re.sub(r'\s+','',text)

def units(scene,settings):
    given=scene.get('captions')
    if given is None:
        if settings['mode']=='bilingual':
            raise ValueError('Bilingual mode needs scene.captions with paired text and translation; the agent prepares translations before rendering.')
        pieces=re.findall(r'[^。！？!?\n]+[。！？!?]?|[^\n]+',scene['narration'])
        # English sentence boundaries; keep complete sentences, not individual words.
        given=[]
        for piece in pieces:
            given.extend({'text':x.strip()} for x in re.split(r'(?<=[.!?])\s+(?=[A-Z])',piece) if x.strip())
    if not given or len(given)>40:
        raise ValueError('Use 1–40 caption units per scene; split longer scenes.')
    result=[]
    for item in given:
        item=dict(item)
        if not str(item.get('text','')).strip():raise ValueError('Caption text is empty')
        item.setdefault('speech',item['text'])
        if settings['mode']=='bilingual' and not str(item.get('translation','')).strip():
            raise ValueError('Every bilingual caption needs a translation')
        result.append(item)
    if normalize(''.join(x['speech'] for x in result))!=normalize(scene['narration']):
        raise ValueError('Caption speech units must match narration; use speech for spoken wording and text for display wording.')
    return result

def pcm(path):
    with wave.open(str(path),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,48000):
            raise ValueError('Caption analysis expects 48 kHz mono PCM16')
        data=array('h');data.frombytes(w.readframes(w.getnframes()))
    if sys.byteorder!='little':data.byteswap()
    return data

def speech_span(samples,rate=48000):
    if not samples:raise ValueError('Empty narration audio')
    peak=max(abs(x) for x in samples)
    if peak<60:raise ValueError('Narration is silent or too quiet to time reliably')
    gate=max(32,round(peak*.003));hop=rate//200 # 5 ms analysis windows.
    active=[i for i in range(0,len(samples),hop) if max(abs(x) for x in samples[i:i+hop])>=gate]
    if not active:raise ValueError('No speech energy detected')
    return active[0],min(len(samples),active[-1]+hop)

def write_pcm(path,samples,rate=48000):
    data=array('h',samples)
    if sys.byteorder!='little':data.byteswap()
    with wave.open(str(path),'wb') as w:
        w.setparams((1,2,rate,0,'NONE','not compressed'));w.writeframes(data.tobytes())

async def generate(scene,settings,voice,base,work,allow_online,synthesize,command,ffmpeg):
    entries=units(scene,settings);combined=array('h');timed=[];provenance=[]
    for i,item in enumerate(entries):
        audio,_,_,record=await synthesize(item['speech'],voice,base,work,allow_online)
        decoded=work/f'caption-{i:02}.pcm.wav'
        command([ffmpeg,'-v','error','-y','-i',audio,'-ac','1','-ar','48000','-c:a','pcm_s16le',decoded])
        samples=pcm(decoded);a,b=speech_span(samples)
        # Retain phoneme-safe padding; timings reference measured energy, not trim edges.
        left=max(0,a-2880);right=min(len(samples),b+5760)
        origin=len(combined)
        combined.extend(samples[left:right])
        start=(origin+a-left)/48000;end=(origin+b-left)/48000
        timed.append({'text':item['text'],'translation':item.get('translation'),'start':start,'end':end})
        provenance.append(record)
        if i<len(entries)-1:combined.extend([0]*round(float(settings['gap_seconds'])*48000))
    key=hashlib.sha256(json.dumps({'scene':scene['narration'],'settings':settings,'units':entries,'provenance':provenance},sort_keys=True).encode()).hexdigest()
    output=work/(key+'.captioned.wav');write_pcm(output,combined)
    return output,timed,'measured-sentence-audio',{'provider':'caption-sentence-synthesis','units':provenance}

def supplied(scene,settings,length):
    result=units(scene,settings)
    previous=0
    for item in result:
        if 'start' not in item or 'end' not in item:
            raise ValueError('Imported audio needs aligned caption start/end times. Strict mode does not estimate timestamps from text length.')
        a,b=float(item['start']),float(item['end'])
        if not math.isfinite(a) or not math.isfinite(b) or not 0<=a<b<=length+.001 or a<previous:
            raise ValueError('Supplied caption times overlap or lie outside narration audio')
        item['start'],item['end']=a,min(b,length);previous=b
    return result

def pointer_scene(scene,cues):
    if not scene.get('pointer'):return scene
    result=dict(scene);pointer=dict(scene['pointer']);keys=[]
    for original in pointer.get('keyframes',[]):
        key=dict(original)
        if 'caption' in key:
            if 'time' in key or 'at' in key:raise ValueError('Pointer keyframe cannot mix caption with time/at')
            index=int(key.pop('caption'))-1
            if not 0<=index<len(cues):raise ValueError('Pointer caption index is out of range')
            edge=key.pop('edge','start')
            if edge not in ('start','end'):raise ValueError('Pointer caption edge must be start or end')
            key['time']=cues[index][edge]+float(key.pop('offset',0))
        keys.append(key)
    pointer['keyframes']=keys;result['pointer']=pointer
    return result

def wrapped(text,font,width):
    result=[]
    for paragraph in text.split('\n'):
        if re.search(r'[\u3400-\u9fff]',paragraph):
            current=''
            for char in paragraph:
                if current and font.getlength(current+char)>width:result.append(current);current=char
                else:current+=char
            if current:result.append(current)
        else:
            current=''
            for word in paragraph.split():
                candidate=(current+' '+word).strip()
                if current and font.getlength(candidate)>width:result.append(current);current=word
                else:current=candidate
            if current:result.append(current)
    return result

def overlay_assets(cues,settings,work,fontfile):
    outputs=[]
    for i,cue in enumerate(cues):
        lines=None
        for size in range(int(settings['max_font_size']),23,-2):
            primary=ImageFont.truetype(fontfile,size);secondary=ImageFont.truetype(fontfile,max(24,size-4))
            a=wrapped(cue['text'],primary,1750)
            b=wrapped(cue.get('translation',''),secondary,1750) if settings['mode']=='bilingual' else []
            total=len(a)*(size+8)+len(b)*(max(24,size-4)+7)
            if total<=158:lines=(a,b,primary,secondary,size,total);break
        if lines is None:raise ValueError('Caption too long to read; split it into shorter natural speech units')
        a,b,primary,secondary,size,total=lines
        image=Image.new('RGBA',(1920,182),(15,23,38,240));d=ImageDraw.Draw(image);y=(182-total)//2
        for row in a:
            d.text((960,y),row,anchor='mt',font=primary,fill='white');y+=size+8
        for row in b:
            d.text((960,y),row,anchor='mt',font=secondary,fill='#d1def5');y+=max(24,size-4)+7
        path=work/f'caption-overlay-{i:02}.png';image.save(path);outputs.append(path)
    return outputs

def filter_chain(input_label,cues,start_input,fps):
    filters=[];last=input_label
    for i,cue in enumerate(cues):
        # Start on the preceding frame: rendering quantization must not introduce lag.
        a=math.floor(cue['start']*fps)/fps;b=math.ceil(cue['end']*fps)/fps
        label=f'sub{i}'
        filters.append(f'[{last}][{start_input+i}:v]overlay=x=0:y=898:enable=\'gte(t,{a:.6f})*lt(t,{b:.6f})\':format=auto[{label}]')
        last=label
    filters.append(f'[{last}]format=yuv420p[captioned]')
    return ';'.join(filters)

def timestamp(t,web=False):
    ms=round(t*1000);separator='.' if web else ','
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}{separator}{ms%1000:03}'

def exports(out,cues,bilingual):
    if not bilingual:
        for kind in ('target','bilingual'):
            for ext in ('srt','vtt'):(out/f'subtitles.{kind}.{ext}').unlink(missing_ok=True)
    for kind in (['source','target','bilingual'] if bilingual else ['source']):
        def text(c):return c['text'] if kind=='source' else c['translation'] if kind=='target' else c['text']+'\n'+c['translation']
        srt='\n\n'.join(f'{i}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{text(c)}' for i,c in enumerate(cues,1))+'\n'
        vtt='WEBVTT\n\n'+'\n\n'.join(f'{timestamp(c["start"],True)} --> {timestamp(c["end"],True)}\n{text(c)}' for c in cues)+'\n'
        (out/f'subtitles.{kind}.srt').write_text(srt,encoding='utf-8');(out/f'subtitles.{kind}.vtt').write_text(vtt,encoding='utf-8')
    chosen='bilingual' if bilingual else 'source'
    (out/'subtitles.srt').write_bytes((out/f'subtitles.{chosen}.srt').read_bytes())
    (out/'subtitles.vtt').write_bytes((out/f'subtitles.{chosen}.vtt').read_bytes())
    (out/'caption-timeline.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')

def clear_exports(out):
    for name in ('subtitles','subtitles.source','subtitles.target','subtitles.bilingual'):
        for extension in ('srt','vtt'):(out/f'{name}.{extension}').unlink(missing_ok=True)
    (out/'caption-timeline.json').unlink(missing_ok=True)
