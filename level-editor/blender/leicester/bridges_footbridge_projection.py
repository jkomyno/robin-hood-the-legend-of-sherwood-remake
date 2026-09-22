"""Correct east footbridge ownership in a fresh comparison; preserve geometry."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from refinement_workspace import prepare,modified,validate
ROOT=Path('level-editor/work/leicester-refinement').resolve()
ASSET='leicester-east-village-footbridge'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def geometry():
 records=[]
 for obj in bpy.data.collections['Leicester Working'].all_objects:
  if obj.type=='MESH' and obj.get('asset_group')==ASSET:
   records.append({'name':obj.name,'source_node':obj.get('source_node'),'projection_component':obj.get('projection_component'),
     'world_matrix':[list(row) for row in obj.matrix_world],'vertices':[list(v.co) for v in obj.data.vertices],
     'faces':[list(p.vertices) for p in obj.data.polygons]})
 return sorted(records,key=lambda record:record['name'])
def main():
 workspace=ROOT/'round-1/assets-v2'/ASSET
 archive=ROOT/'round-1/bridge-revision-archive/user-footbridge-projection'/ASSET
 evidence=ROOT/'bridge-evidence/east-footbridge-projection-revision-v2'
 if not archive.exists():
  records={str(p.relative_to(workspace)):sha(p) for p in workspace.rglob('*') if p.is_file()}
  archive.parent.mkdir(parents=True,exist_ok=True);workspace.rename(archive)
  (archive.parent/'archive.json').write_text(json.dumps({'original_workspace':str(workspace),'archived_workspace':str(archive),'files_sha256':records,
    'feedback':'leicester-east-village-footbridge: looks good but again textures are projected wrong, wrong mask? most texture is missing here',
    'scope':'Source ownership correction only; preserve reviewed geometry. Archived configuration keeps original absolute paths; remap that workspace prefix when replaying archive.'},indent=2)+'\n')
 if not (workspace/'workspace.json').exists():
  bpy.ops.wm.open_mainfile(filepath=str(archive/'model.blend'));bpy.context.window.scene=bpy.data.scenes['Leicester Refinement'];bpy.context.view_layer.update()
  before=geometry();config=json.loads((archive/'workspace.json').read_text())
  prepare(workspace,asset_id=ASSET,scene_name=config['scene_name'],collection_name=config['collection_name'],
    source_path=archive/'reference/source.png',grouping_manifest=archive/'reference/grouping.json',inventory_path=archive/'reference/inventory.json',
    review_path=archive/'reference/grouping-review.json',source_mask_manifest=evidence/'initial-masks.json',
    width=config['width'],height=config['height'],framing_padding=config['framing_padding'],elevation_degrees=config['elevation_degrees'])
  (workspace/'inspection').mkdir(exist_ok=True)
  (workspace/'inspection/reviewed-geometry.json').write_text(json.dumps(before,indent=2)+'\n')
 else:
  bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'));before=json.loads((workspace/'inspection/reviewed-geometry.json').read_text())
 bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
 config=json.loads((workspace/'workspace.json').read_text());shutil.copy2(evidence/'corrected-masks.json',config['source_mask_manifest'])
 if geometry()!=before:raise RuntimeError('Reviewed geometry changed before projection')
 modified(workspace);validate(workspace)
 if geometry()!=before:raise RuntimeError('Projection changed reviewed geometry')
 report={'geometry_unchanged':True,'geometry_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
    'reviewed_model_sha256':sha(archive/'model.blend'),'corrected_model_sha256':sha(workspace/'model.blend'),
    'mask_evidence_sha256':sha(evidence/'review.json'),'recipe_sha256':sha(__file__),'status':'projection correction rendered; actual-material and visual QA pending',
    'source_counts_before':[v['counts'] for v in json.loads((workspace/'input/views.json').read_text())['views']],
    'source_counts_after':[v['counts'] for v in json.loads((workspace/'modified/views.json').read_text())['views']]}
 (workspace/'inspection/projection-correction.json').write_text(json.dumps(report,indent=2)+'\n')
 shutil.copy2(__file__,workspace/'inspection/projection-recipe-executed.py');shutil.copy2(archive/'inspection/user-projection-feedback.json',workspace/'inspection/user-projection-feedback.json')
 (workspace/'handoff.json').write_text(json.dumps({'status':'fix-needed','notes':'Source mask correction rendered; all8 source and saved-material QA pending. Geometry unchanged.','recipe':'inspection/projection-recipe-executed.py','ownership':'source-masks.json','all_eight_views_inspected':False,'texture_generation':'blocked-pending-source-projection-correction','publication':'not-started'},indent=2)+'\n')
 print(json.dumps(report))
if __name__=='__main__':main()
