// Load a staged GLB through the real editor without changing live library files.
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdtemp, rm} from 'node:fs/promises';
import {resolve, join} from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {chromeEndpoint, socketOpen, evaluate} from '../app/tests/cdp.mjs';
import {appendSupplementalMissionParts} from '../shared/src/authored-assets.ts';

const stage = resolve(process.argv[2]);
const live = process.argv.includes('--live');
const base = process.argv.slice(3).find(arg=>!arg.startsWith('--')) || 'http://localhost:5180';
const expected = JSON.parse(await readFile(join(stage, 'asset-verification.json'), 'utf8'));
const stageUrl = live ? '/library/scenes/derby-volumes.scene.glb' : '/@fs/' + stage + '/derby.scene.glb';
let levelDocument = JSON.parse(await readFile(resolve('level-editor/library/scenes/derby.rhlos-map.json'),'utf8'));
if(!live && (levelDocument.groups.length!==expected.groups || levelDocument.objects.length!==expected.parts)){
  const publication=JSON.parse(await readFile(join(stage,'stage.json'),'utf8'));
  const plan=JSON.parse(await readFile(publication.plan,'utf8'));
  if(!plan.allow_supplemental_nodes?.length)throw new Error('Changed publication counts require explicit supplemental allowlist');
  const catalog=JSON.parse(await readFile(plan.catalog,'utf8'));
  const glb=await readFile(join(stage,'derby.scene.glb'));
  const model=JSON.parse(glb.subarray(20,20+glb.readUInt32LE(12)).toString());
  for(const group of catalog.groups)for(const part of group.parts){
    if(!plan.allow_supplemental_nodes.includes(part.node))continue;
    const node=model.nodes.find(node=>node.name===part.node);
    if(!node || node.extras?.mission_patch_profile!==part.mission_profile)throw new Error('Supplemental GLB mission ownership differs from catalog');
    part.obstacle_local_game=node.extras.obstacle_local_game;
  }
  levelDocument=appendSupplementalMissionParts(levelDocument,catalog,plan.allow_supplemental_nodes);
}
if(levelDocument.groups.length!==expected.groups || levelDocument.objects.length!==expected.parts)
  throw new Error('Document migration requires unchanged group/part counts');
if(!live){
  levelDocument.provenance.glb_sha256=createHash('sha256').update(await readFile(join(stage,'derby.scene.glb'))).digest('hex');
  await writeFile(join(stage,'derby.rhlos-map.json'),JSON.stringify(levelDocument,null,2)+'\n');
}
const profile = await mkdtemp(join(stage, 'browser-profile-'));
// Avoid booting the normal app's viewport as well as the test viewport. Two
// copies of a large map can exhaust the software WebGL renderer during startup.
const harness = new URL('/@fs/' + fileURLToPath(new URL('./verify-staged.html', import.meta.url)), base).href;
const chrome = spawn('/usr/lib/chromium/chromium', ['--headless', '--window-size=1000,1150', '--no-sandbox',
  '--disable-dev-shm-usage', '--disable-background-networking', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--remote-debugging-port=0', '--user-data-dir=' + profile, harness], {stdio:['ignore','ignore','pipe'],env:{...process.env,TMPDIR:'/tmp'}});
chrome.stderr.on('data', data=>process.stderr.write(data));
const closed = new Promise(resolve => chrome.on('close', resolve));
let ws;
try {
  const endpoint = new URL(await chromeEndpoint(chrome, {timeoutMs:15000}));
  const pages = await (await fetch('http://' + endpoint.host + '/json/list')).json();
  ws = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
  await socketOpen(ws);
  let id = 0;
  console.log('Waiting for editor page');
  for (let i=0; i<100; i++) {
    try {
      if (await evaluate(ws, ++id, `location.origin===${JSON.stringify(new URL(base).origin)} && document.readyState === "complete"`, {timeoutMs:30000})) break;
    } catch(error) {
      if(!String(error).includes('Cannot find default execution context'))throw error;
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  console.log('Loading staged map and validating runtime');
  await evaluate(ws, ++id, `window.__stageConfig=${JSON.stringify({stageUrl,documentUrl:live?'/library/scenes/derby.rhlos-map.json':'/@fs/'+stage+'/derby.rhlos-map.json',expected})}`, {timeoutMs:30000});
  const script = await readFile(new URL('./verify_staged_editor_browser.js', import.meta.url), 'utf8');
  await evaluate(ws, ++id, script, {timeoutMs:180000});
  let result;
  for (let i=0; i<180; i++) {
    result = await evaluate(ws, ++id, 'window.__stageCheck', {timeoutMs:30000});
    if (result) break;
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  await writeFile(join(stage, live?'live-browser-result.json':'browser-result.json'), JSON.stringify(result || {status:'TIMEOUT'},null,2));
  if (result?.status !== 'PASS') throw new Error(JSON.stringify(result));
  const screenshot = await new Promise((resolve,reject) => {
    const request=++id;
    const listener=event=>{const data=JSON.parse(event.data);if(data.id===request){ws.removeEventListener('message',listener);data.error?reject(data.error):resolve(data.result.data);}};
    ws.addEventListener('message',listener);
    ws.send(JSON.stringify({id:request,method:'Page.captureScreenshot',params:{format:'png'}}));
  });
  await writeFile(join(stage,live?'live-editor.png':'editor.png'),Buffer.from(screenshot,'base64'));
  for(const patch of result.patchChecks ?? []){
    await evaluate(ws,++id,`window.__stageViewport.setPatchRevealed(${JSON.stringify(patch.patch)},true)`);
    await new Promise(resolve=>setTimeout(resolve,700));
    const shot=await new Promise((resolve,reject)=>{
      const request=++id;const listener=event=>{const data=JSON.parse(event.data);if(data.id===request){ws.removeEventListener('message',listener);data.error?reject(data.error):resolve(data.result.data);}};
      ws.addEventListener('message',listener);ws.send(JSON.stringify({id:request,method:'Page.captureScreenshot',params:{format:'png'}}));
    });
    await writeFile(join(stage,(live?'live-':'')+'editor-'+patch.patch+'-revealed.png'),Buffer.from(shot,'base64'));
    await evaluate(ws,++id,`window.__stageViewport.setPatchRevealed(${JSON.stringify(patch.patch)},false)`);
  }
  console.log(JSON.stringify(result));
} finally {
  ws?.close(); chrome.kill('SIGTERM'); await closed;
  await rm(profile,{recursive:true,force:true});
}
