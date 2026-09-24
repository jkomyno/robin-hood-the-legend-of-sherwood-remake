"""Fit the mill's low thatch eave to its painted contour in a derived review packet."""
import json, math, sys, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
if '--geometry-only' not in sys.argv:acquire(slots=2)
import bpy
import refinement_workspace as rw
from mathutils import Vector
from refine_village_secondary import digest

def main():
 asset='nottingham-village-mill'
 old=WORK/'round-1/assets'/asset
 final='--final' in sys.argv
 new=WORK/'round-34/assets'/asset if final else WORK/'texture-generation/projection-corrections'/asset
 c=json.loads((old/'workspace.json').read_text())
 if '--audit-only' in sys.argv:
  (new/'inspection').mkdir(exist_ok=True)
  from restore_foreign_uv_schema import restore_foreign_uv_schema
  restore_foreign_uv_schema(new,apply=True)
  from audit_stored_materials import run
  run(new,new/'inspection/stored-materials',render=True,export=False)
  return
 if not new.exists():
  if '--geometry-only' in sys.argv:raise ValueError('Prepare the workspace under a render lease before using geometry-only mode')
  mask_source=old/'source-masks.json'
  if final:
   from mill_source_authority import prepare_authority
   authority=WORK/'mask-review/mill-authored-stone-authority'
   mask_source=authority/'assignments.json' if authority.exists() else prepare_authority(WORK,authority)
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=asset,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=mask_source,width=320,height=384,context_padding=30,framing_padding=1.12,lighting=json.loads((WORK/'lighting-calibration/map-lighting.json').read_text())['lighting'])
 bpy.ops.wm.open_mainfile(filepath=str(new/'baseline.blend'))
 before={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH'}
 o=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset and o.get('source_node')=='building-237' and not o.hide_render)
 s=math.sin(math.radians(35));co=math.cos(math.radians(35));inv=o.matrix_world.inverted();changes=[]
 for v in o.data.vertices:
  p=o.matrix_world@v.co
  if abs(p.z*co-95.215004)<.01:
   prior=list(p)
   if p.x<1570:p.x=1540.0;p.z=(2634.4766-2574.0)/co
   else:p.z=(2754.6733-2698.0)/co
   v.co=inv@p;changes.append(dict(source_node='building-237',vertex=v.index,before=prior,after=list(p)))
 o.data.update()
 if len(changes)!=2:raise ValueError(('Unexpected eave vertex count',len(changes)))
 # The painted ridge sags above the front gable; connect both halves at that datum.
 for node,near,height in [('building-236',1665.0509,120.0),('building-237',1665.112,120.0)]:
  part=next(q for q in bpy.context.scene.objects if q.type=='MESH' and q.get('asset_group')==asset and q.get('source_node')==node and not q.hide_render)
  inverse=part.matrix_world.inverted()
  for v in part.data.vertices:
   point=part.matrix_world@v.co
   if abs(point.x-near)<.01 and point.z>1:
    prior=list(point);point.z=height/co;v.co=inverse@point;changes.append(dict(source_node=node,vertex=v.index,before=prior,after=list(point)))
  part.data.update()
 # Retain the original upper back shoulder so the thatch follows the curved silhouette.
 from refine_village_secondary import replace
 native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][237]['points']
 bottom=[Vector((q['x'],-q['y']/s,0)) for q in native]
 top=[Vector((1617.0413,-2625.9927/s,150.009/co)),Vector((1665.112,-2746.1895/s,120/co)),Vector((1600.6309,-2754.6733/s,56.6733/co)),Vector((1591.8282,-2732.6487/s,95.268005/co)),Vector((1580.0377,-2703.1677/s,95.268005/co)),Vector((1540,-2634.4766/s,60.4766/co)),Vector((1552.56,-2614.4766/s,75.215004/co))]
 shoulder=replace(o,bottom+top,[(3,2,1,0),(4,5,6),(4,6,7),(4,7,8),(4,8,9),(4,9,10),(0,1,5,4),(1,2,6,5),(2,3,9),(2,9,8),(2,8,7),(2,7,6),(3,0,4),(3,4,10),(3,10,9)],'Mill left roof / drooping eave and upper shoulder')
 from fit_mill_chimney_base import apply as fit_base
 chimney=fit_base()
 contact=None
 if final:
  from cut_mill_mound_chimney_contact import apply as cut_contact
  contact=cut_contact(WORK/'mask-review/mill-authored-stone-authority/000529-authored-stone.png')
 changed=[k for k,v in before.items() if digest(bpy.data.objects[k])!=v]
 assert len(changed)==(4 if final else 3)
 report=dict(asset_id=asset,status='prototype-awaiting-source-review',source_node='building-237',changed_vertices=changes,changed_objects=changed,outside_objects_preserved=len(before)-len(changed),shoulder_mesh=shoulder,chimney_base=chimney,mound_contact=contact,source_eave_targets=[[1540,2574],[1600.6309,2698],[1552.56,2539.2616]],manual_uncertainty_pixels=3,changes=['Lowered the left main-roof eave anchors to the painted thatch outline so roof pixels reach a roof slope rather than the tall side wall.','Lowered the front ridge of both roof halves to native120; main left eave now meets the unchanged adjoining lean-to ridge at native95.268 using two intermediate contact vertices.','Retained the curved back shoulder source contour while moving its inferred depth twenty native units toward the source camera to keep the roof convex.','Restored a flared chimney base on receiver241 and assigned hay receiver240 to native144 with the separate masonry155 excluded.'],limitations=['This is a new geometry revision requiring user review. Source eave tracing and concealed wall support are inferred. Front ridge and curved eave contact are fitted to the drooping thatch. Back-shoulder depth and concealed chimney-foot depth are inferred; the adjoining lean-to remains unchanged.'])
 (new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
 maskpath=new/'source-masks.json';masks=json.loads(maskpath.read_text())
 if not final:
  assignment=next(a for a in masks['projections']['exterior']['assignments'] if a['source_node']=='building-240')
  assignment.update(mask_indices=[144],exclude_mask_indices=[155],exclusions_reviewed=True,exclusion_reason='The native155 stone chimney silhouette is a separate foreground component, not hay-mound material.',review_note='Right hay-mound half belongs to main native144 silhouette; native155 is separate stone chimney and must not project masonry onto hay. Source-domain witness mill-mound240-source.png confirms receiver identity.',review_evidence=str(WORK/'coordinator-audit/props/mill-mound240-source.png'))
  maskpath.write_text(json.dumps(masks,indent=2)+'\n')
 bpy.context.preferences.filepaths.save_version=0
 bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'))
 if '--geometry-only' in sys.argv:return
 rw.modified(new)
 (new/'inspection').mkdir(exist_ok=True)
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 restore_foreign_uv_schema(new,apply=True)
 from audit_stored_materials import run
 run(new,new/'inspection/stored-materials',render=True,export=False)
 report['model_sha256']=hashlib.sha256((new/'model.blend').read_bytes()).hexdigest()
 report['modified_views_sha256']=hashlib.sha256((new/'modified/views.json').read_bytes()).hexdigest()
 (new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
 (new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=asset,status='refinement-in-progress',geometry_approval='pending-new-review',recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
