"""Remove the unsupported zero-ground column beneath the tower access cap."""
import json,math,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from correct_source_projection import geometry

def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 from refinement_workspace import prepare,modified
 from refine_castle_secondary import replace_mesh
 old=WORK/'round-24/assets/nottingham-castle-gate-west-tower';out=WORK/'round-25/assets/nottingham-castle-gate-west-tower';c=json.loads((old/'workspace.json').read_text());m=json.loads((old/'source-masks.json').read_text())
 assignment=next(e for e in m['projections']['exterior']['assignments']if e['source_node']=='building-330');assignment.update(mask_indices=[278,279,280,284,285],review_note='Sloped access cap330 may receive only native-owned source pixels; cottage65/chimney67 excluded, full-scene first-hit retained. Foreground parapet328 is taller and remains a real source occluder.')
 mask=WORK/'castle-audit/review4-texture/west-access-cap-masks.json';mask.write_text(json.dumps(m,indent=2)+'\n');bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update();before=geometry();obj=next(o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH'and o.get('asset_group')==c['asset_id']and o.get('source_node')=='building-330')
 prepare(out,asset_id=c['asset_id'],scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=mask,width=256,height=320,context_padding=35,framing_padding=1.1)
 points=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][330]['points'];s,co=math.sin(math.radians(35)),math.cos(math.radians(35));inv=obj.matrix_world.inverted();verts=[inv@Vector((p['x'],-p['y']/s,(p['z_top']-offset)/co))for offset in [0,4]for p in points];faces=[(0,1,2,3),(7,6,5,4)]+[(i,(i+1)%4,(i+1)%4+4,i+4)for i in range(4)];replace_mesh(obj,verts,faces)
 after=geometry();assert {k:v for k,v in before.items()if k!=obj.name}=={k:v for k,v in after.items()if k!=obj.name};bm=bmesh.new();bm.from_mesh(obj.data);assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);bm.free();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));modified(out)
 proof=dict(version=1,status='awaiting-independent-review',previous_workspace=str(old),model_sha256=hashlib.sha256((out/'model.blend').read_bytes()).hexdigest(),changed_source_nodes=['building-330'],outside_geometry_preserved=len(before)-1,thickness_native_height_units=4,source_top_points=[[p['x'],p['y']-p['z_top']]for p in points],inference='Four-unit closed slab thickness is inferred. The top plane preserves the native sloped access surface exactly; the prior floor-to-zero column duplicated neighboring courtyard wall328. Tall foreground328 remains an occluder; hidden cap pixels stay neutral.',grouping_revision=13)
 (out/'access-cap-correction.json').write_text(json.dumps(proof,indent=2)+'\n');(out/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=c['asset_id'],status='refinement-in-progress',geometry_reviewed=False,geometry_refined=True,inspected_views=[],recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
