"""Reproject an woodland bank with an immutable corrected mask revision."""
import json
import hashlib
from pathlib import Path
import shutil
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refinement_workspace import prepare,modified
from props import signature

root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
archive=root/'round-1/props-revision-archive/leicester-southwest-woodland-bank-before-ground-mask-correction'
workspace=root/'round-1/assets-v2/leicester-southwest-woodland-bank'
config=json.loads((archive/'workspace.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(archive/'model.blend'),load_ui=False)
def geometry():
    return {o.name:{'mesh':signature(o),'matrix':[list(row) for row in o.matrix_world]} for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH'}
before=geometry()
prepare(workspace,asset_id=config['asset_id'],scene_name=config['scene_name'],collection_name=config['collection_name'],source_path=archive/'reference/source.png',grouping_manifest=archive/'reference/grouping.json',inventory_path=archive/'reference/inventory.json',review_path=archive/'reference/grouping-review.json',source_mask_manifest=root/'mask-audit/woodland-bank-v10/source-masks.json',width=config['width'],height=config['height'],elevation_degrees=config['elevation_degrees'],context_padding=config['context_padding'],framing_padding=config['framing_padding'])
modified(workspace)
after=geometry()
if before!=after:raise ValueError('Existing geometry or context changed')
inspection=workspace/'inspection';inspection.mkdir(exist_ok=True)
(inspection/'geometry-preservation.json').write_text(json.dumps({'status':'PASS','archived_reviewed_model':str(archive/'model.blend'),'archived_model_sha256':hashlib.sha256((archive/'model.blend').read_bytes()).hexdigest(),'all_mesh_geometry_and_transforms_equal':True,'before':before,'after':after},indent=2)+'\n')
shutil.copy2(max((workspace/'projection').glob('*/ownership.json'),key=lambda p:p.stat().st_mtime_ns),inspection/'ownership.json')
handoff=json.loads((archive/'handoff.json').read_text());handoff.update(status='validation-pending',all_eight_views_inspected=False,geometry_approval='pending')
handoff['texture_issue']={'status':'correction-awaiting-review','generation_blocked':True,'reviewed_evidence_archive':str(archive),'geometry_preservation':'inspection/geometry-preservation.json','mask_revision':'mask-audit/woodland-bank-v10'}
(workspace/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
print('BANK_SOURCE_CORRECTION_COMPLETE geometry bit-for-bit unchanged')
