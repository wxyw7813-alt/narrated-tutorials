"""Behavioral checks. Fake service returns a tone, not cloned speech."""
import argparse, asyncio, importlib.util, io, json, math, struct, tempfile, threading, unittest, wave
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio',ROOT/'narrated-tutorials/scripts/studio.py')
studio=importlib.util.module_from_spec(spec);spec.loader.exec_module(studio)
def tone(seconds=4, amplitude=5000):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setparams((1,2,24000,0,'NONE','not compressed'))
        w.writeframes(b''.join(struct.pack('<h',round(amplitude*math.sin(2*math.pi*220*i/24000))) for i in range(round(24000*seconds))))
    return out.getvalue()
class Handler(BaseHTTPRequestHandler):
    calls=[];mode='ok';output=tone(2)
    def log_message(self,*a):pass
    def do_POST(self):
        body=self.rfile.read(int(self.headers['Content-Length']))
        Handler.calls.append((self.path,body))
        if Handler.mode=='redirect':
            self.send_response(302);self.send_header('Location','https://example.com/receive');self.end_headers();return
        self.send_response(200);self.send_header('Content-Type','audio/wav')
        if Handler.mode=='dropped':self.send_header('X-OmniVoice-Dropped-Chunks','1')
        self.end_headers();self.wfile.write(self.output)
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.ref=self.root/'private-reference.wav';self.ref.write_bytes(tone())
        self.work=self.root/'cache';self.work.mkdir();Handler.calls=[];Handler.mode='ok'
        self.voice={'provider':'voicestudio','url':self.url,'engine':'omnivoice','language':'Chinese','reference_audio':str(self.ref),'reference_text':'Protocol fixture, not a person.','authorization':'Test synthetic tone; not a real voice.'}
    def tearDown(self):self.temp.cleanup()
    def generate(self,voice=None):return asyncio.run(studio.synthesize('Test narration.',voice or self.voice,self.root,self.work))
    def test_protocol_cache_and_reference_change(self):
        audio,cues,timing,meta=self.generate();self.assertGreater(studio.duration(audio),1.9)
        self.assertEqual(timing,'scene-estimated');self.assertEqual(len(Handler.calls),1)
        path,body=Handler.calls[0];self.assertEqual(path,'/generate')
        for value in [b'name="ref_audio"',b'name="ref_text"',b'name="engine"',b'omnivoice',b'name="stream"',b'false']:self.assertIn(value,body)
        self.assertNotIn(str(self.ref).encode(),body);self.assertFalse((self.work/'reference-normalized.wav').exists())
        self.generate();self.assertEqual(len(Handler.calls),1)
        self.ref.write_bytes(tone(amplitude=3500));self.generate();self.assertEqual(len(Handler.calls),2)
        self.assertNotIn('authorization',json.dumps(meta));self.assertNotIn(str(self.ref),json.dumps(meta))
    def test_missing_authorization_no_request(self):
        v={**self.voice,'authorization':''}
        with self.assertRaisesRegex(ValueError,'authorization'):self.generate(v)
        self.assertFalse(Handler.calls)
    def test_online_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'authorized'):self.generate(studio.preset('zh-xiaoxiao-broadcast'))
    def test_remote_origin_rejected(self):
        for url in ['https://example.com','http://127.0.0.1.evil.test','http://127.0.0.1/other','http://user:pass@127.0.0.1']:
            with self.assertRaises(ValueError):studio.local_url(url)
    def test_long_reference_rejected(self):
        self.ref.write_bytes(tone(21))
        with self.assertRaisesRegex(ValueError,'3–20'):self.generate()
        self.assertFalse(Handler.calls)
    def test_dropped_text_rejected(self):
        Handler.mode='dropped'
        with self.assertRaisesRegex(RuntimeError,'missing narration'):self.generate()
        self.assertFalse((self.work/'reference-normalized.wav').exists())
    def test_redirect_does_not_forward_reference(self):
        Handler.mode='redirect'
        with self.assertRaisesRegex(ValueError,'redirect'):self.generate()
        self.assertEqual(len(Handler.calls),1)
    def test_cache_corruption_is_regenerated(self):
        audio,*_=self.generate();audio.write_bytes(b'bad file');self.generate();self.assertEqual(len(Handler.calls),2)
    def test_local_model_hash_changes_with_weights(self):
        model=self.root/'model';model.mkdir();(model/'config.json').write_text('{}');weights=model/'model.safetensors';weights.write_bytes(b'first')
        first=studio.model_digest(model);(model/'.range-parts').mkdir();(model/'.range-parts/partial').write_bytes(b'partial download')
        self.assertEqual(first,studio.model_digest(model))
        weights.write_bytes(b'changed');self.assertNotEqual(first,studio.model_digest(model))
    def test_qwen_needs_explicit_local_setup(self):
        # An explicit nonexistent model path fails locally, without contacting a service.
        v={'engine':'qwen-design','python':str(self.root/'no-python'),'model':str(self.root/'no-model'),'instruct':'Youth Mandarin voice'}
        with self.assertRaisesRegex(ValueError,'model path'):self.generate(v)
        self.assertFalse(Handler.calls)
    def test_bundled_auditions_work_without_synthesis_or_tools(self):
        from unittest.mock import patch
        import subprocess,sys
        # -S excludes site-packages, including Pillow and all TTS dependencies.
        clean=json.loads(subprocess.check_output([sys.executable,'-S',str(studio.ROOT/'scripts/studio.py'),'listen','--language','all','--output',str(self.root/'clean-python')]))
        self.assertEqual(len(clean['samples']),11)
        args=argparse.Namespace(output=str(self.root/'listen'),language='all',gender=None)
        with patch.object(studio,'synthesize',side_effect=AssertionError('No synthesis allowed')),patch.object(studio,'tool',side_effect=AssertionError('No media tools needed')):
            result=studio.listening_pack(args)
        self.assertEqual(len(result['samples']),11)
        self.assertNotIn('zh-qingcheng-youth',[x['id'] for x in result['samples']])
        for item in result['samples']:
            self.assertEqual(Path(item['audio']).read_bytes(),(studio.ROOT/'assets/auditions'/item['file']).read_bytes())
            self.assertIn(item['audio'],Path(result['markdown']).read_text())
        self.assertTrue(Path(result['page']).is_file());self.assertFalse(Handler.calls)
    def test_bundled_auditions_filter_language_and_gender(self):
        for language,gender,count in [('zh','female',2),('zh','male',3),('en','female',3),('en','male',3)]:
            result=studio.listening_pack(argparse.Namespace(output=str(self.root/f'{language}-{gender}'),language=language,gender=gender))
            self.assertEqual(len(result['samples']),count)
            self.assertTrue(all(s['language'].startswith(language) and s['gender']==gender for s in result['samples']))
    def test_bundled_auditions_reject_damaged_or_changed_presets(self):
        from unittest.mock import patch
        import shutil
        private_skill=self.root/'skill';shutil.copytree(studio.ROOT/'assets/auditions',private_skill/'assets/auditions')
        args=argparse.Namespace(output=str(self.root/'listen'),language='zh',gender='female')
        entry=json.loads((private_skill/'assets/auditions/samples.json').read_text())[0]
        sample=private_skill/'assets/auditions'/entry['file'];original=sample.read_bytes();sample.write_bytes(b'corrupted')
        with patch.object(studio,'ROOT',private_skill):
            with self.assertRaisesRegex(ValueError,'damaged'):studio.listening_pack(args)
        self.assertFalse(Path(args.output).exists())
        sample.write_bytes(original)
        changed=[dict(v,rate='+99%') if v['id']==entry['id'] else v for v in studio.PRESETS]
        with patch.object(studio,'PRESETS',changed):
            with self.assertRaisesRegex(ValueError,'outdated'):studio.listening_pack(args)
    def test_provided_caption_boundaries(self):
        scene={'narration':'First. Second.','captions':[{'text':'First.','start':.1,'end':1},{'text':'Second.','start':1.3,'end':2.4}]}
        cues=studio.captions.supplied(scene,studio.captions.config(),3)
        self.assertEqual([x['start'] for x in cues],[.1,1.3])
        scene['captions'][1]['start']=.8
        with self.assertRaises(ValueError):studio.captions.supplied(scene,studio.captions.config(),3)
    def test_pointer_targets_and_times_rejected(self):
        bad=[{'time':0,'x':-1,'y':10},{'time':6,'x':10,'y':10}]
        for key in bad:
            with self.assertRaises(ValueError):studio.visuals.pointer_plan({'pointer':{'space':'frame','keyframes':[key]}},5,self.root)
        with self.assertRaises(ValueError):studio.visuals.pointer_plan({'pointer':{'space':'frame','keyframes':[{'at':.5,'x':100,'y':100},{'at':.5,'x':200,'y':200}]}},5,self.root)
    def test_style_settings_reject_invalid_speed(self):
        for overrides in ({'fps':0},{'pointer_scale':float('nan')},{'tail_seconds':-1}):
            with self.assertRaises(ValueError):studio.visuals.settings(overrides)
    def test_animated_pointer_and_click_render_at_target(self):
        from PIL import Image
        image=self.root/'screenshot.png';Image.new('RGB',(640,360),'#c9d8f9').save(image)
        manifest=self.root/'pointer.json';out=self.root/'animated'
        manifest.write_text(json.dumps({'schema_version':1,'subtitles':{'burn_in':False},'scenes':[{'title':'Pointer test','narration':'Timing test tone.','captions':[{'text':'Timing test tone.','start':0,'end':4}],'image':str(image),'audio':str(self.ref),'pointer':{'keyframes':[{'at':0,'x':100,'y':120},{'at':.8,'x':500,'y':120,'click':True}]}}]}))
        asyncio.run(studio.render(argparse.Namespace(manifest=str(manifest),output=str(out),font=None,allow_online=False,overwrite=False)))
        frames=[]
        for i,t in enumerate((0,4.1)):
            p=self.root/f'frame-{i}.png';studio.command([studio.tool('ffmpeg'),'-v','error','-y','-ss',str(t),'-i',out/'video.mp4','-frames:v','1',p]);frames.append(Image.open(p).convert('RGB'))
        def whites(im,x):return sum(min(p)>235 for p in im.crop((x,460,x+80,560)).getdata())
        self.assertGreater(whites(frames[0],545),100);self.assertLess(whites(frames[0],1290),5)
        self.assertGreater(whites(frames[1],1290),100);self.assertLess(whites(frames[1],545),5)
        yellow=sum(p[0]>200 and 90<p[1]<230 and p[2]<110 for p in frames[1].crop((1235,410,1360,535)).getdata())
        self.assertGreater(yellow,100)
        meta=json.loads((out/'provenance.json').read_text());self.assertTrue(meta['scenes'][0]['pointer_overlay'])
    def test_render_imported_audio_and_short_video(self):
        from PIL import Image
        image=self.root/'source.png';Image.new('RGB',(640,360),'#c9d8f9').save(image)
        video=self.root/'source.mp4'
        studio.command([studio.tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=20','-t','0.6','-c:v','libx264',video])
        project={'schema_version':1,'title':'Media pipeline test','language':'en-US','subtitles':{'burn_in':False},'scenes':[
            {'title':'Image and numbered marker','narration':'This fixture is a tone, not human speech.','image':str(image),'callouts':[{'number':1,'x':320,'y':180}],'audio':str(self.ref),'audio_origin':'provided-unknown'},
            {'title':'Short source clip is held','narration':'This checks timing only.','video':str(video),'audio':str(self.ref),'audio_origin':'provided-unknown'}]}
        for scene in project['scenes']:scene['captions']=[{'text':scene['narration'],'start':0,'end':4}]
        manifest=self.root/'project.json';manifest.write_text(json.dumps(project))
        out=self.root/'result'
        asyncio.run(studio.render(argparse.Namespace(manifest=str(manifest),output=str(out),font=None,allow_online=False,overwrite=False)))
        info=studio.probe(out/'video.mp4');self.assertEqual({x['codec_type'] for x in info['streams']},{'video','audio','subtitle'})
        record=json.loads((out/'provenance.json').read_text());self.assertAlmostEqual(record['seconds'],9.5,delta=.1)
        self.assertFalse(record['synthetic_narration'])
        self.assertTrue(all(s['audio_duration']<=s['duration'] for s in record['scenes']))
        self.assertTrue(all(s['subtitle_timing']=='provided-audio-aligned-captions' for s in record['scenes']))
        studio.command([studio.tool('ffmpeg'),'-v','error','-i',out/'video.mp4','-f','null','-'])
    def test_caption_pair_and_transcript_validation(self):
        self.assertEqual(studio.captions.config({'mode':'bilingual'},'en-US')['target_language'],'zh')
        self.assertEqual(studio.captions.config({'mode':'bilingual'},'zh-CN')['target_language'],'en')
        settings=studio.captions.config({'mode':'bilingual'})
        with self.assertRaisesRegex(ValueError,'paired'):studio.captions.units({'narration':'Hello.'},settings)
        with self.assertRaisesRegex(ValueError,'translation'):studio.captions.units({'narration':'Hello.','captions':[{'text':'Hello.'}]},settings)
        with self.assertRaisesRegex(ValueError,'match narration'):studio.captions.units({'narration':'Hello.','captions':[{'text':'Different.','translation':'不同。'}]},settings)
        with self.assertRaisesRegex(ValueError,'aligned caption'):studio.captions.supplied({'narration':'Hello.'},studio.captions.config(),4)
    def test_sentence_timing_comes_from_real_pcm(self):
        calls=[]
        async def fake(text,*args):
            calls.append(text);p=self.root/f'sentence-{len(calls)}.wav'
            # Known .30 s leading silence + 1 s signal + .20 s trailing silence.
            with wave.open(str(p),'wb') as w:
                w.setparams((1,2,48000,0,'NONE','not compressed'))
                signal=[0]*14400+[round(6000*math.sin(2*math.pi*220*i/48000)) for i in range(48000)]+[0]*9600
                w.writeframes(struct.pack('<'+'h'*len(signal),*signal))
            return p,[],None,{'provider':'fixture'}
        scene={'narration':'你好。再见。','captions':[{'text':'你好。','translation':'Hello.'},{'text':'再见。','translation':'Goodbye.'}]}
        settings=studio.captions.config({'mode':'bilingual'})
        output,cues,timing,_=asyncio.run(studio.captions.generate(scene,settings,{},self.root,self.work,False,fake,studio.command,studio.tool('ffmpeg')))
        self.assertEqual(calls,['你好。','再见。']);self.assertEqual(timing,'measured-sentence-audio')
        self.assertAlmostEqual(cues[0]['start'],.06,delta=.005);self.assertAlmostEqual(cues[0]['end'],1.06,delta=.005)
        self.assertAlmostEqual(cues[1]['start'],1.36,delta=.005)
        samples=studio.captions.pcm(output);first,last=studio.captions.speech_span(samples)
        self.assertAlmostEqual(cues[0]['start'],first/48000,delta=.005);self.assertAlmostEqual(cues[1]['end'],last/48000,delta=.005)
    def test_bilingual_exports_share_exact_timecodes(self):
        cues=[{'text':'你好。','translation':'Hello.','start':.06,'end':1.1},{'text':'再见。','translation':'Goodbye.','start':1.4,'end':2.3}]
        studio.captions.exports(self.root,cues,True)
        files=[(self.root/f'subtitles.{k}.srt').read_text() for k in ('source','target','bilingual')]
        import re
        stamps=[re.findall(r'.* --> .*',x) for x in files];self.assertEqual(stamps[0],stamps[1]);self.assertEqual(stamps[1],stamps[2])
        self.assertIn('你好。\nHello.',files[2]);self.assertTrue((self.root/'subtitles.vtt').read_text().startswith('WEBVTT'))
        studio.captions.exports(self.root,cues,False);self.assertFalse((self.root/'subtitles.bilingual.srt').exists());self.assertNotIn('Hello.',(self.root/'subtitles.srt').read_text())
    def test_pointer_uses_caption_times_after_voice_change(self):
        scene={'pointer':{'space':'frame','keyframes':[{'caption':2,'offset':.1,'x':100,'y':100}]}}
        a=studio.captions.pointer_scene(scene,[{'start':0,'end':1},{'start':1.2,'end':2}])
        b=studio.captions.pointer_scene(scene,[{'start':0,'end':3},{'start':3.2,'end':4}])
        self.assertAlmostEqual(a['pointer']['keyframes'][0]['time'],1.3);self.assertAlmostEqual(b['pointer']['keyframes'][0]['time'],3.3)
    def test_bilingual_burn_in_and_three_selectable_tracks(self):
        from PIL import Image
        import subprocess
        project={'schema_version':1,'language':'zh-CN','subtitles':{'mode':'bilingual'},'scenes':[{'title':'双语测试','narration':'操作步骤。','audio':str(self.ref),'captions':[{'text':'操作步骤。','translation':'Follow the steps.','start':.4,'end':3.8}]}]}
        manifest=self.root/'bilingual.json';manifest.write_text(json.dumps(project));out=self.root/'bilingual'
        asyncio.run(studio.render(argparse.Namespace(manifest=str(manifest),output=str(out),font=None,allow_online=False,overwrite=False)))
        streams=studio.probe(out/'video.mp4')['streams'];subs=[s for s in streams if s['codec_type']=='subtitle'];self.assertEqual(len(subs),3)
        self.assertEqual([s['tags']['language'] for s in subs],['zho','eng','mul'])
        raw=subprocess.run([studio.tool('ffmpeg'),'-v','error','-i',str(out/'video.mp4'),'-vf','crop=2:2:0:900','-f','rawvideo','-pix_fmt','rgb24','-'],check=True,capture_output=True).stdout
        active=[i for i in range(len(raw)//12) if raw[i*12]<80]
        self.assertAlmostEqual(active[0]/20,.4,delta=.05)
        frame=self.root/'bilingual-frame.png';studio.command([studio.tool('ffmpeg'),'-v','error','-y','-ss','0.8','-i',out/'video.mp4','-frames:v','1',frame]);im=Image.open(frame).convert('RGB')
        self.assertGreater(sum(min(p)>235 for p in im.crop((100,925,1800,990)).getdata()),50)
        self.assertGreater(sum(180<p[0]<230 and p[2]>230 for p in im.crop((100,990,1800,1080)).getdata()),50)
    def test_subtitles_can_be_disabled(self):
        project={'schema_version':1,'subtitles':{'mode':'off'},'scenes':[{'title':'No subtitles','narration':'Test tone','audio':str(self.ref),'captions':[{'text':'Test tone','start':.05,'end':3.9}],'pointer':{'space':'frame','keyframes':[{'caption':1,'x':100,'y':100}]}}]}
        manifest=self.root/'off.json';manifest.write_text(json.dumps(project));out=self.root/'off'
        out.mkdir();(out/'subtitles.bilingual.srt').write_text('stale subtitles');(out/'notes.txt').write_text('keep')
        asyncio.run(studio.render(argparse.Namespace(manifest=str(manifest),output=str(out),font=None,allow_online=False,overwrite=False)))
        self.assertNotIn('subtitle',[s['codec_type'] for s in studio.probe(out/'video.mp4')['streams']])
        self.assertFalse((out/'subtitles.bilingual.srt').exists());self.assertTrue((out/'notes.txt').exists())
    def test_final_audio_and_burned_caption_start_together(self):
        from unittest.mock import patch
        import subprocess
        async def fake(text,*args):
            p=self.root/'padded-source.wav'
            with wave.open(io.BytesIO(tone(.8)),'rb') as original:signal=original.readframes(original.getnframes())
            with wave.open(str(p),'wb') as w:
                w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(bytes(14400)+signal+bytes(9600))
            return p,[],None,{'provider':'test-padded-audio'}
        project={'schema_version':1,'subtitles':{'mode':'bilingual'},'scenes':[{'title':'Audio/caption sync','narration':'First. Second.','captions':[{'text':'First.','translation':'第一句。'},{'text':'Second.','translation':'第二句。'}]}]}
        manifest=self.root/'sync.json';manifest.write_text(json.dumps(project));out=self.root/'sync'
        with patch.object(studio,'synthesize',fake):asyncio.run(studio.render(argparse.Namespace(manifest=str(manifest),output=str(out),font=None,allow_online=False,overwrite=False)))
        final_pcm=self.root/'decoded-final.wav';studio.command([studio.tool('ffmpeg'),'-v','error','-y','-i',out/'video.mp4','-vn','-ac','1','-ar','48000','-c:a','pcm_s16le',final_pcm])
        start,_=studio.captions.speech_span(studio.captions.pcm(final_pcm));audio_start=start/48000
        timeline=json.loads((out/'caption-timeline.json').read_text());self.assertAlmostEqual(timeline[0]['start'],audio_start,delta=.05)
        raw=subprocess.run([studio.tool('ffmpeg'),'-v','error','-i',str(out/'video.mp4'),'-vf','crop=2:2:0:900','-f','rawvideo','-pix_fmt','rgb24','-'],check=True,capture_output=True).stdout
        first_frame=next(i for i in range(len(raw)//12) if raw[i*12]<80)/20
        self.assertLessEqual(first_frame-audio_start,.05);self.assertLessEqual(audio_start-first_frame,.05)
    def test_twenty_scene_cuts_do_not_accumulate_audio_delay(self):
        pulse=self.root/'pulse.wav';pulse.write_bytes(tone(.273))
        project={'schema_version':1,'subtitles':{'burn_in':False},'scenes':[{'title':f'Cut {i}','narration':'Pulse.','audio':str(pulse),'captions':[{'text':'Pulse.','start':0,'end':.273}]} for i in range(20)]}
        manifest=self.root/'cuts.json';manifest.write_text(json.dumps(project));out=self.root/'cuts'
        asyncio.run(studio.render(argparse.Namespace(manifest=str(manifest),output=str(out),font=None,allow_online=False,overwrite=False)))
        decoded=self.root/'cuts.wav';studio.command([studio.tool('ffmpeg'),'-v','error','-y','-i',out/'video.mp4','-vn','-ac','1','-ar','48000','-c:a','pcm_s16le',decoded])
        samples=studio.captions.pcm(decoded);hop=240;onsets=[];previous=False
        for index in range(0,len(samples),hop):
            active=max(abs(x) for x in samples[index:index+hop])>200
            if active and not previous:onsets.append(index/48000)
            previous=active
        self.assertEqual(len(onsets),20)
        self.assertTrue(all(abs(t-i*1.05)<.05 for i,t in enumerate(onsets)),onsets)
        timeline=json.loads((out/'caption-timeline.json').read_text());self.assertTrue(all(abs(c['start']-i*1.05)<.001 for i,c in enumerate(timeline)))
if __name__=='__main__':unittest.main(verbosity=2)
