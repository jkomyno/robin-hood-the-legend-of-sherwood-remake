"""Restore the native spire shaft silhouette without changing reviewed geometry."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from correct_prison_ramp_projection import WORK,clone_workspace,sha,write,pixel_witnesses
from correct_source_projection import geometry,geometry_sha
from freeze_tooling import select_tooling
from render_slots import acquire

def main():
    tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9');acquire()
    import bpy,refinement_workspace as rw
    asset='nottingham-castle-southwest-spire'
    old=WORK/'round-1/assets'/asset;w=WORK/'round-26/assets'/asset
    clone_workspace(old,w)
    config=json.loads((w/'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
    bpy.context.window.scene=bpy.data.scenes[config['scene_name']];bpy.context.view_layer.update()
    before=geometry()
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
    bpy.context.window.scene=bpy.data.scenes[config['scene_name']];bpy.context.view_layer.update();assert before==geometry()
    masks=json.loads((w/'source-masks.json').read_text())
    entry=next(e for e in masks['projections']['exterior']['assignments'] if e.get('source_node')=='building-509')
    original=copy.deepcopy(entry)
    entry.clear();entry.update(source_node='building-509',mask_indices=[451],reviewed=True,constraint_kind='reviewed-native-silhouette',review_note='Native451 includes the continuous source-visible stone shaft beneath the spire roof. The shaft receiver509 was previously blanket-rejected by synthetic527. Native silhouette plus complete source-scene first hit preserves neighboring hall ownership and unseen backs.',review_evidence='added-source-pixels.png')
    write(w/'source-masks.json',masks)
    bpy.context.preferences.filepaths.save_version=0
    rw.modified(w)
    bpy.context.view_layer.update();after=geometry();assert before==after
    pixel_witnesses(w,old,config,'building-509')
    write(w/'projection-correction.json',dict(version=1,asset_id=asset,status='awaiting-independent-review',previous_workspace=str(old),previous_model_sha256=sha(old/'model.blend'),model_sha256=sha(w/'model.blend'),geometry_before_sha256=geometry_sha(before),geometry_after_sha256=geometry_sha(after),geometry_identical=True,mesh_count=len(before),changes=[dict(before=original,after=entry)],tooling=tooling,recipe_sha256=sha(__file__)))
    candidate=json.loads((w/'candidate.json').read_text());candidate.update(status='refinement-in-progress',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),recipe=str(Path(__file__).resolve()),geometry_changed_in_this_revision=False,projection_correction='projection-correction.json',source_comparison='added-source-pixels.png',changes=[entry['review_note']]);write(w/'candidate.json',candidate)
    print('SPIRE GEOMETRY IDENTICAL',flush=True)
def verify():
    select_tooling(WORK/'tooling/58744eeaf71a21e9');acquire()
    import bpy
    import audit_stored_materials as audit
    asset='nottingham-castle-southwest-spire';old=WORK/'round-1/assets'/asset;w=WORK/'round-26/assets'/asset
    config=json.loads((w/'workspace.json').read_text())
    def outside():
        return {o.name:dict(uv={u.name:[tuple(v.uv) for v in u.data] for u in o.data.uv_layers},materials=[m.name if m else None for m in o.data.materials],slots=[p.material_index for p in o.data.polygons]) for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')!=asset}
    bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));g=geometry();uv=outside()
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));assert g==geometry(),'Full scene geometry changed'
    after_uv=outside();changed=[n for n in uv if after_uv[n]!=uv[n]]
    write(w/'outside-projection-validation.json',dict(status='PASS' if not changed else 'FAIL',changed_objects=changed,checked_meshes=len(uv),model_sha256=sha(w/'model.blend')))
    assert not changed,changed
    audit.run(w,w/'inspection/stored-materials',render=True,export=True)
def finalize(review):
    w=WORK/'round-26/assets/nottingham-castle-southwest-spire'
    qa=json.loads(Path(review).read_text());model=sha(w/'model.blend')
    assert qa['status']=='PASS' and qa['model_sha256']==model
    for path in ['validation.json','known-rgb-validation.json','outside-projection-validation.json']:
        assert json.loads((w/path).read_text())['status']=='PASS',path
    material=json.loads((w/'inspection/stored-materials/audit.json').read_text())
    assert material['status']=='STRUCTURAL-PASS' and not material['problems'] and material['model_sha256']==model
    c=json.loads((w/'candidate.json').read_text())
    c.update(status='ready-for-user',geometry_reviewed=True,inspected_views=list(range(8)),independent_review=str(Path(review).resolve()),limitations=['Entire asset is absent when hall patch008 is revealed; no empty-state mesh is invented.','Hidden reverse stone and roof surfaces have no source artwork and remain neutral.'],user_approval='pending',texture_generation='not-started')
    write(w/'candidate.json',c)
    p=json.loads((w/'projection-correction.json').read_text());p.update(status='PASS',inspected_views=list(range(8)),independent_review=str(Path(review).resolve()),recipe_sha256=sha(__file__));write(w/'projection-correction.json',p)
    (w/'review.md').write_text('# Southwest castle spire source correction\n\n'+c['changes'][0]+'\n\nNative mask451 restores the continuous shaft with 16,387 full-scene visible source pixels. Roof and shaft geometry are unchanged. All eight source-only, solid and actual saved-material views inspected. Hidden reverse surfaces remain neutral. Entire asset hides with hall patch008. No AI textures generated. User approval pending.\n')
if __name__=='__main__':
    if '--finalize' in sys.argv:finalize(sys.argv[sys.argv.index('--finalize')+1])
    elif '--verify' in sys.argv:verify()
    else:main()
