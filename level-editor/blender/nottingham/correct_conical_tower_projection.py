"""Recover the conical tower shaft without altering approved geometry."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from correct_prison_ramp_projection import clone_workspace,sha,write,pixel_witnesses
from correct_source_projection import geometry,geometry_sha
from freeze_tooling import select_tooling
from render_slots import acquire

def main():
 acquire();tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,refinement_workspace as rw
 old=WORK/'round-1/assets/nottingham-castle-west-conical-tower';w=WORK/'round-26/assets/nottingham-castle-west-conical-tower';clone_workspace(old,w)
 c=json.loads((w/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update();before=geometry();bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();assert before==geometry()
 m=json.loads((w/'source-masks.json').read_text());changes=[]
 for entry in m['projections']['exterior']['assignments']:
  if entry['source_node'] not in c['part_ids']:continue
  node=entry['source_node'];previous=entry.copy();entry.clear();entry.update(source_node=node,reviewed=True,mask_indices=[435],exclude_mask_indices=[428],exclusions_reviewed=True,exclusion_reason='Native428 owns the foreground stair turret and exposed flight, not the rear conical tower.',constraint_kind='reviewed-native-silhouette',review_evidence=str(WORK/'castle-audit/review5-towers/conical-mask.png'),review_note='Native435 contains the complete source-visible rear conical tower shaft; upper-only436 incorrectly cut its visible lower masonry. Subtract foreground stair428 and retain full-scene first-hit visibility for the neighboring turret, stair and hall.');changes.append(dict(before=previous,after=entry.copy()))
 write(w/'source-masks.json',m);bpy.context.preferences.filepaths.save_version=0;rw.modified(w);bpy.context.view_layer.update();after=geometry();assert before==after
 pixel_witnesses(w,old,c,'building-491');(w/'added-source-pixels.png').rename(w/'added-shaft491.png');(w/'added-source-pixels.json').rename(w/'added-shaft491.json');pixel_witnesses(w,old,c,'building-492')
 report=dict(version=1,status='awaiting-independent-review',asset_id=c['asset_id'],previous_workspace=str(old),approved_model_sha256=sha(old/'model.blend'),previous_model_sha256=sha(old/'model.blend'),model_sha256=sha(w/'model.blend'),geometry_before_sha256=geometry_sha(before),geometry_after_sha256=geometry_sha(after),geometry_identical=True,changes=changes,tooling=tooling,recipe_sha256=sha(__file__))
 write(w/'projection-correction.json',report);candidate=json.loads((w/'candidate.json').read_text());candidate.update(status='refinement-in-progress',inspected_views=[],geometry_reviewed=False,model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),recipe=str(Path(__file__).resolve()),projection_correction='projection-correction.json',geometry_changed_in_this_revision=False,source_comparison='added-source-pixels.png',changes=['Restored the visible lower tower shaft excluded by the upper-only mask; preserved exact approved geometry.'],limitations=['Back faces and parts concealed by the foreground stair turret and adjoining castle remain neutral.'],texture_generation='not-started');write(w/'candidate.json',candidate)
def verify():
    select_tooling(WORK/'tooling/58744eeaf71a21e9');acquire()
    import bpy
    import audit_stored_materials as audit
    asset='nottingham-castle-west-conical-tower';old=WORK/'round-1/assets'/asset;w=WORK/'round-26/assets'/asset
    config=json.loads((w/'workspace.json').read_text())
    def outside():
        return {o.name:dict(uv={u.name:[tuple(v.uv) for v in u.data] for u in o.data.uv_layers},materials=[m.name if m else None for m in o.data.materials],slots=[p.material_index for p in o.data.polygons]) for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')!=asset}
    bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));g=geometry();uv=outside()
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));assert g==geometry(),'Full scene geometry changed'
    after_uv=outside();changed=[n for n in uv if after_uv[n]!=uv[n]]
    write(w/'outside-projection-validation.json',dict(status='PASS' if not changed else 'FAIL',changed_objects=changed,checked_meshes=len(uv),model_sha256=sha(w/'model.blend')))
    assert not changed,changed
    audit.run(w,w/'inspection/stored-materials-export',render=True,export=True)

if __name__=='__main__':
 if '--verify' in sys.argv:verify()
 else:main()

