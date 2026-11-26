/** Optional isolated Chromium capture. Only declared actions run; no arbitrary plan JS.
 * Continuous real page screenshots are timed by a monotonic clock and assembled
 * by capturing.py. This does not attach to the user's personal browser profile.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {performance} from 'node:perf_hooks';

const sleep=ms=>new Promise(resolve=>setTimeout(resolve,Math.max(0,ms)));
const args=process.argv.slice(2);
const flag=name=>args.includes(name);
const value=name=>args[args.indexOf(name)+1];
function urlAllowed(raw,external){
  const u=new URL(raw);
  if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error('Use an HTTP(S) URL without embedded credentials.');
  if(!external&&!['localhost','127.0.0.1','[::1]'].includes(u.hostname))throw Error('External navigation needs --allow-external.');
  return u.href;
}
function locatorFor(page,target){
  if(!target||typeof target!=='object')throw Error('Action needs a declared target.');
  const count=['role','label','placeholder','test_id','text','css'].filter(k=>target[k]!==undefined).length;
  if(count!==1)throw Error('Choose exactly one target strategy: role, label, placeholder, test_id, text or css.');
  if(target.role)return page.getByRole(target.role,{name:target.name,exact:target.exact!==false});
  if(target.label)return page.getByLabel(target.label,{exact:target.exact!==false});
  if(target.placeholder)return page.getByPlaceholder(target.placeholder,{exact:target.exact!==false});
  if(target.test_id)return page.getByTestId(target.test_id);
  if(target.text)return page.getByText(target.text,{exact:target.exact!==false});
  return page.locator(target.css);
}
function safeUrl(raw){const u=new URL(raw);return u.origin+u.pathname;}
async function overlay(){
  if(!document.documentElement){document.addEventListener('DOMContentLoaded',overlay,{once:true});return;}
  if(document.getElementById('nt-teaching-pointer'))return;
  const node=document.createElement('div');node.id='nt-teaching-pointer';node.setAttribute('aria-hidden','true');
  Object.assign(node.style,{position:'fixed',left:'24px',top:'24px',width:'36px',height:'46px',zIndex:'2147483647',pointerEvents:'none',transition:'left 180ms ease-in-out, top 180ms ease-in-out'});
  node.innerHTML='<svg width="36" height="46" viewBox="0 0 36 46"><path d="M3 2 L3 34 L11 27 L20 43 L27 39 L18 23 L31 23 Z" fill="white" stroke="#17243a" stroke-width="2"/></svg>';
  const ring=document.createElement('div');ring.id='nt-teaching-ring';ring.setAttribute('aria-hidden','true');
  Object.assign(ring.style,{position:'fixed',width:'58px',height:'58px',border:'4px solid #ffbf36',borderRadius:'50%',boxSizing:'border-box',opacity:'0',zIndex:'2147483646',pointerEvents:'none',transition:'opacity 150ms'});
  document.documentElement.append(node,ring);
}
async function point(page,x,y,click=false){
  await page.evaluate(overlay);
  await page.evaluate(({x,y})=>{const p=document.getElementById('nt-teaching-pointer');p.style.left=x+'px';p.style.top=y+'px';const r=document.getElementById('nt-teaching-ring');r.style.opacity='0';r.style.left=(x-29)+'px';r.style.top=(y-29)+'px';},{x,y});
  await page.mouse.move(x,y,{steps:8});await sleep(190);
  if(click)await page.evaluate(()=>{const r=document.getElementById('nt-teaching-ring');r.style.opacity='1';setTimeout(()=>{r.style.opacity='0'},430)});
}
async function main(){
  let chromium;
  try{({chromium}=await import('playwright'));}
  catch{throw Error('Optional Playwright package is missing. Run npm ci --prefix scripts from the Skill folder.');}
  if(flag('--doctor')){
    const executable=chromium.executablePath();let available=true;try{await fs.access(executable);}catch{available=false;}
    process.stdout.write(JSON.stringify({node:process.version,playwright:true,browser_available:available,browser:available?executable:null,setup:available?'ready':'Run npx --prefix scripts playwright install chromium after authorizing the download.'})+'\n');
    if(!available)process.exitCode=1;return;
  }
  if(!flag('--job'))throw Error('Use --job /absolute/path/prepared-capture.json');
  const job=JSON.parse(await fs.readFile(value('--job'),'utf8'));
  const out=path.resolve(job.output);await fs.mkdir(out,{recursive:true});
  const external=flag('--allow-external');const startUrl=urlAllowed(job.url,external);
  if(!Array.isArray(job.steps)||!job.steps.length)throw Error('Capture needs at least one step.');
  const viewport=job.viewport??{width:1280,height:720};
  if(!Number.isInteger(viewport.width)||!Number.isInteger(viewport.height)||viewport.width<640||viewport.width>1920||viewport.height<360||viewport.height>1200)throw Error('Use a viewport between 640×360 and 1920×1200.');
  const fps=job.fps??10;if(!Number.isInteger(fps)||fps<5||fps>20)throw Error('Capture fps must be 5–20.');
  const result={schema_version:1,status:'running',capture_method:'Playwright real browser continuous frames',source_url:safeUrl(startUrl),viewport,requested_fps:fps,pointer:'Teaching overlay following actual targets, not the OS cursor',steps:[]};
  const sensitive=job.steps.flatMap(s=>(s.actions??[]).flatMap(a=>[a.value_env?process.env[a.value_env]:'',a.value])).filter(x=>typeof x==='string'&&x.length>2);
  const redacted=message=>sensitive.reduce((s,v)=>s.split(v).join('[redacted]'),String(message)).slice(0,1000);
  const browser=await chromium.launch({headless:!flag('--headed')});
  const context=await browser.newContext({viewport,deviceScaleFactor:1});
  if(!external)await context.route('**/*',route=>{try{urlAllowed(route.request().url(),false);return route.continue();}catch{return route.abort();}});
  await context.addInitScript(overlay);const page=await context.newPage();page.setDefaultTimeout(10000);
  try{
    await page.goto(startUrl,{waitUntil:'domcontentloaded'});await page.evaluate(overlay);
    for(let index=0;index<job.steps.length;index++){
      const step=job.steps[index];const hold=Number(step.hold_seconds??3);
      if(!Number.isFinite(hold)||hold<.3||hold>300)throw Error('Step hold_seconds must be .3–300 seconds.');
      const dir=path.join(out,'frames',String(index+1).padStart(3,'0'));await fs.mkdir(dir,{recursive:true});
      for(const name of await fs.readdir(dir))if(/^frame-\d+\.png$/.test(name))await fs.unlink(path.join(dir,name));
      const frames=[];let failures=0;let active=true;let loopError;let counter=0;
      async function shot(){
        const file=path.join(dir,`frame-${String(counter++).padStart(6,'0')}.png`);const before=performance.now();
        await page.screenshot({path:file,fullPage:false,animations:'allow',caret:'hide',timeout:5000});
        frames.push({file:path.relative(out,file).split(path.sep).join('/'),at_ms:(before+performance.now())/2});
      }
      await shot();const epoch=frames[0].at_ms;
      const entry={title:step.title,frames:[],actions:[],targets:[],warnings:[],screenshot:`step-${String(index+1).padStart(3,'0')}.png`};result.steps.push(entry);
      const loop=(async()=>{while(active){const began=performance.now();try{await shot();failures=0;}catch(e){if(++failures>=3){loopError=e;active=false;break;}}await sleep(Math.max(0,1000/fps-(performance.now()-began)));}})();
      try{
        for(const action of step.actions??[]){
          if(loopError)throw loopError;
          const scheduled=action.at_seconds;
          if(scheduled!==undefined){if(!Number.isFinite(scheduled)||scheduled<0||scheduled>hold)throw Error('Action time must be inside the prepared scene.');await sleep(epoch+scheduled*1000-performance.now());}
          const start=(performance.now()-epoch)/1000;
          const log={type:action.type,target:action.target??null,start_seconds:start};entry.actions.push(log);
          if(scheduled!==undefined&&start-scheduled>.25)entry.warnings.push(`动作 ${action.type} 比语句计划晚 ${(start-scheduled).toFixed(2)} 秒，需要检查旁白与操作是否对应。`);
          if(action.type==='navigate')await page.goto(urlAllowed(new URL(action.url,page.url()).href,external),{waitUntil:'domcontentloaded'});
          else if(action.type==='scroll')await page.mouse.wheel(Number(action.x??0),Number(action.y??400));
          else if(action.type==='expect_text')await page.getByText(action.text,{exact:action.exact!==false}).waitFor({state:'visible'});
          else{
            const locator=locatorFor(page,action.target);await locator.waitFor({state:'visible'});await locator.scrollIntoViewIfNeeded();
            const box=await locator.boundingBox();if(!box)throw Error('Target has no visible bounding box.');
            entry.targets.push({label:action.target.name??action.target.label??action.target.test_id??action.target.text??action.type,...box});
            await point(page,box.x+box.width/2,box.y+box.height/2,action.type==='click');
            if(action.type==='click')await locator.click();
            else if(action.type==='fill'){
              const content=action.value_env?process.env[action.value_env]:action.value;
              if(typeof content!=='string')throw Error('Fill value or declared environment variable is missing.');
              await locator.fill(content);
            }else if(action.type==='press')await locator.press(action.key);
            else if(action.type==='select')await locator.selectOption(action.value);
            else if(action.type==='check')await locator.check();
            else if(action.type==='uncheck')await locator.uncheck();
            else if(action.type!=='hover')throw Error('Unsupported capture action: '+action.type);
          }
          if(context.pages().length!==1)throw Error('This capture version records one tab; handle the new window in a separate plan.');
          log.end_seconds=(performance.now()-epoch)/1000;log.status='passed';
        }
        await sleep(Math.max(epoch+hold*1000-performance.now(),250));
      }finally{active=false;await loop;}
      if(loopError)throw loopError;
      await page.screenshot({path:path.join(out,entry.screenshot),fullPage:false,animations:'allow',caret:'hide'});
      entry.duration_seconds=Math.max(hold,(performance.now()-epoch)/1000);
      entry.frames=frames.map(f=>({...f,at_ms:f.at_ms-epoch}));
      entry.status='passed';
      await fs.writeFile(path.join(out,'capture-log.json'),JSON.stringify(result,null,2));
    }
    result.status='passed';
  }catch(error){result.status='failed';result.error=redacted(error.message);if(result.steps.length)result.steps.at(-1).status='failed';throw new Error(result.error);}
  finally{await context.close();await browser.close();await fs.writeFile(path.join(out,'capture-log.json'),JSON.stringify(result,null,2));}
  process.stdout.write(JSON.stringify({capture_log:path.join(out,'capture-log.json'),steps:result.steps.length,status:result.status})+'\n');
}
main().catch(error=>{process.stderr.write('CAPTURE ERROR: '+error.message+'\n');process.exitCode=1});
