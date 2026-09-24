"""Restore courtyard support ownership and retain the reviewed visible wall geometry."""
import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
import refinement_workspace as rw
from audit_stored_materials import run
from restore_native_southwest_support import restore_support
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
asset='nottingham-castle-west-courtyard-wall';old=WORK/'round-5/assets'/asset;new=WORK/'round-38/assets'/asset
bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));cfg=json.loads((old/'workspace.json').read_text())
owned=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==asset];names={o['source_node']:o.name for o in owned};matrices={o['source_node']:[list(r) for r in o.matrix_world] for o in owned};assert set(names)=={'building-327','building-328','building-379'}
from restore_foreign_uv_schema import invariant
approved_geometry={o['source_node']:dict(vertices=[list(v.co) for v in o.data.vertices],faces=[list(p.vertices) for p in o.data.polygons]) for o in owned}
bpy.ops.wm.open_mainfile(filepath=str(WORK/'grouped/nottingham-grouped-v14.blend'))
objects=list(bpy.data.collections[cfg['collection_name']].all_objects)
for node,name in names.items():
 target=next(o for o in objects if o.type=='MESH' and o.get('source_node')==node)
 assert [list(r) for r in target.matrix_world]==matrices[node]
 with bpy.data.libraries.load(str(old/'model.blend'),link=False) as (source,destination):destination.objects=[name]
 archived=destination.objects[0];target.data=archived.data.copy();bpy.data.objects.remove(archived,do_unlink=True)
 assert [list(v.co) for v in target.data.vertices]==approved_geometry[node]['vertices']
 assert [list(p.vertices) for p in target.data.polygons]==approved_geometry[node]['faces']
recovery=restore_support(WORK/'grouped/nottingham-grouped-v7.blend',cfg['collection_name'],asset,'Castle courtyard southwestern curtain wall')
# Explicitly reject painted stair source on the support; it has no exposed native projection domain.
m=json.loads((old/'source-masks.json').read_text());a=next(a for a in m['projections']['exterior']['assignments'] if a['source_node']=='building-352');a.update(mask_indices=[527],reviewed=True,native_ownership_reviewed=False,constraint_kind='unknown-no-approved-source',accepted_source_pixels=0,review_note='Native352 is a source-hidden support volume, not the separately owned221 stair. Complete native-scene first-hit scan found zero exposed352 pixels.',review_evidence=str(WORK/'castle-audit/review6-stair/native352-first-hits.json'))
mask=WORK/'mask-review/courtyard-support352.json';mask.write_text(json.dumps(m,indent=2)+'\n')
rw.prepare(new,asset_id=asset,scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=old/'reference/source.png',grouping_manifest=WORK/'grouping/catalog-v14.json',inventory_path=WORK/'inventory/inventory-v2.json',review_path=WORK/'grouping/grouping-review-v14.json',source_mask_manifest=mask,width=384,height=448,context_padding=150,framing_padding=1.08)
(new/'inspection').mkdir(exist_ok=True);(new/'inspection/support-recovery.json').write_text(json.dumps(recovery,indent=2)+'\n');shutil.copy2(WORK/'castle-audit/review6-stair/identity-source-comparison.png',new/'inspection/identity-source-comparison.png');rw.modified(new)
from restore_foreign_uv_schema import restore_foreign_uv_schema
restore_foreign_uv_schema(new,apply=True)
audit=run(new,new/'inspection/stored-material',render=True,export=False);assert audit['status']=='STRUCTURAL-PASS',audit['problems']
(new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=asset,status='refinement-in-progress',geometry_refined=False,geometry_reviewed=False,recipe=str(Path(__file__).resolve()),model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json')),indent=2)+'\n')
