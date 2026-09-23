"""Freeze the mission artwork and rebuild its stall and archery backstop."""
import argparse,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_slots import acquire
from freeze_tooling import select_tooling

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['prepare','modify','inspect','stored']);args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);acquire(slots=2)
 tools=select_tooling(W/'tooling/58744eeaf71a21e9')
 import bpy
 from refinement_workspace import prepare,modified
 old=W/'round-6/assets/nottingham-castle-yard-mission-props';new=W/'round-17/assets/nottingham-castle-yard-mission-props';audit=W/'environment-audit/custom1-props';audit.mkdir(parents=True,exist_ok=True)
 if args.operation=='prepare':
  if new.exists():raise FileExistsError(new)
  masks=json.loads((W/'mask-review/source-masks-v11-baseline.json').read_text());masks['mask_inventory']=str((W/'mask-review/inventory-v11-custom1-curtain/manifest.json').resolve())
  masks['projections']['exterior']['source_sha256']=sha(W/'source-states/nottingham-custom1.png')
  masks['projections']['exterior']['state']='Custom1 mission artwork with patch009 prop obstacles enabled'
  for a in masks['projections']['exterior']['assignments']:
   n=a.get('source_node')
   if n in [f'building-{i}'for i in range(547,551)]:
    i=int(n[-3:]);a.clear();a.update(source_node=n,mask_indices=[i-34]+([543]if i==548 else[]),reviewed=True,native_ownership_reviewed=True,constraint_kind='reviewed-native-silhouette'if i!=548 else'reviewed-authored-source-domain',review_note='Custom1 mission artwork; native prop silhouette combined with exact first-hit receiver. Native514 plus authored543 restores the dark curtain on548 only, excluding native foreground counter/vessels513 and canopy515. No Day paving projection; circular targets remain separate scenery.')
  authority=audit/'source-masks-custom1-curtain.json';authority.write_text(json.dumps(masks,indent=2)+'\n')
  bpy.ops.wm.open_mainfile(filepath=str(old/'baseline.blend'))
  prepare(new,asset_id='nottingham-castle-yard-mission-props',scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=W/'source-states/nottingham-custom1.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=authority,width=512,height=512,elevation_degrees=35,context_padding=32,framing_padding=1.24)
  raw=ROOT/'datadirs/fullgame_linux/Data/Levels/Custom1/Nottingham.map'
  proof=dict(raw_source=str(raw),raw_sha256=sha(raw),decoded_source=str(W/'source-states/nottingham-custom1.png'),decoded_sha256=sha(W/'source-states/nottingham-custom1.png'),dimensions=[2304,3520],mission='H07_Not_MK',ambiance=16,state='Custom1 with patch009 mission obstacles enabled',mask_indices=[513,514,515,516],authored_curtain_mask=543,authority_sha256=sha(authority),excluded_target_masks=[517,518,519],tooling=tools)
  (new/'source-provenance.json').write_text(json.dumps(proof,indent=2)+'\n');return
 bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'))
 if args.operation=='stored':
  from audit_stored_materials import run
  print(run(new,new/'inspection/stored-materials',render=True,export=True))
  return
 if args.operation=='inspect':
  from refinement_review import render_review
  from refinement_workspace import _review_layers
  config=json.loads((new/'workspace.json').read_text())
  for label,nodes in [('stall',[547,548,549]),('backstop',[550])]:
   names=[o.name for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('source_node')in[f'building-{n}'for n in nodes]]
   render_review(new/'inspection'/label,scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=config['asset_id'],source_path=config['source_path'],width=384,height=384,elevation_degrees=35,projection_layers=_review_layers(config),source_mask_manifest=config['source_mask_manifest'],render_object_names=names,framing_padding=1.08)
  return
 report=refine();once=mesh_shapes();refine();assert once==mesh_shapes();report['idempotent']=True
 (new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));result=modified(new);print(result)


