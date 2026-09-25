"""Verify terrain coverage from its explicit UV-atlas generation contract."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'level-editor/refinement/blender'),str(ROOT/'level-editor/refinement')]
import bpy,numpy as np
from PIL import Image
from planar_texture_guards import validate_fill
from render_slots import acquire,release
from render_texture_coverage import inspect
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 w=ROOT/'level-editor/work/nottingham-refinement/texture-generation/nottingham-terrain-ground-uv-atlas-v1';b=w/'bake-uv-v1';out=ROOT/'level-editor/work/nottingham-refinement/coordinator-audit/final-texture-coverage/terrain-uv';out.mkdir(exist_ok=True)
 prep=json.loads((w/'preparation.json').read_text());v=json.loads((b/'validation.json').read_text());ev=json.loads((b/'uv-evidence.json').read_text());old=json.loads((w/'uv-evidence.json').read_text());manifest=json.loads((w/'views.json').read_text())
 for name,digest in prep['files'].items():assert sha(w/name)==digest,name
 assert sha(w/'preparation.json')==v['preparation_sha256'];assert sha(b/'uv-evidence.json')==v['baked_uv_evidence_sha256'];assert sha(b/'worker.blend')==v['baked_model_sha256']==ev['model_sha256'];assert sha(b/'atlas.png')==v['generated_sha256']==ev['atlas_sha256'];assert ev['geometry_uv_matrix_sha256']==old['geometry_uv_matrix_sha256']
 original=np.asarray(Image.open(w/'input.png').convert('RGBA'));generated=np.asarray(Image.open(b/'atlas.png').convert('RGBA'));mask=np.asarray(Image.open(w/'mask.png').convert('RGBA'));surface=np.asarray(Image.open(w/'surface.png').convert('L'))>0;known=np.asarray(Image.open(w/'known.png').convert('L'))>127
 count=validate_fill(original,generated,mask,surface);editable=mask[:,:,3]<128
 assert count==v['editable_pixels']==prep['editable_pixels'];assert np.array_equal(known,surface&~editable);assert int(known.sum())==prep['known_pixels']
 bpy.ops.wm.open_mainfile(filepath=str(b/'worker.blend'));obj=bpy.data.objects[ev['receiver']];material=obj.data.materials[ev['material_slot']];nodes=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE'and n.image];assert len(nodes)==1;image=nodes[0].image;packed=hashlib.sha256(image.packed_file.data).hexdigest();assert packed==sha(b/'atlas.png');assert hashlib.sha256(np.asarray(image.pixels[:],np.float32).tobytes()).hexdigest()==ev['packed_pixel_sha256'];uv=[list(x.uv)for x in obj.data.uv_layers[ev['uv_layer']].data];assert uv==ev['geometry']['uv'][ev['uv_layer']]
 ownership=np.zeros(surface.shape,np.uint8);ownership[known]=1;ownership[editable]=2;ownership=ownership[::-1].copy();path=out/'ownership.npz';np.savez_compressed(path,ownership=ownership)
 proof=dict(path=str(path),sha256=sha(path),packed_image_sha256=packed,uv_sha256=hashlib.sha256(json.dumps(uv).encode()).hexdigest());report=dict(status='PASS',asset_id=v['asset_id'],model_sha256=v['baked_model_sha256'],validation_sha256=sha(b/'validation.json'),preparation_sha256=sha(w/'preparation.json'),known_pixels=int(known.sum()),generated_pixels=int(editable.sum()),unfilled_surface_pixels=int(np.sum(surface&~known&~editable)),objects=[dict(object=obj.name,texel_provenance=proof)],method='Explicit protected-source and editable generation masks, exact generated PNG and saved packed-image equality, actual saved UV equality, protected RGBA preservation. No physical texture alpha is used to infer provenance.')
 evidence=out/'provenance.json';evidence.write_text(json.dumps(report,indent=2)+'\n')
 frames=b/'qa-views.json';f=json.loads(frames.read_text());reviewed=Path(manifest['reviewed_packet'])/'views.json';assert sha(reviewed)==manifest['reviewed_manifest_sha256']==v['frame_manifest_sha256'];originalframes=json.loads(reviewed.read_text())
 for actual,expected in zip(f['views'],originalframes['views']):
  for key in expected:
   if key!='crop':assert actual[key]==expected[key],key
 acquire()
 try:inspect(frames,b,out/'coverage',provenance_reports=[evidence])
 finally:release()
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
