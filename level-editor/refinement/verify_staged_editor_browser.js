(async () => {
  const {stageUrl,documentUrl,expected} = window.__stageConfig;
  const {prepareMapCandidate} = await import('/src/map-candidate.ts');
  const {EditorViewport} = await import('/src/editor-viewport.ts');
  const files=['derby-volumes.scene.json','derby-volumes.scene.glb','derby.level3d.json'];
  const directory={async getDirectoryHandle(){return this;},async getFileHandle(name){
    if(!files.includes(name))throw new DOMException(name,'NotFoundError');
    const url=name.endsWith('.glb')?stageUrl:name.endsWith('.level3d.json')?documentUrl:'/library/scenes/'+name;
    const response=await fetch(url+'?stage-check='+Date.now());
    if(!response.ok)throw Error('HTTP '+response.status+' '+url);
    const file=new File([await response.arrayBuffer()],name);
    return {getFile:async()=>file};
  },async *entries(){for(const name of files)yield [name,{kind:'file'}];}};
  const candidate=await prepareMapCandidate('derby',directory,null);
  if(candidate.document.groups.length!==expected.groups||candidate.sources.size!==expected.parts)
    throw Error('Catalog group/part count mismatch');
  const generated={};let meshCount=0;
  candidate.asset.traverse(object=>{
    if(object.isMesh)meshCount++;
    for(const material of (Array.isArray(object.material)?object.material:[object.material])){
      const sha=material?.userData.generated_source_sha256;
      if(sha)(generated[sha]??=new Set()).add(material);
    }
  });
  for(const [sha,count] of Object.entries(expected.generated_materials))
    if(generated[sha]?.size!==count)throw Error('Generated texture provenance/count mismatch '+sha);
  let selection=null;
  const viewport=new EditorViewport({document:()=>candidate.document,selection:()=>selection,level:()=>null,
    showObstacles:()=>false,showElevation:()=>false,onSelection:value=>selection=value,commitTransform:()=>{}});
  document.body.innerHTML='<div id="stage-view" style="width:950px;height:1050px"></div>';
  viewport.setup(document.querySelector('#stage-view'));
  viewport.replaceMap(candidate.asset,candidate.ground,candidate.sources);
  viewport.syncViews(candidate.document);viewport.gameCamera(true);viewport.scene.updateMatrixWorld(true);
  await new Promise(resolve=>setTimeout(resolve,1000));
  const box=viewport.renderer.domElement.getBoundingClientRect();
  const target={clientX:box.left+box.width*.47,clientY:box.top+box.height*.37};
  viewport.pick(target,false);const first=selection;
  if(first?.kind!=='group')throw Error('First click did not select logical group');
  viewport.pick(target,false);
  if(selection?.kind!=='part')throw Error('Second click did not select part');
  const part=candidate.document.objects.find(object=>object.id===selection.id);
  if(part.group!==first.id)throw Error('Second click escaped selected group');
  viewport.select(null);
  window.__stageViewport=viewport;
  window.__stageCheck={status:'PASS',groups:candidate.document.groups.length,parts:candidate.sources.size,meshCount,
    generatedMaterials:Object.fromEntries(Object.entries(generated).map(([sha,materials])=>[sha,materials.size])),
    firstClick:first,secondClick:part.id,stagedGlb:stageUrl,liveFilesModified:false};
})().catch(error=>window.__stageCheck={status:'FAIL',error:String(error),stack:error.stack});
