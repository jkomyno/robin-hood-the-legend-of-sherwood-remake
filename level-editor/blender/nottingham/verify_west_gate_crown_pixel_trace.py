"""Check the access stair packet against its immutable predecessor."""
import sys,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(Path(__file__).parent));WORK=ROOT/'level-editor/work/nottingham-refinement'
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy,bmesh
from refinement_workspace import validate
old=WORK/'round-28/assets/nottingham-castle-gate-west-tower';w=WORK/'round-38/assets/nottingham-castle-gate-west-tower'
def snapshot():
 result={}
 for o in bpy.data.objects:
  if o.type!='MESH':continue
  result[o.name]=dict(node=o.get('source_node'),asset=o.get('asset_group'),vertices=[list(v.co) for v in o.data.vertices],faces=[list(p.vertices) for p in o.data.polygons],matrix=[list(row) for row in o.matrix_world],uv=[(u.name,[list(d.uv) for d in u.data]) for u in o.data.uv_layers],materials=[m.name if m else None for m in o.data.materials],indices=[p.material_index for p in o.data.polygons])
 return result
bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));before=snapshot();bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));after=snapshot();assert set(before)==set(after)
changes=[]
for name,a in after.items():
 b=before[name]
 if a['asset']!=w.name:assert a==b,('outside object drift',name)
 if a['node'] not in ['building-331','building-332']:assert all(a[k]==b[k] for k in ['vertices','faces','matrix']),('unrelated geometry drift',name)
 if a!=b:changes.append(name)
validation=validate(w);assert validation['status']=='PASS'
objects=[o for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')==w.name and o.get('source_node') in ['building-331','building-332']]
points=[];actual=[]
for o in objects:
 bm=bmesh.new();bm.from_mesh(o.data);assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);assert bm.calc_volume(signed=True)>0;bm.free()
 ps=[o.matrix_world@v.co for v in o.data.vertices];pixels=[(v.x,-v.y*math.sin(math.radians(35))-v.z*math.cos(math.radians(35)))for v in ps];points.extend(pixels);actual.append(dict(node=o['source_node'],vertices=pixels,edges=[list(e.vertices)for e in o.data.edges]))
report=json.loads((w/'crown-correction.json').read_text());rows=[]
for target in report['corners']:
 for role in ['outer_source','inner_source','notch_floor_source']:
  x,y=target[role];err=min(math.hypot(px-x,py-y)for px,py in points);assert err<.002,(target,role,err);rows.append(dict(cap=target['cap'],endpoint=target['endpoint'],role=role,source_pixel=[x,y],construction_residual=err))
(w/'inspection').mkdir(exist_ok=True)
(w/'inspection/crown-structure-validation.json').write_text(json.dumps(dict(status='PASS',model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),validation=validation,outside_geometry_uv_materials_preserved=True,unchanged_core_stair_geometry=True,changed_objects=changes,measured_corner_construction_checks=rows,actual_meshes=actual,nonmanifold_edges=0,degenerate_faces=0),indent=2)+'\n')
code=(Path(__file__).parent/'verify_workspace_known_rgb.py').read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')");sys.argv=['verify_workspace_known_rgb.py','--',str(w)];exec(compile(code,str(Path(__file__).parent/'verify_workspace_known_rgb.py'),'exec'))

from audit_stored_materials import run
run(w,w/'inspection/stored-materials',render=True)
sys.argv=['audit_castle_final_source_coverage.py','--',str(w)]
exec(compile((Path(__file__).parent/'audit_castle_final_source_coverage.py').read_text(),str(Path(__file__).parent/'audit_castle_final_source_coverage.py'),'exec'))
