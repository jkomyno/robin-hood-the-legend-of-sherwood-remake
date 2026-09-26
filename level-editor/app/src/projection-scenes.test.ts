import test from 'node:test';
import assert from 'node:assert/strict';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { selectGlbScene } from '@rle/shared';
function glb(names=['closed','open']) {
 const json={asset:{version:'2.0'},scene:0,scenes:names.map((name,i)=>({name,nodes:[i]})),nodes:names.map(()=>({name:'building-000',mesh:0})),meshes:[{primitives:[{attributes:{POSITION:0}}]}],accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[0,0,0],max:[1,1,0]}],bufferViews:[{buffer:0,byteLength:36}],buffers:[{byteLength:36}]};
 const encoded=new TextEncoder().encode(JSON.stringify(json)), size=Math.ceil(encoded.length/4)*4;
 const bytes=new ArrayBuffer(28+size+36),view=new DataView(bytes),raw=new Uint8Array(bytes);
 view.setUint32(0,0x46546c67,true);view.setUint32(4,2,true);view.setUint32(8,bytes.byteLength,true);view.setUint32(12,size,true);view.setUint32(16,0x4e4f534a,true);raw.fill(32,20,20+size);raw.set(encoded,20);view.setUint32(20+size,36,true);view.setUint32(24+size,0x004e4942,true);raw.set(new Uint8Array(new Float32Array([0,0,0,1,0,0,0,1,0]).buffer),28+size);return bytes;
}
test('one selected state is parsed; shared BIN and node indices remain intact',async()=>{
 const bytes=glb();assert.equal(selectGlbScene(bytes),bytes);
 for(const name of ['closed','open']){const selected=selectGlbScene(bytes,name);assert.deepEqual(new Uint8Array(selected).slice(-36),new Uint8Array(bytes).slice(-36));const result=await new GLTFLoader().parseAsync(selected,'');assert.equal(result.scenes.length,1);assert.equal(result.scene.name,name);assert.equal(result.scene.children.length,1);assert.equal(result.parser.json.nodes[result.parser.associations.get(result.scene.children[0]!)!.nodes!].name,'building-000');}
});
test('missing, duplicate, blank selectors and corrupt files reject',()=>{
 assert.throws(()=>selectGlbScene(glb(),'missing'),/exactly once/);assert.throws(()=>selectGlbScene(glb(['open','open']),'open'),/exactly once/);assert.throws(()=>selectGlbScene(glb(),' '),/selector/);assert.throws(()=>selectGlbScene(new ArrayBuffer(3),'open'),/header/);
});
