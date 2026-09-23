"""Read actual saved material atlas samples at disputed composite ray hits."""
import bpy,sys,json,math,hashlib,collections
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['31','33','composite-final33'];pair=WORK/f'round-{int(args[0])}/assets/nottingham-southwest-curtain-wall-north/inspection'/args[2];stair=WORK/f'round-{int(args[1])}/assets/nottingham-southwest-wall-stair';bpy.ops.wm.open_mainfile(filepath=str(pair/'model.blend'));cfg=json.load(open(pair/'workspace.json'));obs=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH'and not o.hide_render and o.get('asset_group')==cfg['asset_id']];verts=[];triangles=[];data=[]
for o in obs:
 o.data.calc_loop_triangles()
 for tri in o.data.loop_triangles:
  points=[o.matrix_world@o.data.vertices[v].co for v in tri.vertices];triangles.append(tuple(range(len(verts),len(verts)+3)));verts+=points;data.append((o,tri,points))
tree=BVHTree.FromPolygons(verts,triangles,all_triangles=True);rows=json.load(open(stair/'inspection/independent-native135/audit.json'))['rows'];rows=[r for r in rows if r['first_node']=='building-220'and not r['first_native_allowed']];s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));counts=collections.Counter();cache={};out=[]
for r in rows:
 x,y=r['pixel'];origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,d=tree.ray_cast(origin,-toward);o,tri,points=data[i];mat=o.data.materials[tri.material_index];ims=[node.image for node in mat.node_tree.nodes if node.type=='TEX_IMAGE'and node.image]if mat.use_nodes else [];samples=[]
 for im in ims:
  if im.name not in cache:cache[im.name]=list(im.pixels)
  uvnodes=[n for n in mat.node_tree.nodes if n.type=='UVMAP'];layer=o.data.uv_layers[uvnodes[0].uv_map]if uvnodes else o.data.uv_layers.active;uv=[Vector((*layer.data[l].uv,0))for l in tri.loops];point=barycentric_transform(hit,*points,*uv);ix=min(im.size[0]-1,max(0,int(point.x*im.size[0])));iy=min(im.size[1]-1,max(0,int(point.y*im.size[1])));p=(iy*im.size[0]+ix)*4;rgba=cache[im.name][p:p+4];samples.append(dict(image=im.name,rgba=rgba))
 known=any(max(q['rgba'][:3])-min(q['rgba'][:3])>1/255 for q in samples);counts['source-colored'if known else 'neutral-gray']+=1;out.append(dict(pixel=r['pixel'],first_node=o.get('source_node'),material=mat.name,samples=samples,known=known))
report=dict(classification='Achromatic samples identify neutral-gray material; opacity alone does not establish source ownership.',composite_model_sha256=hashlib.sha256((pair/'model.blend').read_bytes()).hexdigest(),counts=dict(counts),rows=out);(pair/'independent-144-atlas.json').write_text(json.dumps(report,indent=2)+'\n');print(dict(counts));print(out[:2])
