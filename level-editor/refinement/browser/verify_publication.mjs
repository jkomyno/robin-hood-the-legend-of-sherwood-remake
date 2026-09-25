import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdtemp,mkdir,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve,dirname,join} from 'node:path';
import {chromeEndpoint,socketOpen,evaluate as boundedEvaluate} from '../../app/tests/cdp.mjs';
const evaluate=(socket,id,expression)=>boundedEvaluate(socket,id,expression,{timeoutMs:60000});
if(!process.argv[2])throw Error('Usage: node verify_publication.mjs config.json [editor URL]');
const configPath=resolve(process.argv[2]);
const here=dirname(configPath),config=JSON.parse(await readFile(configPath,'utf8'));
const base=process.argv[3]??'http://127.0.0.1:5180';
const verifyLive=async()=>{for(const [path,hash]of Object.entries(config.protected_live_files??{})){if(createHash('sha256').update(await readFile(path)).digest('hex')!==hash)throw Error('Live file changed during read-only browser test '+path);}};
await writeFile(join(here,'result.json'),JSON.stringify({status:'RUNNING',phase:'verifying-live-input-hashes'}));
await verifyLive();
console.log('Live hashes verified; starting Chromium');
const temporaryRoot='/home/phire/.cache/sccache/leicester-browser';await mkdir(temporaryRoot,{recursive:true});
const profile=await mkdtemp(join(temporaryRoot,'p-'));
const chrome=spawn('/usr/lib/chromium/chromium',['--headless','--window-size='+(config.viewport?.width??1500)+','+(config.viewport?.height??1200),'--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--enable-unsafe-swiftshader','--use-angle=swiftshader','--remote-debugging-port=0','--user-data-dir='+profile,base],{stdio:['ignore','ignore','pipe'],env:{...process.env,TMPDIR:temporaryRoot}});
chrome.stderr.on('data',data=>process.stderr.write(data));
const closed=new Promise(resolve=>chrome.on('close',resolve));let ws,id=0;
try{
 const endpoint=new URL(await chromeEndpoint(chrome,{timeoutMs:15000}));const pages=await(await fetch('http://'+endpoint.host+'/json/list')).json();ws=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);await socketOpen(ws);
 const request=(method,params)=>new Promise((resolve,reject)=>{
  const rid=++id;
  const cleanup=()=>{clearTimeout(timer);ws.removeEventListener('message',message);ws.removeEventListener('close',closed);ws.removeEventListener('error',failed);};
  const done=(error,value)=>{cleanup();error?reject(error):resolve(value);};
  const message=e=>{const data=JSON.parse(e.data);if(data.id===rid)done(data.error,data.result);};
  const closed=()=>done(Error(method+' disconnected'));
  const failed=()=>done(Error(method+' transport failed'));
  const timer=setTimeout(()=>done(Error(method+' timed out')),method==='Page.captureScreenshot'?120000:30000);
  ws.addEventListener('message',message);ws.addEventListener('close',closed);ws.addEventListener('error',failed);
  ws.send(JSON.stringify({id:rid,method,params}));
 });
 const screenshot=async name=>writeFile(join(here,name+'.png'),Buffer.from((await request('Page.captureScreenshot',{format:'png'})).data,'base64'));
 let appReady=false;
 for(let i=0;i<300;i++){
  try{if(await evaluate(ws,++id,"document.querySelector('.app')!==null")){appReady=true;break;}}
  catch(error){if(!/Cannot find default execution context|Execution context was destroyed/.test(String(error)))throw error;}
  await new Promise(r=>setTimeout(r,100));
 }
 if(!appReady)throw Error('Editor application did not become ready');
 await evaluate(ws,++id,'window.__publicationConfig='+JSON.stringify(config));
 await evaluate(ws,++id,await readFile(new URL('./publication-check.js',import.meta.url),'utf8'));
 let result,phase,lastProgress=0;
 for(let i=0;i<1200;i++){
  result=await evaluate(ws,++id,'window.__publicationResult');if(result)break;
  if(Date.now()-lastProgress>15000){const progress=await evaluate(ws,++id,'window.__publicationProgress')??{phase:'app-startup'};console.log(JSON.stringify(progress));await writeFile(join(here,'progress.json'),JSON.stringify({status:'RUNNING',...progress}));lastProgress=Date.now();}
  phase=await evaluate(ws,++id,'window.__publicationPhase');if(phase&&!phase.captured){await writeFile(join(here,'progress.json'),JSON.stringify({status:'RUNNING',phase:phase.phase+'-screenshot'}));await new Promise(r=>setTimeout(r,800));await screenshot(phase.phase==='map-ready'?'map-before-insertion':'map-revealed');await evaluate(ws,++id,'window.__publicationPhase.captured=true;window.__publicationContinue=true');}
  await new Promise(r=>setTimeout(r,200));
 }
 if(result?.status!=='PASS'){await screenshot('failure');await writeFile(join(here,'result.json'),JSON.stringify(result??{status:'TIMEOUT'},null,2));throw Error(JSON.stringify(result));}
 if(!config.visual_only){
 await writeFile(join(here,'progress.json'),JSON.stringify({status:'RUNNING',phase:'saved-document-full-reload'}));
 await request('Page.reload',{});await new Promise(r=>setTimeout(r,1500));
 let restored=false;for(let i=0;i<300;i++){if(await evaluate(ws,++id,`document.querySelectorAll('.object-list li.depth-0').length===${result.savedGroups} && document.querySelectorAll('.shared-library .asset-card button[aria-label^="Add "]').length===${config.expected.assets.length}`)){restored=true;break;}await new Promise(r=>setTimeout(r,200));}
 if(!restored)throw Error('Full browser reload did not restore saved publication instances');
 result.checks.push('full page reload restores saved groups, pinned external models and all palette entries');
 await screenshot('map-after-reload');
 }
 await verifyLive();result.liveFileHashesUnchanged=Object.keys(config.protected_live_files??{}).length;
 await writeFile(join(here,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({status:result.status,groups:result.mapGroups,parts:result.mapParts,assets:result.insertedAssets?.length,visualOnly:result.visualOnly,checks:result.checks}));
}catch(error){await writeFile(join(here,'result.json'),JSON.stringify({status:'FAIL',error:String(error),stack:error.stack},null,2));throw error;}finally{ws?.close();chrome.kill('SIGTERM');await closed;await rm(profile,{recursive:true,force:true});}
