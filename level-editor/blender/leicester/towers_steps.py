"""Replace the church tower's source-visible stair ramp with nine closed treads."""
import json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from towers import write_mesh,diagnostics
workspace=Path(sys.argv[sys.argv.index('--')+1]).resolve()
config=json.loads((workspace/'workspace.json').read_text())
assert config['asset_id']=='leicester-church-side-tower'
obj=next(o for o in bpy.data.collections[config['collection_name']].all_objects if o.get('asset_group')==config['asset_id'] and o.get('source_node')=='building-191')
points=json.loads((Path(__file__).resolve().parents[3]/'datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json').read_text())['sight_obstacles'][191]['points']
s,c=math.sin(math.radians(35)),math.cos(math.radians(35))
p=[Vector((v['x'],-v['y']/s,v['z_top']/c)) for v in points]
verts=[];faces=[];count=9
for i in range(count):
 t0,t1=i/count,(i+1)/count
 corners=[p[0].lerp(p[3],t0),p[1].lerp(p[2],t0),p[1].lerp(p[2],t1),p[0].lerp(p[3],t1)]
 z=p[0].z+(p[3].z-p[0].z)*t1
 offset=len(verts);verts.extend([(v.x,v.y,z) for v in corners]+[(v.x,v.y,0) for v in corners])
 faces.extend(tuple(offset+j for j in f) for f in [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)])
before=diagnostics(obj);write_mesh(obj,verts,faces,obj.name+' nine stone treads')
bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
after=diagnostics(obj);assert not after['nonmanifold_edges'] and not after['degenerate_faces']
(workspace/'inspection/stone-stairs.json').write_text(json.dumps(dict(source_node='building-191',before=before,after=after,treads=count,evidence='Covered northeast tower source: exposed approach stair flight; native bottom/top corners and landing heights retained.',limitations=['Nine visible tread bands interpreted from artwork; uniform rise/run and hidden riser depths are hypotheses.']),indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
