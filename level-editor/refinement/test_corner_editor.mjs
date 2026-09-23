// Browser acceptance against an isolated copy of a real review project.
import {spawn} from 'node:child_process';
import {mkdtemp,copyFile,readFile,writeFile,rm} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {chromeEndpoint,socketOpen,evaluate} from '../app/tests/cdp.mjs';
const project=resolve(process.argv[2]);
const dir=await mkdtemp(join(resolve('level-editor/work'),'corner-editor-test-'));
await copyFile(project,join(dir,'project.json'));
const server=spawn('python3',['level-editor/refinement/corner_editor.py',join(dir,'project.json'),'--port','5183'],{stdio:['ignore','pipe','pipe']});
await new Promise((ok,no)=>{server.stdout.once('data',ok);server.once('exit',()=>no(Error('Test server failed')))});
const chrome=spawn('/usr/lib/chromium/chromium',['--headless','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--window-size=1500,1050','--remote-debugging-port=0','--user-data-dir='+join(dir,'chrome'),'http://localhost:5183/'],{stdio:['ignore','ignore','pipe'],env:{...process.env,TMPDIR:'/tmp'}});
chrome.stderr.on('data',data=>process.stderr.write(data));
let ws,id=0;const closed=new Promise(r=>chrome.once('close',r));
try{
 const ep=new URL(await chromeEndpoint(chrome));const pages=await(await fetch('http://'+ep.host+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await socketOpen(ws);
 for(let i=0;i<100;i++){if(await evaluate(ws,++id,"document.querySelector('#status')?.textContent.startsWith('Ready.')"))break;await new Promise(r=>setTimeout(r,100))}
 await new Promise(r=>setTimeout(r,700));
 const result=await evaluate(ws,++id,`(()=>{
 const $=id=>document.getElementById(id),assert=(x,m)=>{if(!x)throw Error(m)};
 assert($('asset').options.length===2,'Both walls loaded');
 const before=$('paths').children.length;
 $('new').click();assert($('paths').children.length===before+1,'New zigzag');
 const c=$('canvas'),r=c.getBoundingClientRect();
 // Use genuine CDP pointer input below; this portion checks coordinate controls/history.
 window.testRect={x:r.x,y:r.y,width:r.width,height:r.height};
 return {before,rect:window.testRect};
 })()`);
 async function command(method,params){return new Promise((ok,no)=>{const n=++id;const handler=e=>{const m=JSON.parse(e.data);if(m.id===n){ws.removeEventListener('message',handler);m.error?no(Error(JSON.stringify(m.error))):ok(m.result)}};ws.addEventListener('message',handler);ws.send(JSON.stringify({id:n,method,params}))})}
 const {rect}=result;const x=rect.x+rect.width*.4,y=rect.y+rect.height*.4;
 async function click(x,y,modifiers=0){await command('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',clickCount:1,modifiers});await command('Input.dispatchMouseEvent',{type:'mouseReleased',x,y,button:'left',clickCount:1,modifiers})}
 await click(x,y);await click(x+70,y+70);
 await command('Input.dispatchMouseEvent',{type:'mousePressed',x:x+70,y:y+70,button:'left',clickCount:1});
 await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:x+100,y:y+90,buttons:1});
 await command('Input.dispatchMouseEvent',{type:'mouseReleased',x:x+100,y:y+90,button:'left',clickCount:1});
 await click(x+50,y+45,8); // Shift inserts on the moved segment.
 await evaluate(ws,++id,`(()=>{const $=id=>document.getElementById(id),assert=(v,m)=>{if(!v)throw Error(m)};assert($('paths').lastChild.textContent.includes('3 corners'),'Draw, drag and insert');$('undo').click();assert($('paths').lastChild.textContent.includes('2 corners'),'Undo insert');$('redo').click();assert($('paths').lastChild.textContent.includes('3 corners'),'Redo insert');$('x').value=123;$('x').dispatchEvent(new Event('change'));$('save').click()})()`);
 for(let i=0;i<100;i++){if(await evaluate(ws,++id,"document.getElementById('status').textContent.startsWith('Saved to')"))break;await new Promise(r=>setTimeout(r,100))}
 const saved=JSON.parse(await readFile(join(dir,'edited-corners.json'),'utf8'));
 if(saved.assets[0].paths.at(-1).points[1][0]!==123)throw Error('Saved pixel coordinate mismatch');
 await evaluate(ws,++id,'location.reload()');await new Promise(r=>setTimeout(r,1200));
 await evaluate(ws,++id,`(()=>{const $=id=>document.getElementById(id);if(!$('paths').lastChild.textContent.includes('3 corners'))throw Error('Reload persistence');$('asset').value=1;$('asset').dispatchEvent(new Event('change'));$('mesh').click()})()`);
 await new Promise(r=>setTimeout(r,500));
 const screenshot=await command('Page.captureScreenshot',{format:'png'});
 await writeFile(join(resolve('level-editor/work'),'battlement-editor-test.png'),Buffer.from(screenshot.data,'base64'));
 console.log('PASS: both assets; draw; drag; insert; undo/redo; exact coordinate save; reload persistence; mesh overlay.');
}finally{ws?.close();chrome.kill('SIGTERM');server.kill('SIGTERM');await closed;await rm(dir,{recursive:true,force:true})}
