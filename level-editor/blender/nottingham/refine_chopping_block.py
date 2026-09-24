"""Replace the hollow container hypothesis with the source chopping block and axe."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
S=math.sin(math.radians(35));C=math.cos(math.radians(35));ASSET='nottingham-village-small-hut-prop';TAG='chopping_block_axe_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pixel(x,y,z):return Vector((x,(-y-z*C)/S,z))
def refine():
 from refine_village_secondary import replace
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH'and not o.hide_render and o.get('asset_group')==ASSET and o.get('source_node')=='building-314')
 if obj.get(TAG):return json.loads(obj[TAG])
 verts=[];faces=[];count=32;center=pixel(438.0,2893.3,12)
 for z,radius in [(0,.94),(1.3,1.0),(8.5,1.0),(12,1.03)]:
  for i in range(count):
   a=i*math.tau/count;r=radius*(1+.025*math.sin(5*a));verts.append(Vector((center.x+5.0*r*math.cos(a),center.y+3.6*r*math.sin(a),z)))
 for row in range(3):
  for i in range(count):j=(i+1)%count;faces.append((row*count+i,row*count+j,(row+1)*count+j,(row+1)*count+i))
 faces.extend([tuple(reversed(range(count))),tuple(3*count+i for i in range(count))])
 def prism(poly,depth):
  start=len(verts);n=len(poly);delta=Vector((0,-C,S))*depth/2;verts.extend(p-delta for p in poly);verts.extend(p+delta for p in poly);faces.extend([tuple(start+i for i in reversed(range(n))),tuple(start+n+i for i in range(n))]);faces.extend((start+i,start+(i+1)%n,start+n+(i+1)%n,start+n+i)for i in range(n))
 blade=[(435.0,2886.8,20),(437.7,2886.1,20.6),(439.1,2888.4,18),(442.0,2889.5,16.5),(441.6,2892.1,11),(436.3,2892.2,11.1),(436.1,2889.4,17),(435.0,2888.8,18)]
 prism([pixel(*p)for p in blade],.6)
 # The handle follows the long painted diagonal. Its hidden circular section is inferred.
 a=pixel(437.5,2886.5,20.5);b=pixel(452.7,2877.4,30);axis=(b-a).normalized();u=axis.cross(Vector((0,0,1))).normalized();v=axis.cross(u).normalized();start=len(verts)
 for p in [a,b]:
  verts.extend(p+(u*math.cos(i*math.tau/8)+v*math.sin(i*math.tau/8))*.55 for i in range(8))
 faces.extend([tuple(start+i for i in reversed(range(8))),tuple(start+8+i for i in range(8))]);faces.extend((start+i,start+(i+1)%8,start+8+(i+1)%8,start+8+i)for i in range(8))
 report=replace(obj,verts,faces,'Solid chopping block with axe');obj['projection_min_cosine']=.05
 report.update(asset_id=ASSET,changes=['Closed the pale cut wooden top instead of a hollow barrel cavity.','Added the source-visible steel axe head and long diagonal wooden handle.','Retained one selectable canonical314 part with closed stump, blade and handle components.'],source_trace={'stump_top_center':[438.0,2893.3],'blade':[[x,y]for x,y,z in blade],'handle':[[437.5,2886.5],[452.7,2877.4]]},inference=['Hidden stump rear and bottom, slight bark irregularity, blade thickness0.6 and eight-sided handle radius0.55 are inferred.','Source artwork is22x29pixels; manually picked contours have approximatelyonepixel uncertainty.','Blade is inset into the solid top; exact tool pitch/depth are hypotheses constrained by its projected silhouette.'])
 obj[TAG]=json.dumps(report);return report

def main():
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import refinement_workspace as rw
 from refine_village_secondary import digest
 old=WORK/'round-1/assets'/ASSET;new=WORK/'round-31/assets'/ASSET;cfg=json.loads((old/'workspace.json').read_text())
 if not new.exists():
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));rw.prepare(new,asset_id=ASSET,scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=384,height=384,context_padding=32,framing_padding=3.2)
 bpy.ops.wm.open_mainfile(filepath=str(new/'baseline.blend'));bpy.context.view_layer.update()
 def snapshot():return {o.name:(digest(o),[list(r)for r in o.matrix_world])for o in bpy.context.scene.objects if o.type=='MESH'}
 before=snapshot();report=refine();after=snapshot();assert all(before[k]==after[k]for k in before if bpy.data.objects[k].get('asset_group')!=ASSET);refine();assert after==snapshot()
 report.update(recipe_sha256=sha(__file__),tooling=tooling,idempotence='PASS',outside_objects_unchanged=True);(new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));rw.modified(new)
 (new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=ASSET,status='refinement-in-progress',model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'),recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
