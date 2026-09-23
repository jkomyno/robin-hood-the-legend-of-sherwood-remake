"""Check the access stair packet against its immutable predecessor."""
import sys,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(Path(__file__).parent));WORK=ROOT/'level-editor/work/nottingham-refinement'
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy,bmesh
from refinement_workspace import validate
old=WORK/'round-25/assets/nottingham-castle-gate-west-tower';w=WORK/'round-28/assets/nottingham-castle-gate-west-tower'
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
 if a['node']!='building-330':assert all(a[k]==b[k] for k in ['vertices','faces','matrix']),('unrelated geometry drift',name)
 if a!=b:changes.append(name)
validation=validate(w);assert validation['status']=='PASS'
o=next(o for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')==w.name and o.get('source_node')=='building-330');bm=bmesh.new();bm.from_mesh(o.data);assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);volume=bm.calc_volume(signed=True);assert volume>0;bm.free()
report=json.loads((w/'stair-correction.json').read_text());rows=[]
for target in report['source_trace']:
 x,y=target['source_pixel'];projected=[(o.matrix_world@v.co) for v in o.data.vertices];pixels=[(v.x,-v.y*math.sin(math.radians(35))-v.z*math.cos(math.radians(35))) for v in projected];err=min(math.hypot(px-x,py-y) for px,py in pixels);assert err<.001;rows.append(dict(**target,actual_saved_vertex_residual_pixels=err))
(w/'inspection').mkdir(exist_ok=True)
(w/'inspection/steps-structure-validation.json').write_text(json.dumps(dict(status='PASS',model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),validation=validation,outside_geometry_uv_materials_preserved=True,unchanged_non330_geometry=True,changed_objects=changes,measured_corner_construction_checks=rows,actual_source_vertices=pixels,actual_mesh_edges=[list(e.vertices) for e in o.data.edges],nonmanifold_edges=0,degenerate_faces=0,signed_volume=volume),indent=2)+'\n')
code=(Path(__file__).parent/'verify_workspace_known_rgb.py').read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')");sys.argv=['verify_workspace_known_rgb.py','--',str(w)];exec(compile(code,str(Path(__file__).parent/'verify_workspace_known_rgb.py'),'exec'))
