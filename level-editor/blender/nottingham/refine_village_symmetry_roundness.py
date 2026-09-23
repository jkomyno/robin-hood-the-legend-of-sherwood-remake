"""Center the forge flue and round the dovecote's measured perimeter."""
import hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def chimney():
 import bpy
 from mathutils import Vector
 from refine_village_secondary import native,point,replace
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')=='nottingham-village-small-hut' and o.get('source_node')=='building-284')
 pts=native(284);base=[point(p,36) for p in pts]
 u=(base[1]-base[0]).normalized();v=Vector((-u.y,u.x,0))
 top_z=102.381004/C;center=Vector((407.75,(-2760-top_z*C)/S,0))
 # Identical vertical axis at every height. Orthogonal horizontal rings have
 # opposite corners mirrored exactly, including the lower flared hood.
 def ring(z,a,b):return [center+u*x*a+v*y*b+Vector((0,0,z)) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
 bottom=ring(36/C,(base[1]-base[0]).length/2,(base[3]-base[0]).length/2)
 middle=ring(top_z-25/C,9.5,11.5);top=ring(top_z,6.1,7.6)
 inner=ring(top_z,6.1*.66,7.6*.66);lower=[p-Vector((0,0,5)) for p in inner]
 verts=bottom+middle+top+inner+lower;faces=[(3,2,1,0),(16,17,18,19)]
 for i in range(4):
  j=(i+1)%4;faces.extend([(i,j,4+j,4+i),(4+i,4+j,8+j,8+i),(8+i,8+j,12+j,12+i),(12+i,12+j,16+j,16+i)])
 report=replace(obj,verts,faces,'Forge chimney / centered symmetric hood and shaft');obj['projection_min_cosine']=.05
 report.update(vertical_center_world=list(center),symmetry_max_error=max(((verts[k]+verts[k+2])/2-center-Vector((0,0,verts[k].z))).length for k in [0,4,8,12,16]),changes=['All five chimney rings share one vertical center; opposed walls and hood shoulders are symmetric.','The shaft remains open and the lower hood closes below the roof intersection.'],limitations=['Hidden chimney returns and the shallow flue recess are inferred. Manual silhouette observations have approximately two-pixel uncertainty.'])
 return report

def dovecote():
 import bpy,bmesh
 from mathutils import Vector
 from refine_village_secondary import native,point,replace
 from refine_village import _mesh
 objs={o.get('source_node'):o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')=='nottingham-village-dovecote'}
 anchors=[point(p,112.91701) for p in native(293)];ring=[]
 # Periodic Catmull-Rom follows every observed native contour anchor. The
 # interpolation rounds the old chords without replacing the irregular source
 # silhouette by a guessed perfect circle.
 for i in range(7):
  p0,p1,p2,p3=[anchors[k%7] for k in [i-1,i,i+1,i+2]]
  for j in range(8):
   t=j/8;ring.append((p1*2+(p2-p0)*t+(p0*2-p1*5+p2*4-p3)*t*t+(-p0+p1*3-p2*3+p3)*t*t*t)/2)
 n=len(ring);bodybottom=[Vector((p.x,p.y,0)) for p in ring]
 faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 report=replace(objs['building-293'],bodybottom+ring,faces,'Dovecote / rounded masonry shell')
 apex=Vector((2113.12,-5380.54,240.67));verts=[apex];faces=[]
 for k in range(1,6):
  t=k/5
  for p in ring:verts.append(apex.lerp(p,t)+Vector((0,0,3*4*t*(1-t))))
 for j in range(n):faces.append((0,1+j,1+(j+1)%n))
 for k in range(4):
  for j in range(n):a=1+k*n+j;b=1+k*n+(j+1)%n;faces.append((a,b,b+n,a+n))
 start=len(verts);verts.extend(p-Vector((0,0,3)) for p in ring)
 for j in range(n):faces.append((1+4*n+j,1+4*n+(j+1)%n,start+(j+1)%n,start+j))
 faces.append(tuple(reversed(range(start,start+n))))
 mesh,valid=_mesh('Dovecote / rounded continuous thatch roof',verts,faces)
 nodes=[f'building-{i}' for i in range(294,300)]
 centers={node:sum([point(p,p['z_top']) for p in native(int(node.split('-')[1]))],Vector())/3 for node in nodes}
 buckets={node:[] for node in nodes}
 for f in mesh.polygons:
  owner=min(nodes,key=lambda node:(f.center.x-centers[node].x)**2+(f.center.y-centers[node].y)**2);buckets[owner].append(f.index)
 for node,indices in buckets.items():
  assert indices,node
  obj=objs[node];copy=mesh.copy();bm=bmesh.new();bm.from_mesh(copy);bm.faces.ensure_lookup_table();wanted=set(indices);bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in wanted],context='FACES');bm.to_mesh(copy);bm.free()
  inverse=obj.matrix_world.inverted()
  for vertex in copy.vertices:vertex.co=inverse@vertex.co
  for mat in obj.data.materials:copy.materials.append(mat)
  obj.data=copy
 report.update(radial_segments=n,source_anchor_count=7,roof_aggregate_validation=valid,changes=['Replaced seven straight wall/roof chords with a 56-segment smooth perimeter through the measured anchors.','Kept the roof apex, eave height, shallow thatch curvature, door landing and all stair geometry.'],limitations=['Curvature between observed anchors and the concealed rear contour are interpolated; no new source pixels or details are invented.','Six canonical roof receivers meet along shared aggregate-shell seams.'])
 return report

