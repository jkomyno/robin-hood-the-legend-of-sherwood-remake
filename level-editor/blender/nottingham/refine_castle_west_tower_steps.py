"""Trace the three exposed access treads beside the west gate tower."""
import json, math, sys, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from correct_source_projection import geometry

def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 from refinement_workspace import prepare,modified
 from refine_castle_secondary import replace_mesh
 old=WORK/'round-25/assets/nottingham-castle-gate-west-tower';out=WORK/'round-28/assets/nottingham-castle-gate-west-tower'
 c=json.loads((old/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update();before=geometry()
 obj=next(o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==c['asset_id'] and o.get('source_node')=='building-330')
 prepare(out,asset_id=c['asset_id'],scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=256,height=320,context_padding=35,framing_padding=1.1)
 points=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][330]['points'];low=points[3];high=points[0];side=points[2]
 # Numbered far-edge leading corners measured in the untouched source artwork.
 targets=[(737.0,1369.0),(746.0,1358.0),(754.0,1349.0)]
 def native_y(x):return low['y']+(high['y']-low['y'])*(x-low['x'])/(high['x']-low['x'])
 profile=[(low['x'],low['z_top'])];z=low['z_top'];trace=[]
 for i,(x,sy) in enumerate(targets):
  profile.append((x,z));z=native_y(x)-sy;profile.append((x,z));trace.append(dict(number=i+1,role='far tread leading corner',source_pixel=[x,sy],confidence='measured +/-2 pixels',native_height=z))
 profile.append((high['x'],z))
 # A continuous sloped underside avoids coincident reverse risers.
 assert min(h-(low['z_top']-8+(z-low['z_top'])*(x-low['x'])/(high['x']-low['x'])) for x,h in profile)>0
 profile += [(high['x'], z-8), (low['x'], low['z_top']-8)]
 s,co=math.sin(math.radians(35)),math.cos(math.radians(35));inv=obj.matrix_world.inverted();dx=side['x']-low['x'];dy=side['y']-low['y'];verts=[]
 for offset in [0,1]:
  verts.extend(inv@Vector((x+offset*dx,-(native_y(x)+offset*dy)/s,h/co)) for x,h in profile)
 n=len(profile);faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 replace_mesh(obj,verts,faces);bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);volume=bm.calc_volume(signed=True);bm.to_mesh(obj.data);bm.free();assert volume>0
 after=geometry();assert {k:v for k,v in before.items() if k!=obj.name}=={k:v for k,v in after.items() if k!=obj.name}
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));modified(out)
 report=dict(status='awaiting-independent-review',previous_workspace=str(old),model_sha256=hashlib.sha256((out/'model.blend').read_bytes()).hexdigest(),changed_source_nodes=['building-330'],outside_geometry_preserved=len(before)-1,tread_count=3,source_sha256=hashlib.sha256((out/'reference/source.png').read_bytes()).hexdigest(),source_trace=trace,signed_volume=volume,inference='Full tread width and sloped underside eight units below endpoint treads retain the prior footprint behind foreground parapet328. Three visible far tread corners constrain heights; untouched parapet hides the near ends.')
 (out/'stair-correction.json').write_text(json.dumps(report,indent=2)+'\n');(out/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=c['asset_id'],status='refinement-in-progress',geometry_reviewed=False,geometry_refined=True,inspected_views=[],recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
