"""Project the centered gate and its exact transferred neighboring jamb."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from PIL import Image,ImageDraw,ImageChops
 from refinement_workspace import prepare,modified
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 from audit_stored_materials import run
 raw=WORK/'round-39/assets/nottingham-castle-gate-east-tower';tower=WORK/'round-40/assets/nottingham-castle-gate-east-tower';baseline=WORK/'round-23/assets/nottingham-castle-gate-east-tower'
 if '--finish' in sys.argv:
  (tower/'inspection').mkdir(exist_ok=True);restore_foreign_uv_schema(tower);run(tower,tower/'inspection/stored-materials',render=True,export=False);(tower/'inspection/jamb-transfer.json').write_text((raw/'inspection/jamb-transfer.json').read_text());return
 scope=raw/'inspection/jamb-occluder';scope.mkdir(exist_ok=True);mask=scope/'source-masks.json';m=json.loads((baseline/'source-masks.json').read_text());old=Path(m['mask_inventory']);inventory=json.loads(old.read_text())
 r=next(r for r in inventory['masks']if r['index']==375);native=Image.new('L',(2304,3520));native.paste(Image.open(old.parent/r['png']).convert('L'),r['box_top_left']);domain=Image.new('L',native.size);ImageDraw.Draw(domain).polygon([(966,1414),(980,1427),(981,1488),(966,1477)],fill=255);domain=ImageChops.darker(domain,native)
 complement=ImageChops.invert(domain);complement.save(scope/'outside-measured-native375-jamb.png')
 for r in inventory['masks']:
  r['png']=str((old.parent/r['png']).resolve());r['box_top_left']=r['box_top_left'][:2]
 i=max(r['index']for r in inventory['masks'])+1;inventory['masks'].append(dict(index=i,layer=-1,layer_index=-1,png='outside-measured-native375-jamb.png',box_top_left=[0,0],box_size=list(domain.size),mask_type='reviewed-foreign-occluder',description='Complement of measured four-corner jamb intersected with native375. Only archived foreign proxies may be ignored in this exact domain for337.'))
 (scope/'manifest.json').write_text(json.dumps(inventory,indent=2)+'\n');m['mask_inventory']=str(scope/'manifest.json')
 for node in [333,348,366,340]:
  m['projections']['exterior'].setdefault('occluder_constraints',[]).append(dict(reviewed=True,source_node=f'building-{node}',receiver_nodes=['building-337'],mask_indices=[i],reason='Measured native375 jamb belongs337. The exact previous333 volume was transferred; archived oldgate and backgroundproxy hits must not suppress this source-visible transferred surface.',review_evidence=str(raw/'inspection/jamb-transfer.json')))
 mask.write_text(json.dumps(m,indent=2)+'\n')
 if not tower.exists():
  bpy.ops.wm.open_mainfile(filepath=str(baseline/'model.blend'));c=json.loads((baseline/'workspace.json').read_text())
  prepare(tower,asset_id=tower.name,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=baseline/'reference/source.png',grouping_manifest=baseline/'reference/grouping.json',inventory_path=baseline/'reference/inventory.json',review_path=baseline/'reference/grouping-review.json',projection_manifest=baseline/'projection-layers.json',source_mask_manifest=mask,width=320,height=400,context_padding=35,framing_padding=c['framing_padding'])
 else:bpy.ops.wm.open_mainfile(filepath=str(tower/'baseline.blend'))
 target_name=json.loads((raw/'inspection/jamb-transfer.json').read_text())['tower_changed_object'];target=bpy.data.objects[target_name]
 with bpy.data.libraries.load(str(raw/'model.blend'),link=False) as(a,b):b.objects=[target_name]
 obj=b.objects[0];target.data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(tower/'model.blend'))
 modified(tower);(tower/'inspection').mkdir(exist_ok=True);restore_foreign_uv_schema(tower);run(tower,tower/'inspection/stored-materials',render=True,export=False)
 (tower/'inspection/jamb-transfer.json').write_text((raw/'inspection/jamb-transfer.json').read_text())
 print('PAIR_PROJECTION_COMPLETE',tower.name,hashlib.sha256((tower/'model.blend').read_bytes()).hexdigest(),flush=True)
if __name__=='__main__':main()