def evidence(workspace,asset):
 import bpy
 from PIL import Image,ImageDraw
 source=Image.open(workspace/'reference/source.png').convert('RGB')
 hut=asset.endswith('small-hut');box=(340,2735,470,2920) if hut else (2000,2850,2225,3190)
 crop=source.crop(box).resize(((box[2]-box[0])*3,(box[3]-box[1])*3),Image.Resampling.NEAREST);draw=ImageDraw.Draw(crop)
 node='building-284' if hut else 'building-293'
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==asset and o.get('source_node')==node)
 world=[obj.matrix_world@v.co for v in obj.data.vertices]
 rings=[[world[i] for i in range(start,start+4)] for start in (4,8)] if hut else [world[56:112]]
 project=lambda p:(p.x,-p.y*S-p.z*C)
 display=lambda p:((p[0]-box[0])*3,(p[1]-box[1])*3)
 for ring in rings:
  pixels=[project(p) for p in ring];draw.line([display(p) for p in pixels+[pixels[0]]],fill=(0,255,255),width=2)
  if hut:
   for i,p in enumerate(pixels):draw.text(display(p),str(i+1),fill=(255,0,0))
 if not hut:
  for i in range(7):
   p=display(project(world[56+i*8]));draw.ellipse((p[0]-3,p[1]-3,p[0]+3,p[1]+3),fill=(255,0,0));draw.text((p[0]+4,p[1]),str(i+1),fill=(255,0,0))
 target=workspace/'inspection';target.mkdir(exist_ok=True)
 crop.save(target/'source-mesh-contours.png')
 write(target/'source-mesh-contours.json',dict(source_sha256=sha(workspace/'reference/source.png'),model_sha256=sha(workspace/'model.blend'),source_node=node,actual_mesh_rings=[list(map(project,r)) for r in rings],meaning='Cyan actual saved-mesh ring edges; red numbers identify chimney corners or retained dovecote perimeter anchors. Not an independent fit score.'))

def main():
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,refinement_workspace as rw
 from refine_village_secondary import digest
 asset=sys.argv[sys.argv.index('--')+1];hut=asset.endswith('small-hut');old=WORK/f'round-{21 if hut else 1}/assets'/asset;new=WORK/'round-23/assets'/asset
 cfg=json.loads((old/'workspace.json').read_text())
 if not new.exists():
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=asset,scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=384,height=448,context_padding=48,framing_padding=1.15)
 bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'));bpy.context.view_layer.update()
 def snap():return {o.name:(digest(o),[list(row) for row in o.matrix_world]) for o in bpy.context.scene.objects if o.type=='MESH'}
 before=snap();refine=chimney if hut else dovecote;report=refine();after=snap();outside=[k for k in before if before[k]!=after[k] and bpy.data.objects[k].get('asset_group')!=asset];assert not outside,outside
 refine();assert after==snap(),'Non-idempotent recipe'
 report.update(asset_id=asset,previous_workspace=str(old),tooling=tooling,idempotence='PASS',outside_objects_preserved=sum(o.type=='MESH' and o.get('asset_group')!=asset for o in bpy.context.scene.objects),recipe_sha256=sha(__file__))
 write(new/'geometry-report.json',report);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));rw.modified(new);evidence(new,asset)
 write(new/'candidate.json',dict(version=1,asset_id=asset,status='refinement-in-progress',model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'),recipe=str(Path(__file__).resolve())))
if __name__=='__main__':main()