def mesh_shapes():
 import bpy
 return {o.name:hashlib.sha256(json.dumps(dict(v=[list(v.co)for v in o.data.vertices],f=[list(f.vertices)for f in o.data.polygons],m=[list(r)for r in o.matrix_world]),sort_keys=True).encode()).hexdigest()for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}

def refine():
 import bpy,bmesh
 from mathutils import Vector
 s=math.sin(math.radians(35));c=math.cos(math.radians(35))
 native=json.loads((W/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
 import numpy as np
 canopy=native[549]['points']
 plane=np.linalg.lstsq(np.array([[p['x'],p['y'],1]for p in canopy]),np.array([p['z_top']for p in canopy]),rcond=None)[0]
 roof_targets=[(984,1007),(1073,1027),(1077,1039),(1060,1060),(961,1038)]
 roof_poly=[];roof_top=[]
 for x,source_y in roof_targets:
  y=float((source_y+plane[0]*x+plane[2])/(1-plane[1]));roof_poly.append((x,y));roof_top.append(y-source_y)
 # The recovered canopy pixels lie in front of the adjacent wall/roof, while
 # inherited collision slopes place its rear edge behind them. Solve only the
 # ambiguous depth: keep front posts fixed and raise/pull the rear cloth clear.
 # Equal native Y/Z offsets preserve every traced source pixel exactly.
 frontleft,frontright=roof_poly[4],roof_poly[3]
 def front_depth(x):return frontleft[1]+(x-frontleft[0])*(frontright[1]-frontleft[1])/(frontright[0]-frontleft[0])
 rear_ray_depth=[max(0,1.3*(front_depth(x)-y))for x,y in roof_poly]
 for i,distance in enumerate(rear_ray_depth):
  delta=distance*s*c;roof_poly[i]=(roof_poly[i][0],roof_poly[i][1]+delta);roof_top[i]+=delta
 before=mesh_shapes();reports=[]
 for n in range(547,551):
  obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('source_node')==f'building-{n}')
  points=native[n]['points'];verts=[];faces=[]
  def prism(poly,lo,hi):
   base=len(verts);count=len(poly)
   for heights in (lo,hi):
    for (x,y),z in zip(poly,heights if isinstance(heights,list)else[heights]*count):verts.append((x,-y/s,z/c))
   faces.extend([tuple(base+i for i in reversed(range(count))),tuple(base+count+i for i in range(count))])
   for i in range(count):j=(i+1)%count;faces.append((base+i,base+j,base+count+j,base+count+i))
  def extrusion(profile,delta):
   base=len(verts);count=len(profile)
   verts.extend(profile);verts.extend([tuple(Vector(v)+Vector(delta))for v in profile])
   faces.extend([tuple(base+i for i in reversed(range(count))),tuple(base+count+i for i in range(count))])
   for i in range(count):j=(i+1)%count;faces.append((base+i,base+j,base+count+j,base+count+i))
  def beam(a,b,width):
   a=Vector((a[0],-a[1]/s,a[2]/c));b=Vector((b[0],-b[1]/s,b[2]/c));axis=(b-a).normalized();side=axis.cross(Vector((0,0,1))).normalized()*width/2;up=axis.cross(side).normalized()*width/2
   extrusion([tuple(a+side+up),tuple(a-side+up),tuple(a-side-up),tuple(a+side-up)],b-a)
  poly=[(p['x'],p['y'])for p in points]
  if n==547:
   # Cloth-covered counter: top stays measured; bottom follows courtyard contact.
   prism(poly,100,[p['z_top']for p in points])
  elif n==548:
   # Continuous U-shaped side/back fabric shell, open at the counter front.
   backleft,backright,rightbend,frontright,frontleft=roof_poly
   inner=[(frontright[0]-2,frontright[1]),(rightbend[0]-2,rightbend[1]),(backright[0]-1,backright[1]+2),(backleft[0]+2,backleft[1]+2),(frontleft[0]+2,frontleft[1])]
   poly=[frontright]+inner+[frontleft,backleft,backright,rightbend]
   prism(poly,100,[roof_top[i]-3 for i in [3,3,2,1,0,4,4,0,1,2]])
   prism(roof_poly,100,101)
  elif n==549:
   # Fit the inherited roof slope, then solve the independently observed cloth
   # outline on that plane. Its rear-right bevel excludes neighboring shingles.
   poly=roof_poly;top=roof_top
   prism(poly,[z-3 for z in top],top)
   # The native canopy mask gives the scalloped boundary, not a flat lintel.
   from PIL import Image
   mask=Image.open(W/'mask-review/inventory-v11/000515.png').convert('L')
   edge=[]
   for x in range(960,1054):
    hits=[y+1006 for y in range(mask.height)if mask.getpixel((x-958,y))>127]
    edge.append((x,max(hits)+.5))
   edge.extend([(1055,1073),(1058,1077),(1061,1073)])
   left,right=poly[4],poly[3]
   def depth(x):return left[1]+(x-left[0])*(right[1]-left[1])/(right[0]-left[0])
   def valance_top(x):return roof_top[4]+(x-left[0])*(roof_top[3]-roof_top[4])/(right[0]-left[0])-2.8
   profile=[(edge[0][0],-depth(edge[0][0])/s,valance_top(edge[0][0])/c),(edge[-1][0],-depth(edge[-1][0])/s,valance_top(edge[-1][0])/c)]
   profile.extend((x,-depth(x)/s,(depth(x)-y)/c)for x,y in reversed(edge))
   extrusion(profile,(0,1.2,0))
  else:
   prism(poly,100,[p['z_top']for p in points])
   # Two triangular foot braces continue behind the boards; only the near foot
   # is fully observed, with the far support constrained by the same structure.
   for x,y in [(375.2,1447.8),(439.3,1356.3)]:
    beam((x-25,y-6,102),(x,y,130),3)
    beam((x-43,y-10.5,101),(x+6,y+1.5,101),3)
  mesh=bpy.data.meshes.new(f'Custom1 prop {n}');inv=obj.matrix_world.inverted();mesh.from_pydata([inv@Vector(v)for v in verts],[],faces);mesh.update()
  for mat in obj.data.materials:mesh.materials.append(mat)
  mesh.uv_layers.new(name='UVMap');bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();obj.data=mesh
  bm=bmesh.new();bm.from_mesh(mesh);report=dict(source_node=f'building-{n}',nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),degenerate_faces=sum(f.calc_area()<1e-8 for f in bm.faces),signed_volume=bm.calc_volume(signed=True),vertices=len(mesh.vertices),faces=len(mesh.polygons));bm.free();assert report['nonmanifold_edges']==0 and report['degenerate_faces']==0
  if n==549:
   topverts=[obj.matrix_world@mesh.vertices[i].co for i in range(5,10)];normal=(topverts[1]-topverts[0]).cross(topverts[2]-topverts[0]).normalized();error=max(abs((v-topverts[0]).dot(normal))for v in topverts)
   assert error<.001,error
   report.update(top_planarity_max_world_deviation=error,front_valance_count=1,valance_minimum_native_elevation=min((obj.matrix_world@v.co).z*c for v in list(mesh.vertices)[10:]),rear_depth_ray_distances=rear_ray_depth)
  reports.append(report)
 after=mesh_shapes();changed=[n for n in before if before[n]!=after[n]];allowed={o.name for o in bpy.data.collections['nottingham Working'].all_objects if o.get('source_node')in[f'building-{i}'for i in range(547,551)]};assert set(changed)<=allowed
 return dict(version=1,objects=reports,changed_objects=changed,outside_objects_unchanged=True,source_ground_contact='Native elevation100, constrained by visible courtyard feet; hidden contact inferred.',recipe_sha256=sha(__file__))
if __name__=='__main__':main()
