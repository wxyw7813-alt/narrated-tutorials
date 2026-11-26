"""Preview, templates, review evidence and real browser capture behavior."""
import argparse,asyncio,functools,http.server,importlib.util,json,math,struct,subprocess,tempfile,threading,unittest,wave
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_workflow',ROOT/'narrated-tutorials/scripts/studio.py');studio=importlib.util.module_from_spec(spec);spec.loader.exec_module(studio)
import reviewing,capturing

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.audio=self.root/'pulse.wav'
        with wave.open(str(self.audio),'wb') as w:
            w.setparams((1,2,48000,0,'NONE','not compressed'))
            w.writeframes(b''.join(struct.pack('<h',round(5000*math.sin(2*math.pi*220*i/48000))) for i in range(48000)))
    def tearDown(self):self.tmp.cleanup()
    def scene(self,title='First',**extra):return dict(title=title,narration='A synthetic test tone.',audio=str(self.audio),captions=[{'text':'A synthetic test tone.','start':.01,'end':.98}],**extra)
    def render(self,project,**extra):
        p=self.root/'project.json';p.write_text(json.dumps(project));out=self.root/'result'
        args=dict(manifest=str(p),output=str(out),font=None,allow_online=False,overwrite=False);args.update(extra)
        asyncio.run(studio.render(argparse.Namespace(**args)));return out
    def test_template_overrides_are_visible_and_user_style_wins(self):
        from PIL import Image
        style=studio.visuals.settings({'accent':'#bb2200'},'concept-explainer')
        self.assertEqual(style['accent'],'#bb2200');self.assertEqual(style['background'],'#faf8f2')
        frame=self.root/'frame.png';studio.make_card({'title':'Template','narration':'Test'},frame,self.root,studio.font_path(),style)
        im=Image.open(frame);self.assertEqual(im.getpixel((0,0)),(187,34,0));self.assertEqual(im.getpixel((1900,500)),(250,248,242))
        with self.assertRaisesRegex(ValueError,'Unknown template'):studio.visuals.settings({},'missing')
    def test_storyboard_needs_no_new_speech_and_preserves_source(self):
        data={'schema_version':1,'template':'minimal','scenes':[{'title':'Layout','narration':'No synthesis here.','points':['Step one']} ]}
        before=json.dumps(data)
        with patch.object(studio,'synthesize',side_effect=AssertionError('No speech in storyboard')):
            result=reviewing.storyboard(data,self.root,self.root/'board',studio.font_path(),studio.make_card,studio.command,studio.tool('ffmpeg'))
        self.assertEqual(json.dumps(data),before);self.assertTrue(Path(result['contact_sheet']).is_file())
        self.assertIn('No synthesis here.',Path(result['storyboard']).read_text())
    def test_scene_preview_renders_only_requested_scene(self):
        out=self.render({'schema_version':1,'scenes':[self.scene('First'),self.scene('Second')]},action='preview',preview_scenes=[2])
        meta=json.loads((out/'provenance.json').read_text());self.assertEqual(meta['render_mode'],'scene-preview')
        self.assertEqual([(x['title'],x['source_scene']) for x in meta['scenes']],[('Second',2)])
        self.assertLess(meta['seconds'],2)
        self.assertEqual(json.loads((out/'review.json').read_text())['render_mode'],'scene-preview')
    def test_preview_rejects_invalid_scene_selection(self):
        for selection in ([0],[2],[1,1]):
            with self.assertRaisesRegex(ValueError,'Preview scene numbers'):self.render({'schema_version':1,'scenes':[self.scene()]},action='preview',preview_scenes=selection)
    def test_review_uses_exported_frames_and_keeps_human_checks_pending(self):
        out=self.render({'schema_version':1,'scenes':[self.scene('Evidence')]})
        record=json.loads((out/'review.json').read_text());self.assertEqual(record['automatic_status'],'automatic_checks_passed')
        self.assertEqual(record['manual_status'],'pending');self.assertTrue(record['manual_checks'])
        self.assertGreaterEqual(len(list((out/'review-frames').glob('*.jpg'))),2)
        self.assertTrue((out/'contact-sheet.png').is_file());self.assertIn('Evidence',(out/'review.html').read_text())
        self.assertTrue(any(c['code']=='decode' and c['status']=='pass' for c in record['automatic_checks']))
    def test_protected_button_under_captions_is_flagged(self):
        out=self.render({'schema_version':1,'scenes':[self.scene(protected_regions=[{'label':'Save button','space':'frame','x':100,'y':950,'width':200,'height':50}])]})
        review=json.loads((out/'review.json').read_text());self.assertEqual(review['automatic_status'],'needs_attention')
        self.assertTrue(any(c['status']=='warning' and 'Save button' in c['detail'] for c in review['automatic_checks']))
    def test_numbered_marker_covering_protected_region_is_flagged(self):
        from PIL import Image
        image=self.root/'shot.png';Image.new('RGB',(640,360),'white').save(image)
        scene=self.scene(image=str(image),callouts=[{'number':1,'x':320,'y':180}],protected_regions=[{'label':'Important text','x':300,'y':170,'width':60,'height':30}])
        out=self.render({'schema_version':1,'scenes':[scene]});review=json.loads((out/'review.json').read_text())
        self.assertTrue(any(c['code'].startswith('marker_') and c['status']=='warning' for c in review['automatic_checks']))
    def test_capture_minimum_preserves_longer_action_video(self):
        out=self.render({'schema_version':1,'scenes':[self.scene(min_seconds=3.2)]})
        self.assertAlmostEqual(json.loads((out/'provenance.json').read_text())['seconds'],3.2,delta=.05)
    def test_review_detects_changed_video_record(self):
        out=self.render({'schema_version':1,'scenes':[self.scene()]});p=out/'provenance.json';meta=json.loads(p.read_text());meta['video_sha256']='0'*64;p.write_text(json.dumps(meta))
        reviewing.build(out,studio.probe,studio.command,studio.tool('ffmpeg'),studio.digest,studio.font_path())
        self.assertEqual(json.loads((out/'review.json').read_text())['automatic_status'],'error')
    def test_browser_plan_rejects_missing_voice_unsafe_url_and_unknown_actions(self):
        plan={'schema_version':1,'url':'http://127.0.0.1:8765/','voice':{'preset':'zh-chengyue-steady'},'steps':[{'title':'One','narration':'Test','actions':[]}]}
        capturing.validate(plan)
        for bad in (dict(plan,url='file:///private/test'),dict(plan,url='https://example.com/'),dict(plan,voice={}),dict(plan,steps=[{'title':'One','narration':'Test','actions':[{'type':'evaluate','code':'anything'}]}])):
            with self.assertRaises(ValueError):capturing.validate(bad)
        capturing.validate(dict(plan,url='https://example.com/'),allow_external=True)
    def test_browser_plan_does_not_allow_ambiguous_targets(self):
        plan={'schema_version':1,'url':'http://localhost:8765/','voice':{'preset':'zh-chengyue-steady'},'steps':[{'title':'One','narration':'Test','actions':[{'type':'click','target':{'role':'button','name':'Save','text':'Save'}}]}]}
        with self.assertRaisesRegex(ValueError,'exactly one'):capturing.validate(plan)

    def test_flow_component_is_rendered_and_rejects_overflow(self):
        from PIL import Image
        frame=self.root/'flow.png'
        studio.make_card({'title':'Flow','narration':'Diagram','flow':['Plan','Capture','Review']},frame,self.root,studio.font_path(),studio.visuals.settings(template='concept-explainer'))
        im=Image.open(frame);self.assertEqual(im.getpixel((100,450)),(22,120,111))
        with self.assertRaisesRegex(ValueError,'2–4'):studio.make_card({'title':'Flow','flow':['Only one']},frame,self.root,studio.font_path())

    def test_generated_caption_keeps_spoken_wording_when_reimported(self):
        import captions
        scene={'narration':'Python three eleven.','captions':[{'speech':'Python three eleven.','text':'Python 3.11.'}]}
        settings=captions.config({'mode':'single'},'en');work=self.root/'work';work.mkdir()
        async def voice(*args):return self.audio,None,None,{'provider':'synthetic-tone-fixture'}
        audio,cues,_,_=asyncio.run(captions.generate(scene,settings,{},self.root,work,False,voice,studio.command,studio.tool('ffmpeg')))
        imported=captions.supplied({**scene,'captions':cues},settings,float(studio.probe(audio)['format']['duration']))
        self.assertEqual(imported[0]['speech'],'Python three eleven.');self.assertEqual(imported[0]['text'],'Python 3.11.')

    def test_real_browser_capture_records_changed_page_and_failed_replacement(self):
        from PIL import Image,ImageChops
        try:subprocess.run(['node',str(ROOT/'narrated-tutorials/scripts/capture.mjs'),'--doctor'],check=True,capture_output=True)
        except (FileNotFoundError,subprocess.CalledProcessError):self.skipTest('Optional Playwright/Chromium unavailable; run npm ci and install chromium to include real capture integration')
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'narrated-tutorials/assets')))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            plan=json.loads((ROOT/'narrated-tutorials/assets/browser-plan.example.json').read_text())
            plan['url']=f'http://127.0.0.1:{server.server_port}/browser-demo.html';plan['voice']={}
            for step in plan['steps']:
                step.update(audio=str(self.audio),audio_origin='provided-unknown',hold_seconds=1.6)
                step['captions'][0].update(start=.01,end=.98)
            path=self.root/'plan.json';path.write_text(json.dumps(plan));out=self.root/'capture'
            args=argparse.Namespace(manifest=str(path),output=str(out),overwrite=False,allow_external=False,allow_online=False,headed=False)
            asyncio.run(capturing.capture(args,studio.resolve_voice,studio.synthesize,studio.command,studio.tool,studio.probe,studio.digest))
            log=json.loads((out/'capture-log.json').read_text());self.assertEqual(log['status'],'passed')
            self.assertEqual([a['type'] for a in log['steps'][1]['actions']],['select','click','expect_text'])
            self.assertTrue(all(a['status']=='passed' for step in log['steps'] for a in step['actions']))
            self.assertGreater(len(log['steps'][0]['frames']),3)
            first=Image.open(out/log['steps'][0]['frames'][0]['file']).convert('RGB')
            last=Image.open(out/'step-001.png').convert('RGB');self.assertIsNotNone(ImageChops.difference(first,last).getbbox())
            project=json.loads((out/'project.json').read_text());self.assertEqual(len(project['scenes']),2)
            self.assertGreater(project['scenes'][1]['min_seconds'],1.5)
            renderargs=argparse.Namespace(manifest=str(out/'project.json'),output=str(self.root/'rendered'),font=None,allow_online=False,overwrite=False)
            asyncio.run(studio.render(renderargs))
            review=json.loads((self.root/'rendered/review.json').read_text());self.assertNotEqual(review['automatic_status'],'error')
            # A strict ambiguous locator fails; the previous successful manifest is removed.
            plan['steps'][0]['actions']=[{'type':'click','target':{'css':'button'}}]
            path.write_text(json.dumps(plan));args.overwrite=True
            with self.assertRaises(RuntimeError):asyncio.run(capturing.capture(args,studio.resolve_voice,studio.synthesize,studio.command,studio.tool,studio.probe,studio.digest))
            self.assertEqual(json.loads((out/'capture-log.json').read_text())['status'],'failed')
            self.assertFalse((out/'project.json').exists())
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
