"""Check source-visible roof coverage when separating masonry authority."""
import bpy,json,math,sys,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement';A='nottingham-village-dovecote';out=W/'round-50/assets'/A
S=math.sin(math.radians(35));C=math.cos(math.radians(35));toward=Vector((0,-C,S));snapshots={}
def tree(path,roof_only=False):
 bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();vs=[];ts=[];owners=[]
 if str(path)not in snapshots:
  snapshots[str(path)]={o.name:hashlib.sha256(json.dumps(dict(vertices=[list(o.matrix_world@v.co)for v in o.data.vertices],faces=[list(f.vertices)for f in o.data.polygons]),sort_keys=True).encode()).hexdigest()for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
 for o in bpy.data.collections['nottingham Working'].all_objects:
  if o.type!='MESH' or o.hide_render or o.get('asset_group')!=A:continue
  if roof_only and o.get('source_node')not in [f'building-{n}'for n in range(294,300)]:continue
  o.data.calc_loop_triangles()
  for t in o.data.loop_triangles:
   ts.append(tuple(range(len(vs),len(vs)+3)));vs.extend(o.matrix_world@o.data.vertices[i].co for i in t.vertices);owners.append(o.get('source_node'))
 return vs,ts,owners
def cast(t,x,y):return t.ray_cast(Vector((x,-y*S,-y*C))+toward*10000,-toward)
def main():
 ov,ot,owners=tree(W/'round-24/assets'/A/'model.blend');nv,nt,nowners=tree(out/'model.blend');rv,rt,_=tree(out/'model.blend',True);old=BVHTree.FromPolygons(ov,ot,all_triangles=True);new=BVHTree.FromPolygons(nv,nt,all_triangles=True);roof=BVHTree.FromPolygons(rv,rt,all_triangles=True)
 from mathutils.kdtree import KDTree
 from collections import Counter
 kd=KDTree(len(rv))
 for i,p in enumerate(rv):kd.insert(p,i)
 kd.balance();weld={i:min(j for _,j,_ in kd.find_range(p,.002))for i,p in enumerate(rv)};edges=Counter();degenerate=0
 for a,b,c in rt:
  q=[weld[a],weld[b],weld[c]];degenerate+=int(len(set(q))<3 or (rv[b]-rv[a]).cross(rv[c]-rv[a]).length<1e-8)
  for a,b in zip(q,q[1:]+q[:1]):edges[tuple(sorted((a,b)))]+=1
 assert max(p.z for p in rv)<=240.671
 assert min((p-Vector((2113.12,-5380.54,240.67))).length for p in rv)<.001
 roof_topology=dict(apex_preserved=True,maximum_world_z=max(p.z for p in rv),triangles=len(rt),degenerate_triangles=degenerate,nonmanifold_edges=sum(n!=2 for n in edges.values()),weld_tolerance=.002)
 assert not degenerate and not roof_topology['nonmanifold_edges'],roof_topology
 invp=Path(json.loads((out/'source-masks.json').read_text())['mask_inventory']);inv=json.loads(invp.read_text());r=next(r for r in inv['masks']if r['index']==260);native=Image.new('L',(2304,3520));native.paste(Image.open(invp.parent/r['png']).convert('L'),tuple(r['box_top_left'][:2]));mask=Image.open(W/'dovecote-projection-audit/wall-authority-v7/painted-masonry-native260.png').convert('L');counts={};misses=[];changed=[]
 for y in range(2850,3180):
  for x in range(2000,2230):
   if not native.getpixel((x,y)):continue
   hit,n,i,d=cast(old,x+.5,y+.5)
   if i is None:continue
   owner=owners[i];nh,nn,ni,nd=cast(new,x+.5,y+.5)
   key='old_'+owner;counts[key]=counts.get(key,0)+1
   if not mask.getpixel((x,y)) and owner=='building-293':
    rh,rn,ri,rd=cast(roof,x+.5,y+.5);key='removed_body_covered_by_roof'if ri is not None else'removed_body_without_roof';counts[key]=counts.get(key,0)+1;changed.append([x,y,ri is not None])
    if ri is None:misses.append([x,y])
 import runpy
 recipe=runpy.run_path(str(Path(__file__).with_name('refine_dovecote_projection_boundary.py')),run_name='audit_constants');body=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==A and o.get('source_node')=='building-293');ring=[body.matrix_world@v.co for v in list(body.data.vertices)[56:112]];rim=[]
 for j,p in enumerate(ring):
  target=p.copy();target.x=recipe['RIM_X'].get(j,p.x);target.y-=recipe['RIM_SOURCE_Y_OFFSET'].get(j,0)/S;actual=min(rv,key=lambda q:(q-target).length);assert (actual-target).length<.003,(j,(actual-target).length);rim.append(dict(index=j,old_source=[p.x,-p.y*S-p.z*C],actual_source=[actual.x,-actual.y*S-actual.z*C],construction_residual=(actual-target).length))
 source=Image.open(out/'reference/source.png').convert('RGB');box=(2010,2920,2220,3170);overlay=source.crop(box).resize((840,1000),Image.Resampling.NEAREST);draw=ImageDraw.Draw(overlay);display=lambda q:((q[0]-box[0])*4,(q[1]-box[1])*4)
 for key,color in [('old_source','red'),('actual_source','cyan')]:draw.line([display(r[key])for r in rim+[rim[0]]],fill=color,width=2)
 overlay.save(out/'inspection/saved-roof-outline.png');(out/'inspection/saved-roof-outline.json').write_text(json.dumps(dict(rim=rim,manual_uncertainty_pixels=2),indent=2)+'\n')
 im=Image.open(out/'reference/source.png').convert('RGB');d=ImageDraw.Draw(im)
 for x,y,covered in changed:d.point((x,y),fill=(0,255,255)if covered else(255,0,0))
 im.crop((2010,2920,2220,3170)).resize((840,1000),Image.Resampling.NEAREST).save(out/'inspection/body-authority-source-coverage.png')
 old_snapshot=snapshots[str(W/'round-24/assets'/A/'model.blend')];new_snapshot=snapshots[str(out/'model.blend')];changed_objects=[n for n in old_snapshot if old_snapshot[n]!=new_snapshot[n]];assert all('continuous thatch roof'in n for n in changed_objects),changed_objects
 classes={}
 for x,y in misses:
  label='traced-left-background'if x<2040 and y>=3011 else 'left-thatch-boundary'if x<2040 else 'right-background-fleck-or-boundary'if x>=2200 else 'front-thatch-boundary'
  classes.setdefault(label,[]).append([x,y])
 report=dict(rejected_source_classification=classes,roof_topology=roof_topology,saved_geometry_changed_objects=changed_objects,unchanged_mesh_count=len(old_snapshot)-len(changed_objects),model_sha256=hashlib.sha256((out/'model.blend').read_bytes()).hexdigest(),counts=counts,removed_body_without_roof=misses,interpretation='Cyan old source-visible body pixels now owned by actual roof; red require source classification before readiness.')
 (out/'inspection/body-authority-source-coverage.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
 sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
 from render_source_atlas_crop import render
 for o in bpy.data.objects:
  if o.type=='MESH' and (o.get('asset_group')!=A or o.get('source_node')not in [f'building-{i}'for i in range(293,302)]):o.hide_render=True
 bpy.context.view_layer.update();render('nottingham Working',(2000,2850,2230,3190),out/'inspection/actual-source-materials.png')
 source=Image.open(out/'reference/source.png').convert('RGB').crop((2000,2850,2230,3190));actual=Image.open(out/'inspection/actual-source-materials.png').convert('RGB');pair=Image.new('RGB',(460,340));pair.paste(source,(0,0));pair.paste(actual,(230,0));pair.resize((920,680),Image.Resampling.NEAREST).save(out/'inspection/source-comparison.png')
def full_native():
 vs,ts,owners=tree(out/'model.blend');mesh=BVHTree.FromPolygons(vs,ts,all_triangles=True);ip=Path(json.loads((out/'source-masks.json').read_text())['mask_inventory']);r=next(r for r in json.loads(ip.read_text())['masks']if r['index']==260);mask=Image.open(ip.parent/r['png']).convert('L');ox,oy=r['box_top_left'][:2];missing=[];counts={};native_count=0
 for y in range(mask.height):
  for x in range(mask.width):
   if not mask.getpixel((x,y)):continue
   native_count+=1;hit,n,i,d=cast(mesh,x+ox+.5,y+oy+.5)
   if i is None:missing.append([x+ox,y+oy])
   else:counts[owners[i]]=counts.get(owners[i],0)+1
 source=Image.open(out/'reference/source.png').convert('RGB');marked=source.copy();draw=ImageDraw.Draw(marked)
 for x,y in missing:draw.point((x,y),fill='magenta')
 box=(2000,2850,2230,3200);pair=Image.new('RGB',(460,350));pair.paste(source.crop(box),(0,0));pair.paste(marked.crop(box),(230,0));pair.resize((920,700),Image.Resampling.NEAREST).save(out/'inspection/full-native-domain-rejections.png')
 from PIL import ImageFilter,ImageChops
 roof=BVHTree.FromPolygons(vs,[t for t,o in zip(ts,owners)if o in [f'building-{i}'for i in range(294,300)]],all_triangles=True);silhouette=Image.new('L',(230,350));sd=ImageDraw.Draw(silhouette)
 for y in range(2850,3200):
  for x in range(2000,2230):
   if cast(roof,x+.5,y+.5)[2]is not None:sd.point((x-2000,y-2850),fill=255)
 edge=ImageChops.subtract(silhouette,silhouette.filter(ImageFilter.MinFilter(3)));overlay=source.crop(box);overlay.paste((0,255,255),(0,0),edge);pair=Image.new('RGB',(460,350));pair.paste(source.crop(box),(0,0));pair.paste(overlay,(230,0));pair.resize((920,700),Image.Resampling.NEAREST).save(out/'inspection/actual-roof-silhouette.png')
 report=dict(model_sha256=hashlib.sha256((out/'model.blend').read_bytes()).hexdigest(),native_index=260,native_positive_pixels=native_count,receiver_counts=counts,no_receiver_pixels=missing,domain='Every positive pixel of native260, including its complete recorded bounding box; independent of revised acceptance mask.')
 (out/'inspection/full-native-domain-rejections.json').write_text(json.dumps(report,indent=2)+'\n');print('FULL_NATIVE',native_count,len(missing),counts)
if __name__=='__main__':
 if '--full-native'in sys.argv:full_native()
 else:main()
