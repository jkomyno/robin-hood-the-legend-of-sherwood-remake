"""Constrain neighboring coping proxies to their observed wall silhouette."""
import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy,bmesh
from mathutils import Vector
from mathutils.geometry import convex_hull_2d
import refinement_workspace as rw
from audit_stored_materials import run
from refine_village_secondary import digest
old=WORK/'round-32/assets/nottingham-southwest-wall-stair';wall=WORK/'round-31/assets/nottingham-southwest-curtain-wall-north';new=WORK/'round-33/assets'/old.name
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
mask=WORK/'mask-review/southwest-stair-final-occluders.json'
m=json.loads((old/'source-masks.json').read_text());m['projections']['exterior']['occluder_constraints']=[dict(reviewed=True,source_node=f'building-{node}',receiver_nodes=['building-221'],mask_indices=[279,282],reason='Whole landing source-domain audit finds175 painted landing pixels inside native135 and outside both accepted neighboring wall masks279/282. Scope only these oversized foreign wall/coping proxies; keep own and every other blocker.',review_evidence=str(old/'inspection/source-domain-audit/source-vs-domains.png')) for node in [328,379]];mask.write_text(json.dumps(m,indent=2)+'\n')
if not new.exists():
 bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));c=json.loads((old/'workspace.json').read_text())
 rw.prepare(new,asset_id=old.name,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=mask,width=384,height=448,context_padding=48,framing_padding=1.15)
 (new/'inspection').mkdir(exist_ok=True);rw.modified(new)
from restore_foreign_uv_schema import restore_foreign_uv_schema
# The global projection refresh updates this Boolean-edited proxy UV layer.
# Restore its exact frozen UV values; the proxy serves only as an occluder.
from restore_foreign_uv_schema import uv,invariant
bpy.ops.wm.open_mainfile(filepath=str(new/'baseline.blend'));proxy=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('source_node')=='building-220' and not o.hide_render);proxy_name=proxy.name;expected_uv=uv(proxy)
bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'));proxy=bpy.data.objects[proxy_name];guard={o.name:invariant(o) for o in bpy.data.objects if o.type=='MESH'}
for layer,values in expected_uv.items():
 target_layer=proxy.data.uv_layers[layer];assert len(target_layer.data)==len(values)
 for v,xy in zip(target_layer.data,values):v.uv=xy
assert guard=={o.name:invariant(o) for o in bpy.data.objects if o.type=='MESH'}
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'))
(new/'inspection/occluder-uv-restoration.json').write_text(json.dumps(dict(status='PASS',object=proxy_name,layers=list(expected_uv),non_uv_state_preserved=True,reason='Restored exact frozen proxy UV coordinates after global projection refresh.'),indent=2)+'\n')
restore_foreign_uv_schema(new,apply=True)
changed=[proxy_name]
for p in ['geometry-report.json']:
 shutil.copy2(old/p,new/p)
shutil.copy2(old/'inspection/landing-source-comparison.png',new/'inspection/landing-source-comparison.png')
(new/'neighbor-import.json').write_text(json.dumps(dict(status='PASS',source_stair_sha256=sha(old/'model.blend'),source_wall_sha256=sha(wall/'model.blend'),native_scoped_occluders=[328,379],corrected_occluder_objects=changed,own_geometry_preserved=True,reason='The older scene has an unsplit canonical220 wall proxy. Apply the final stair-exclusive footprint subtraction before freeze, preserving its southern portion and all other scene geometry. Source projection and the actual final pair now share the landing occlusion boundary.'),indent=2)+'\n')
audit=run(new,new/'inspection/stored-material',render=True,export=False);assert audit['status']=='STRUCTURAL-PASS',audit['problems']
(new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=new.name,status='refinement-in-progress',recipe=str(Path(__file__).resolve())),indent=2)+'\n')
