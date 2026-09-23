"""Resolve an observed ground/BVH marching tie using independent double precision."""
import sys,json,math,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
w=WORK/'round-27/assets/nottingham-terrain-ground';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));cfg=json.loads((w/'workspace.json').read_text());bpy.context.window.scene=bpy.data.scenes[cfg['scene_name']];ground=next(o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH' and o.get('source_node')=='ground');x,y=1796,2725;s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=np.array([0,-c,s],dtype=np.float64);origin=np.array([x+.5,-(y+.5)*s,-(y+.5)*c])+toward*10000;direction=-toward
matrix=np.array([list(r) for r in ground.matrix_world],dtype=np.float64);vertices=np.array([(matrix@np.array([*v.co,1.]))[:3] for v in ground.data.vertices]);ground.data.calc_loop_triangles();hits=[]
for tri in ground.data.loop_triangles:
 a,b,d=vertices[list(tri.vertices)];edge1=b-a;edge2=d-a;p=np.cross(direction,edge2);det=np.dot(edge1,p)
 if abs(det)<1e-12:continue
 inv=1/det;t=origin-a;u=np.dot(t,p)*inv;q=np.cross(t,edge1);v=np.dot(direction,q)*inv;distance=np.dot(edge2,q)*inv
 if u>=-1e-10 and v>=-1e-10 and u+v<=1+1e-10 and distance>0:hits.append((distance,u,v,tri))
assert hits,'Analytic ground intersection is absent';distance,u,v,tri=min(hits,key=lambda t:t[0]);point=origin+direction*distance;face=ground.data.polygons[tri.polygon_index];material=ground.data.materials[face.material_index];uvnode=next(n for n in material.node_tree.nodes if n.type=='UVMAP');texture=next(n for n in material.node_tree.nodes if n.type=='TEX_IMAGE');uvs=[np.array(ground.data.uv_layers[uvnode.uv_map].data[i].uv,dtype=np.float64) for i in tri.loops];uv=uvs[0]*(1-u-v)+uvs[1]*u+uvs[2]*v;img=texture.image;px=int(math.floor(uv[0]*img.size[0]));py=int(math.floor((1-uv[1])*img.size[1]));assert (px,py)==(x,y),(px,py)
source=bpy.data.images.load(cfg['source_path'],check_existing=False);index=((img.size[1]-1-py)*img.size[0]+px)*4;actual=list(img.pixels[index:index+4]);expected=list(source.pixels[index:index+4]);assert actual[:3]==expected[:3],(actual,expected);assert actual[3]==1.0,actual
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();report=dict(status='PASS-analytic-source-boundary',model_sha256=sha(w/'model.blend'),pixel=[x,y],raw_dense_bvh_march_misses=1,ground_triangle=tri.polygon_index,world_intersection=point.tolist(),barycentric=[1-u-v,u,v],uv=uv.tolist(),actual_atlas_pixel=[px,py],packed=bool(img.packed_file),actual_linear_rgba=actual,expected_source_linear_rgba=expected,actual_source_rgb_preserved=True,owning_material=material.name,explanation='The source-visible ground is present analytically and its actual packed material stores the exact opaque source texel. An unsupported barrel base is less than 0.001 world units above this receiver in single-precision BVH output; advancing the skip ray by 0.001 passes through the ground. The raw dense-march discrepancy is retained and is not treated as a missing texture domain.',ray_trace=str(w/'inspection/single-pixel-ray-tie.json'))
(w/'inspection/analytic-source-boundary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
