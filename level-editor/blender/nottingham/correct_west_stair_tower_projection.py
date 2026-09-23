"""Restore the source-visible masonry of the western castle stair turret."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from correct_prison_ramp_projection import clone_workspace,pixel_witnesses,sha,write
from correct_source_projection import geometry,geometry_sha
from freeze_tooling import select_tooling
from render_slots import acquire

def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,refinement_workspace as rw
 old=WORK/'round-1/assets/nottingham-castle-west-stair-tower';w=WORK/'round-26/assets/nottingham-castle-west-stair-tower';clone_workspace(old,w)
 c=json.loads((w/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));before=geometry();bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
 m=json.loads((w/'source-masks.json').read_text())
 for entry in m['projections']['exterior']['assignments']:
  if entry['source_node'] not in c['part_ids']:continue
  node=entry['source_node'];entry.clear();entry.update(source_node=node,reviewed=True,mask_indices=[428,435] if node=='building-487' else [428],constraint_kind='reviewed-native-silhouette',review_evidence=str(w/'inspection'),review_note='Native428 contains the stair and its surrounding turret shaft. Previously only stair487 accepted this native silhouette, while the five supporting masonry receivers rejected all source pixels. Upper stair487 additionally uses native435, which owns the four source-visible treads above native428. Full-scene first-hit and facing tests retain neighboring architecture occlusion.')
 write(w/'source-masks.json',m);bpy.context.preferences.filepaths.save_version=0;rw.modified(w)
 assert before==geometry(),'Geometry changed'
 (w/'inspection').mkdir(exist_ok=True)
 for node in c['part_ids']:
  pixel_witnesses(w,old,c,node)
  for ext in ['json','png']:(w/f'added-source-pixels.{ext}').rename(w/f'inspection/{node}-added-source-pixels.{ext}')
 write(w/'projection-correction.json',dict(status='awaiting-independent-review',previous_model_sha256=sha(old/'model.blend'),model_sha256=sha(w/'model.blend'),geometry_before_sha256=geometry_sha(before),geometry_after_sha256=geometry_sha(geometry()),geometry_identical=True,recipe_sha256=sha(__file__)))
 make_evidence(w,old)
 candidate=json.loads((w/'candidate.json').read_text());candidate.update(status='refinement-in-progress',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),recipe=str(Path(__file__).resolve()),geometry_refined=False,geometry_changed_in_this_revision=False,no_change_reason='Native source ownership correction only; all vertices, faces and transforms preserved.',changes=['Restored native428 source ownership to the turret masonry receivers485/486/496/497/498.'],limitations=['Source-concealed and reverse surfaces remain gray.'],user_approval='pending',texture_generation='not-started',source_comparison='inspection/source-comparison.png',source_trace='inspection/source-native428.png');write(w/'candidate.json',candidate)
def make_evidence(w,old):
 from PIL import Image,ImageDraw
 source=Image.open(WORK/'source-states/covered.png').convert('RGB');inventory=WORK/'mask-review/inventory-v11';m=json.loads((inventory/'manifest.json').read_text())['masks'][428]
 mask=Image.new('L',source.size);mask.paste(Image.open(inventory/m['png']).convert('L'),m['box_top_left']);box=(120,820,370,1640)
 native=Image.composite(source,Image.new('RGB',source.size,'#555555'),mask);sheet=Image.new('RGB',(500,850),'white');sheet.paste(source.crop(box),(0,30));sheet.paste(native.crop(box),(250,30));d=ImageDraw.Draw(sheet);d.text((5,7),'Untouched source artwork',fill='black');d.text((255,7),'Native428 source ownership',fill='black');sheet.save(w/'inspection/source-native428.png')
 sheet=Image.new('RGB',(768,510),'white');d=ImageDraw.Draw(sheet)
 for i,(folder,label)in enumerate([(old,'Before: masonry rejected all source pixels'),(w,'After: native428 masonry restored')]):
  im=Image.open(folder/'modified/textured.png').crop((0,0,256,320)).resize((384,480));sheet.paste(im,(i*384,30));d.text((i*384+6,7),label,fill='black')
 sheet.save(w/'inspection/source-comparison.png')

def verify():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 asset='nottingham-castle-west-stair-tower';old=WORK/'round-1/assets'/asset;w=WORK/'round-26/assets'/asset
 def outside():
  return {o.name:dict(uv={u.name:[tuple(v.uv) for v in u.data] for u in o.data.uv_layers},materials=[m.name if m else None for m in o.data.materials],slots=[p.material_index for p in o.data.polygons]) for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')!=asset}
 bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));g=geometry();uv=outside()
 bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));assert g==geometry(),'Full scene geometry changed'
 after=outside();assert set(uv)==set(after),'Outside mesh inventory changed'
 changed=[n for n in uv if after[n]!=uv[n]]
 report=dict(status='PASS' if not changed else 'FAIL',changed_objects=changed,checked_meshes=len(uv),model_sha256=sha(w/'model.blend'),previous_model_sha256=sha(old/'model.blend'),geometry_identical=True)
 write(w/'outside-projection-validation.json',report);assert not changed,changed;print(report,flush=True)

def audit():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 from audit_stored_materials import run
 w=WORK/'round-26/assets/nottingham-castle-west-stair-tower'
 print(run(w,w/'inspection/stored-materials-final',render=True,export=True))
if __name__=='__main__':
 if '--verify' in sys.argv:verify()
 elif '--audit' in sys.argv:audit()
 else:main()
