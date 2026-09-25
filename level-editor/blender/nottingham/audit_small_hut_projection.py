"""Trace the approved hut faces into source artwork before correcting ownership."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];W=ROOT/"level-editor/work/nottingham-refinement";A="nottingham-village-small-hut"
sys.path.insert(0,str(Path(__file__).parent))
S=math.sin(math.radians(35));C=math.cos(math.radians(35));toward=Vector((0,-C,S))
args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
model=Path(args[0]) if args else W/"round-23/assets"/A/"model.blend"
bpy.ops.wm.open_mainfile(filepath=str(model));bpy.context.view_layer.update();rows=[]
if "--fit-eaves" in args:
 for o in bpy.context.scene.objects:
  if o.type!='MESH' or o.get('asset_group')!=A:continue
  if o.get('source_node')=='building-282':indices,dx,dz=[2,6],2,.5
  elif o.get('source_node')=='building-283':indices,dx,dz=[1,5],-1.5,.8
  else:continue
  inv=o.matrix_world.inverted()
  for j in indices:
   p=o.matrix_world@o.data.vertices[j].co;p.x+=dx
   if j>=4:p.z+=dz
   o.data.vertices[j].co=inv@p
  o.data.update()
if "--repair-supports" in args:
 from small_hut_source_structure import repair
 repair({o.get("source_node"):o for o in bpy.context.scene.objects if o.type=="MESH" and not o.hide_render and o.get("asset_group")==A})
 bpy.context.view_layer.update()
for o in bpy.data.collections["nottingham Working"].all_objects:
 if o.type!="MESH" or o.hide_render or o.get("asset_group")!=A:continue
 vertices=[o.matrix_world@v.co for v in o.data.vertices];faces=[]
 o.data.calc_loop_triangles()
 for f in o.data.polygons:
  n=(o.matrix_world.to_3x3().inverted().transposed()@f.normal).normalized()
  faces.append({"index":f.index,"vertices":list(f.vertices),"normal":list(n),"toward":n.dot(toward),"source":[[vertices[i].x,-vertices[i].y*S-vertices[i].z*C] for i in f.vertices]})
 rows.append({"name":o.name,"node":o.get("source_node"),"vertices":[list(v)for v in vertices],"faces":faces,"triangles":[list(t.vertices) for t in o.data.loop_triangles]})
out=Path(args[1]) if len(args)>1 else W/"coordinator-audit/small-hut-projection";out.mkdir(parents=True,exist_ok=True);(out/"faces.json").write_text(json.dumps(rows,indent=2)+"\n");print(str(out/"faces.json"))
