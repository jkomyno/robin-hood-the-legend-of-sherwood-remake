"""Measured curved drum, conical roof, metal finial and tower apertures."""
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).resolve().parent))

def geometry(obj,vertices,faces):
 from mathutils import Vector
 from refine_castle_secondary import replace_mesh
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));inv=obj.matrix_world.inverted()
 return replace_mesh(obj,[inv@Vector((x,-y/s,z/c)) for x,y,z in vertices],faces)

def lathe(profile,start=0,end=math.tau,segments=64):
 # Profile follows outside from bottom to top, then inside down to bottom.
 full=abs(end-start-math.tau)<1e-6;n=segments if full else segments+1
 verts=[(1348.15+rx*math.cos(start+(end-start)*i/segments),1284.705+ry*math.sin(start+(end-start)*i/segments),z) for rx,ry,z in profile for i in range(n)]
 faces=[]
 for row in range(len(profile)-1):
  for i in range(segments):
   j=(i+1)%n;faces.append((row*n+i,row*n+j,(row+1)*n+j,(row+1)*n+i))
 faces.extend([tuple(reversed(range(n))),tuple((len(profile)-1)*n+i for i in range(n))])
 if not full:
  faces.extend([tuple(row*n for row in range(len(profile))),tuple(reversed([row*n+n-1 for row in range(len(profile))]))])
 # Partial profiles already close through endpoints; their end caps use the
 # complete cross section and the first/last profile rings need radial caps.
 if not full:
  faces=faces[:-4]+[tuple(row*n for row in range(len(profile))),tuple(reversed([row*n+n-1 for row in range(len(profile))]))]
  for i in range(segments):faces.append((i,(len(profile)-1)*n+i,(len(profile)-1)*n+i+1,i+1))
 return verts,faces

def recess(obj,points,name):
 import bpy
 from mathutils import Vector
 from refine_castle_secondary import replace_mesh
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));verts=[]
 for depth in [2,-6]:
  for x,source_y in points:
   y=1284.705+46.09*math.sqrt(max(0,1-((x-1348.15)/72.47)**2))+depth
   verts.append(Vector((x,-y/s,(y-source_y)/c)))
 n=len(points);faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);cut=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(cut)
 # Recalculate cutter normals through the same topology-checked helper.
 replace_mesh(cut,verts,faces)
 bpy.context.view_layer.objects.active=obj;mod=obj.modifiers.new(name,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut
 bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)

def apply(workspace):
 import bpy,bmesh
 from refinement_workspace import _geometry,modified
 from refine_castle_secondary import sha,write
 config=json.loads((workspace/'workspace.json').read_text());objects=list(bpy.data.collections[config['collection_name']].all_objects)
 targets={int(o['source_node'][9:]):o for o in objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']}
 before={o.name:_geometry(o) for o in objects};mat={o.name:tuple(v for row in o.matrix_world for v in row) for o in objects};changes=[]
 body=targets[354]
 profile=[(72.47,46.09,0),(72.47,46.09,246),(73.97,47.04,247),(73.97,47.04,250),(72.47,46.09,251),(72.47,46.09,255),(74.47,47.36,256),(74.47,47.36,258),(72.47,46.09,259),(72.47,46.09,325),(74.47,47.36,326),(74.47,47.36,328),(73.47,46.73,330.295)]
 geometry(body,*lathe(profile))
 for pts,name in [([(1325,1035),(1325,1010),(1328,1006),(1336,1006),(1339,1010),(1339,1035)],'west upper opening'), ([(1376,1027),(1376,1005),(1379,1001),(1385,1000),(1389,1004),(1389,1027)],'east upper opening'), ([(1348,1121),(1348,1100),(1352,1100),(1352,1121)],'lower arrow slit')]:recess(body,pts,name)
 # Preserve five roof part identities; round their arc while sharing one profile.
 angles=[math.atan2(p['y']-1284.705,p['x']-1348.15) for p in json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][354]['points']]
 for number,a,b in [(355,angles[0],angles[1]),(358,angles[1],angles[2]),(359,angles[2],angles[4]),(357,angles[4],angles[6]),(356,angles[6],angles[0])]:
  if b<a:b+=math.tau
  roof=[(74.47,47.36,330.295),(14.5,9.22,393),(13.5,8.59,393),(73.47,46.73,329.295)]
  geometry(targets[number],*lathe(roof,a,b,max(8,round((b-a)/math.tau*96))))
 # Stacked cap, teardrop, sphere, rod and tapered spike measured in source pixels.
 # The axial centre is x1348.15/source depth1284.705; height=depth-source-y.
 profile=[(14.5,9.22,393),(11,7,398),(6.5,4.13,406),(4.8,3.05,408),(5.8,3.69,412),(4.9,3.12,418),(1.2,.76,424),(1.2,.76,425),(3.8,2.42,426),(4.5,2.86,430),(3.3,2.10,433),(1.0,.64,434),(1.0,.64,450),(3.0,1.91,450),(.25,.16,467)]
 v,f=lathe(profile)
 # Keep finial under an existing owned roof part without creating a new receiver.
 obj=targets[355];from mathutils import Vector
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));inv=obj.matrix_world.inverted();old=[tuple(o.co) for o in obj.data.vertices];faces=[tuple(p.vertices) for p in obj.data.polygons];offset=len(old)
 from refine_castle_secondary import replace_mesh
 replace_mesh(obj,old+[inv@Vector((x,-y/s,z/c)) for x,y,z in v],faces+[tuple(offset+i for i in face) for face in f])
 for n,obj in targets.items():
  bm=bmesh.new();bm.from_mesh(obj.data);bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);bm.free();assert bad==deg==0,(n,bad,deg)
  obj['castle_round_tower_recipe']='measured-round-profile-v1'
  changes.append({'source_node':obj['source_node'],'nonmanifold_edges':bad,'degenerate_faces':deg,'before_sha256':before[obj.name],'after_sha256':_geometry(obj)})
 assert all(_geometry(o)==before[o.name] for o in objects if o not in targets.values())
 assert all(tuple(v for row in o.matrix_world for v in row)==mat[o.name] for o in objects)
 write(workspace/'round-tower-report.json',{'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),'changes':changes,'source_evidence':'castle-audit/round-tower-measure.png','inference':'Rear ellipse follows measured native footprint extents; blind recess depths and concealed continuations are inferred.'})
 from refine_castle_packets import apply_masks
 apply_masks(workspace,WORK/'mask-review/castle-secondary-overrides-v11.json')
 bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));modified(workspace)

if __name__=='__main__':
 from freeze_tooling import select_tooling
 select_tooling()
 from render_slots import acquire
 acquire()
 import bpy
 w=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else WORK/'round-5/assets/nottingham-castle-east-round-tower'
 bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));apply(w)
