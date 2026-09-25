"""Replace the forge roof's false front gable with an artwork-supported hip.

This writes a separate geometry candidate requiring renewed user review.
"""
import json,sys,hashlib,math,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-village-small-hut'
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 from render_slots import acquire
 acquire(slots=2)
 import bpy
 import refinement_workspace as rw
 from mathutils import Vector
 from refine_village_secondary import replace,digest
 old=WORK/'round-23/assets'/ASSET;out=WORK/'texture-generation/projection-corrections/v7'/ASSET
 c=json.loads((old/'workspace.json').read_text())
 if not out.exists():
  from small_hut_eave_ownership import apply as review_eave
  authority=WORK/'mask-review/hut-eave-v7';authority.mkdir(parents=True,exist_ok=True)
  prepared_masks=review_eave(authority,json.loads((old/'source-masks.json').read_text()),old/'reference/source.png')
  authored=authority/'source-masks.json';authored.write_text(json.dumps(prepared_masks,indent=2)+'\n')
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(out,asset_id=ASSET,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=authored,width=c['width'],height=c['height'],context_padding=c['context_padding'],framing_padding=c['framing_padding'],lighting=json.loads((WORK/'lighting-calibration/map-lighting.json').read_text())['lighting'])
 bpy.ops.wm.open_mainfile(filepath=str(out/'baseline.blend'));bpy.context.view_layer.update()
 before={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH'}
 objects={o.get('source_node'):o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==ASSET}
 a=objects['building-282'];b=objects['building-283']
 av=[a.matrix_world@v.co for v in a.data.vertices];bv=[b.matrix_world@v.co for v in b.data.vertices]
 av[16].x+=2;av[16].z+=.5
 bv[19].x-=1.5;bv[19].z+=.8
 q=(av[17]+bv[17])*.5
 ridge_front=(av[18]+bv[16])*.5
 p=ridge_front.lerp(q,.43)
 p.z+=8.5
 # Fit the two outer eave runs and retain the front lower roof tip. The front hip
 # rises to the observed thatch/chimney junction, hidden partly by the hood.
 e=Vector((ridge_front.x,ridge_front.y,45.2));base=44.5
 reports=[]
 for obj,front,rear in [(a,av[19],av[16]),(b,bv[19],bv[18])]:
  top=[e,front,rear,q,p]
  bottom=[Vector((v.x,v.y,base))for v in top[:4]]
  vertices=bottom+top
  faces=[(0,3,2,1),(4,5,8),(5,6,7,8),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,8,7)]
  reports.append(replace(obj,vertices,faces,'Forge roof / source-fitted front hip'))
 from small_hut_source_structure import repair
 reports.extend(repair(objects))
 changed=[name for name,v in before.items()if digest(bpy.data.objects[name])!=v]
 assert set(changed)=={a.name,b.name,objects["building-284"].name,objects["building-281"].name},changed
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
 def project(v):return [v.x,-v.y*math.sin(math.radians(35))-v.z*math.cos(math.radians(35))]
 report=dict(version=1,asset_id=ASSET,status='prototype-awaiting-independent-source-review',geometry_approval='pending-new-user-review',previous_workspace=str(old),previous_model_sha256=sha(old/'model.blend'),model_sha256=sha(out/'model.blend'),changed_objects=changed,outside_objects_preserved=len(before)-4,components=reports,source_hip_junction=project(p),source_hip_junction_observation=None,concealed_ridge_lift_world=dict(front=8.5,rear=0),source_visible_left_contour=[[355,2840],[380,2813],[394,2799]],source_uncertainty_pixels=3,source_eaves=[project(x)for x in [av[19],av[16],bv[19],bv[18]]],changes=['Replaced the false front gable with a sloping front hip; concealed ridge starts behind the chimney hood.','Raised only the concealed front ridge by 8.5 world units; retained the original rear endpoint to match the source roof silhouette to put the rear slope behind the source-visible left roof contour; fitted the two outer eave edges within two source pixels and preserved the body walls; the chimney taper and supports are corrected separately.','Native bitmaps and facing threshold remain unchanged; restored211 to body/hood receivers; the generic zero-ground proxy is excluded from source occlusion with measured foot evidence.'],limitations=['Concealed ridge position, height and support thickness are inferred from the visible left roof contour, not directly measured.','Source silhouette uncertainty is approximately three pixels; original eave anchors are preserved in the immutable baseline for comparison.','This is a new geometry revision and is not authorized for texture generation until reviewed.'],recipe=str(Path(__file__).resolve()),recipe_sha256=sha(__file__))
 (out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
 evidence=out/'post-ground-evidence.json'
 evidence.write_text(json.dumps(dict(version=1,source_sha256=sha(old/'reference/source.png'),native_source_domain='native210 roof/posts plus native211 masonry/hearth/hood',source_landmarks=next(r['landmarks'] for r in reports if 'landmarks' in r),ground_world_z=0,ground_object='nottingham Terrain',rationale='All three visible support feet descend below the flat zero-height proxy when their top anchors and native artwork heights are preserved. The local depicted slope is lower than this generic plane. Exclude only that ground plane from source occlusion; keep all structural foreground occluders.'),indent=2)+'\n')
 config=json.loads((out/'workspace.json').read_text())
 config['source_projection_ground_exclusion']=dict(version=1,asset_id=ASSET,object_name='nottingham Terrain',rationale='Measured source-visible timber feet lie below the inaccurate flat ground proxy; preserve their native artwork while retaining structural occluders.',source_sha256=sha(old/'reference/source.png'),evidence=str(evidence),evidence_sha256=sha(evidence))
 (out/'workspace.json').write_text(json.dumps(config,indent=2)+'\n')
 masks=json.loads((out/'source-masks.json').read_text())
 for assignment in masks['projections']['exterior']['assignments']:
  if assignment.get('source_node') in ['building-281','building-284']:
   assignment['mask_indices']=[210,211]
   assignment['review_evidence']=str(WORK/'coordinator-audit/small-hut-projection/native211-domain.png')
   assignment['review_note']='Native211 owns the forge hearth, white masonry side and chimney hood; native210 owns roof/posts. Restored reviewed ownership; all foreground first-hit constraints remain active.'
 shutil.copytree(WORK/'mask-review/hut-eave-v7/reviewed-eave-domain',out/'reviewed-eave-domain',dirs_exist_ok=True)
 (out/'source-masks.json').write_text(json.dumps(masks,indent=2)+'\n')
 rw.modified(out)
 report['model_sha256']=sha(out/'model.blend')
 (out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=ASSET,status='refinement-in-progress',geometry_approval='pending-new-user-review',model_sha256=sha(out/'model.blend'),modified_views_sha256=sha(out/'modified/views.json'),recipe=str(Path(__file__).resolve())),indent=2)+'\n')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
