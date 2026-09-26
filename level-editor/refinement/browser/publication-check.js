(async()=>{
 const config=window.__publicationConfig;
 const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 const assert=(value,message)=>{if(!value)throw Error(message);};
 const wait=async(predicate,label)=>{for(let i=0;i<900;i++){if(await predicate())return;await sleep(100);}throw Error('Timeout '+label+' '+document.body.innerText);};
 const button=label=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===label);
 const click=label=>{const b=button(label);assert(b&&!b.disabled,'Button unavailable '+label);b.click();};
 const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 const opfs=await navigator.storage.getDirectory();
 const library=await opfs.getDirectoryHandle('private-'+config.map+'-publication-check',{create:true});
 window.__publicationProgress={phase:'copying-private-inputs',files:0,total:config.files.length};
 for(const item of config.files){
  const response=await fetch(item.url);assert(response.ok,'Read '+item.url);
  const bytes=await response.arrayBuffer();assert(await hash(bytes)===item.sha256,'File hash '+item.path);
  let dir=library;const parts=item.path.split('/');
  for(const part of parts.slice(0,-1))dir=await dir.getDirectoryHandle(part,{create:true});
  const file=await dir.getFileHandle(parts.at(-1),{create:true}),writer=await file.createWritable();await writer.write(bytes);await writer.close();window.__publicationProgress.files++;
 }
 // Independently inspect the same real GLBs through the production loader.
 const {prepareMapCandidate}=await import('/src/map-candidate.ts');
 const {PatchDisplay}=await import('/src/patch-display.ts');
 const {prepareProjectionAsset}=await import('/src/projection-library.ts');
 const {disposeObjectResources}=await import('/src/resources.ts');
 window.__publicationProgress={phase:'production-loader-and-state-preflight'};
 const {groundMeshes,groundTextures,generatedCounts,patchIds,patchChecks,selectionGroups}=await(async()=>{
 const candidate=await prepareMapCandidate(config.map,library,null);
 assert(candidate.document.groups.length===config.expected.groups,'Map group count');
 assert(candidate.document.objects.length===config.expected.parts,'Map part count');
 assert(candidate.ground,'Missing exported ground');
 let groundMeshes=0,groundTextures=0;candidate.ground.traverse(object=>{if(object.isMesh){groundMeshes++;for(const m of Array.isArray(object.material)?object.material:[object.material])if(m.map?.image||m.emissiveMap?.image)groundTextures++;}});
 assert(groundMeshes>0&&groundTextures>0,'Ground geometry/texture absent');
 const generated={};candidate.asset.traverse(object=>{for(const material of Array.isArray(object.material)?object.material:[object.material]){const sha=material?.userData.generated_source_sha256;if(sha)(generated[sha]??=new Set()).add(material);}});
 for(const [sha,count] of Object.entries(config.expected.generated_materials??{}))assert(generated[sha]?.size===count,'Generated material provenance '+sha);
 const patches=new Set();candidate.asset.traverse(o=>{if(o.userData.reveal_material_patch)patches.add(o.userData.reveal_material_patch);for(const k of ['reveal_hide_when_applied','reveal_show_when_applied'])for(const id of o.userData[k]??[])patches.add(id);});
 for(const id of config.expected.required_patches)assert(patches.has(id),'Required patch missing '+id);
 const display=new PatchDisplay(),patchChecks=[];
 const checkVisible=active=>{let matched=0;candidate.asset.traverse(o=>{const u=o.userData;let visible=true,governed=false;if(u.reveal_material_patch){governed=true;visible=(u.reveal_material_state==='revealed')===active.has(u.reveal_material_patch);}if(u.reveal_hide_when_applied){governed=true;visible=visible&&!u.reveal_hide_when_applied.some(p=>active.has(p));}if(u.reveal_show_when_applied){governed=true;visible=visible&&u.reveal_show_when_applied.some(p=>active.has(p));}if(governed){assert(o.visible===visible,'Patch visibility '+o.name);matched++;}});assert(matched>0||!patches.size,'No governed patch nodes');return matched;};
 const transforms=[];candidate.asset.traverse(o=>transforms.push([o,o.matrix.toArray()]));
 display.apply(candidate.asset);checkVisible(new Set());
 for(const id of patches){display.set(id,true);display.apply(candidate.asset);const nodes=checkVisible(new Set([id]));display.set(id,false);display.apply(candidate.asset);checkVisible(new Set());patchChecks.push({id,nodes,roundTrip:true});}
 for(const id of patches)display.set(id,true);display.apply(candidate.asset);checkVisible(patches);
 for(const id of patches)display.set(id,false);display.apply(candidate.asset);checkVisible(new Set());
 for(const [o,m]of transforms)assert(JSON.stringify(o.matrix.toArray())===JSON.stringify(m),'Patch preview changed geometry transform '+o.name);
 const selectionGroups=candidate.document.groups.map(group=>({id:group.id,name:group.name??group.id,parts:candidate.document.objects.filter(part=>part.group===group.id).map(part=>({id:part.id,name:part.name??part.id}))}));
 const summary={groundMeshes,groundTextures,generatedCounts:Object.fromEntries(Object.entries(generated).map(([sha,set])=>[sha,set.size])),patchIds:[...patches],patchChecks,selectionGroups};
 disposeObjectResources([candidate.asset,candidate.ground]);
 return summary;
 })();
 const patches=new Set(patchIds);
 window.__publicationProgress={phase:'actual-editor-loading'};
 window.showDirectoryPicker=async()=>library;
 await wait(()=>button('Open library…'),'app shell');click('Open library…');
 await wait(()=>document.querySelectorAll('.shared-library .asset-card button[aria-label^="Add "]').length===config.expected.assets.length,'published palette');
 await wait(()=>document.querySelectorAll('.object-list li.depth-0').length===config.expected.groups,'ActualUI map groups');
 window.__publicationPhase={phase:'map-ready',groundMeshes,groundTextures};
 await wait(()=>window.__publicationContinue,'map screenshot');
 const uiPatchLabels=[...document.querySelectorAll('.view-settings label')].filter(l=>l.textContent.includes('Reveal interior:'));
 assert(uiPatchLabels.length===patches.size,'UI exposes all patch controls');
 for(let i=0;i<uiPatchLabels.length;i++){const labels=()=>[...document.querySelectorAll('.view-settings label')].filter(l=>l.textContent.includes('Reveal interior:'));let input=labels()[i].querySelector('input');input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}));await sleep(40);assert(labels()[i].querySelector('input').checked,'UI reveal toggle');input=labels()[i].querySelector('input');input.checked=false;input.dispatchEvent(new Event('change',{bubbles:true}));await sleep(40);assert(!labels()[i].querySelector('input').checked,'UI cover toggle');}
 for(const label of [...document.querySelectorAll('.view-settings label')].filter(l=>l.textContent.includes('Reveal interior:'))){const input=label.querySelector('input');input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}));}
 window.__publicationContinue=false;window.__publicationPhase={phase:'map-revealed'};await wait(()=>window.__publicationContinue,'revealed map screenshot');
 if(config.visual_only){window.__publicationResult={status:'PASS',visualOnly:true,mapGroups:config.expected.groups,mapParts:config.expected.parts,uiPatchControls:uiPatchLabels.length,patchChecks,checks:['supplemental covered/revealed full-map visual capture; comprehensive functional checks recorded separately'],liveWrites:false};return;}
 for(const label of [...document.querySelectorAll('.view-settings label')].filter(l=>l.textContent.includes('Reveal interior:'))){const input=label.querySelector('input');input.checked=false;input.dispatchEvent(new Event('change',{bubbles:true}));}
 const selectionChecks=[];
 for(const [index,group]of selectionGroups.entries()){
  window.__publicationProgress={phase:'map-group-and-part-selection',index,total:selectionGroups.length,asset:group.id};
  let row=document.querySelectorAll('.object-list li.depth-0')[index];
  const title=`${group.name} (${group.parts.length} parts)`;
  row.click();await wait(()=>document.querySelector('.object-detail h2')?.textContent===title,'Select group '+group.id);
  row=document.querySelectorAll('.object-list li.depth-0')[index];row.querySelector('.chev-btn').click();
  const currentParts=()=>{const result=[];const current=document.querySelectorAll('.object-list li.depth-0')[index];for(let child=current.nextElementSibling;child?.classList.contains('depth-1');child=child.nextElementSibling)result.push(child);return result;};
  await wait(()=>currentParts().length===group.parts.length,'Selectable part count '+group.id);
  for(const [partIndex,part]of group.parts.entries()){
   currentParts()[partIndex].click();await wait(()=>document.querySelector('.object-detail h2')?.textContent===part.name,'Select part '+part.id);
   assert(button('Select building '+group.id),'Selected part belongs to '+group.id);
  }
  click('Select building '+group.id);await wait(()=>document.querySelector('.object-detail h2')?.textContent===title,'Return to complete group '+group.id);
  document.querySelectorAll('.object-list li.depth-0')[index].querySelector('.chev-btn').click();
  selectionChecks.push({id:group.id,parts:group.parts.map(part=>part.id),groupAndPartsSelectable:true});
 }
 const scenes=await library.getDirectoryHandle('scenes');
 const saved=async()=>JSON.parse(await(await(await scenes.getFileHandle(config.map+'.rhlos-map.json')).getFile()).text());
 const save=async()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim().startsWith('Save'));if(!b.disabled)b.click();await wait(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Save'&&b.disabled),'save');return saved();};
 const transform=async(value)=>{const row=[...document.querySelectorAll('.object-detail .meta-row')].find(row=>row.querySelector('.meta-key')?.textContent==='dx');const input=row.querySelector('input');input.value=value;input.dispatchEvent(new Event('change',{bubbles:true}));await sleep(50);};
 const inserted=[],stateChecks=[];
 for(const [index,asset]of config.expected.assets.entries()){
  window.__publicationProgress={phase:'actual-editor-asset-insertion',index,total:config.expected.assets.length,asset:asset.id};
  await wait(()=>document.querySelector(`.shared-library .asset-card button[aria-label="Add ${asset.name}"]`),'Named palette entry '+asset.id);
  const add=document.querySelector(`.shared-library .asset-card button[aria-label="Add ${asset.name}"]`);assert(add,'Named palette entry '+asset.id);
  if(asset.editor_usage==='map-background'){assert(add.disabled&&add.textContent==='Map background','Ground capability UI');continue;}
  const priorGroups=document.querySelectorAll('.object-list li.depth-0').length;
  add.click();
  await wait(()=>!add.disabled&&document.querySelectorAll('.object-list li.depth-0').length===priorGroups+1&&document.querySelector('.object-detail h2')?.textContent.startsWith(asset.name.replace(/ \(static\)$/,"")),'Add '+asset.id);
  await transform(config.expected.width+500+index*100);inserted.push(asset.id);
  const selector=[...document.querySelectorAll('.object-detail select')].find(el=>[...el.options].some(o=>o.value==='applied'));
  if(selector){selector.value='applied';selector.dispatchEvent(new Event('change',{bubbles:true}));await sleep(50);let probe=await save();let group=probe.groups.at(-1);assert(group.states.active==='applied','Applied state persisted');for(const id of group.states.initial)assert(probe.objects.find(o=>o.id===id).hidden,'Initial endpoint hidden');for(const id of group.states.applied)assert(!probe.objects.find(o=>o.id===id).hidden,'Applied endpoint visible');stateChecks.push({asset:asset.id,kind:'state-selector',applied:true});}
  if(asset.state_variant)stateChecks.push({asset:asset.id,kind:'static-variant',state:asset.state_variant});
 }
 let doc=await save();assert(doc.assetSources.length===inserted.length,'All standalone source references');
 assert(doc.groups.length===config.expected.groups+inserted.length,'All standalone groups inserted');
 const last=doc.groups.at(-1);click('Duplicate');await sleep(100);click('Undo');await sleep(100);click('Redo');await sleep(100);
 doc=await save();assert(doc.groups.length===config.expected.groups+inserted.length+1,'Duplicate undo redo');
 assert(doc.groups.at(-1).id!==last.id&&doc.groups.at(-1).transform.dx!==last.transform.dx,'Independent duplicate');
 window.__publicationResult={status:'PASS',filesHashVerified:config.files.length,mapGroups:config.expected.groups,mapParts:config.expected.parts,groundMeshes,groundTextures,
  generatedMaterials:generatedCounts,insertedAssets:inserted,savedGroups:doc.groups.length,savedParts:doc.objects.length,
  sourceReferences:doc.assetSources,patchChecks,stateChecks,selectionChecks,uiPatchControls:uiPatchLabels.length,checks:['actual Editor3D palette and map','ground geometry and image loaded','every map group and owned part selectable through actual editor controls','All standalone Add actions select named logical groups; ground cannot be inserted','independent duplicate and Undo/Redo','private OPFS save','covered/revealed visibility round-trips through production PatchDisplay and actual UI controls','initial/applied standalone variants or selectors'],liveWrites:false};
})().catch(error=>{window.__publicationResult={status:'FAIL',error:String(error),stack:error.stack};});
