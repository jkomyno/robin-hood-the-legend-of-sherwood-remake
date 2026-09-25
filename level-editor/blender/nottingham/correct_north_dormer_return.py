"""Prepare an isolated dormer source-receiver candidate for renewed user review.

No approved pointers or generation inputs are modified. The candidate needs
independent visual/source review after the exact coverage and material audits.
"""
import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
def build_domain(old):
 """Retain native inventories and append the source-classified house domain."""
 from PIL import Image,ImageChops,ImageDraw
 root=WORK/'coordinator-audit/north-dormer-stripe/domain-v6';out=root/'source-masks.json'
 if out.exists():return out
 root.mkdir(parents=True);m=json.loads((old/'source-masks.json').read_text());ip=Path(m['mask_inventory']);inv=json.loads(ip.read_text());dest=root/'inventory';dest.mkdir()
 for row in inv['masks']:shutil.copy2(ip.parent/row['png'],dest/row['png'])
 def native(k):
  row=inv['masks'][k];im=Image.new('L',(2304,3520));im.paste(Image.open(ip.parent/row['png']).convert('L'),tuple(row['box_top_left']));return im
 mask=ImageChops.lighter(native(79),ImageChops.lighter(native(83),native(84)));mask=ImageChops.subtract(mask,ImageChops.lighter(native(525),native(526)));ImageDraw.Draw(mask).rectangle((0,540,2303,3519),fill=0);idx=len(inv['masks']);name=f'{idx:06d}.png';mask.save(dest/name)
 inv['masks'].append(dict(index=idx,layer=-1,layer_index=idx,png=name,mask_type=0,box_top_left=[0,0],box_size=[2304,3520],character_polyline=None,projectile_polyline=None,obstacle_indices=[],authored=True,description='House domain excluding separately owned storage525/526 and foreground below y540.'))
 (dest/'manifest.json').write_text(json.dumps(inv,indent=2)+'\n');m['mask_inventory']=str(dest/'manifest.json')
 for projection in m['projections'].values():
  for assignment in projection['assignments']:
   if assignment['source_node'] in ['building-122','building-123','building-124','building-125']:
    assignment['mask_indices']=[idx];assignment['review_note']='Valid house retained; storage525/526 and lower foreground excluded.'
 out.write_text(json.dumps(m,indent=2)+'\n');return out
def apply():
 import bpy,bmesh
 from mathutils import Vector
 objects={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.get('asset_group')=='nottingham-north-dormer-house'}
 roof=objects['building-123'];body=objects['building-122'];rv=[roof.matrix_world@v.co for v in roof.data.vertices];down=Vector((0,-.573576436351046,-.819152044288992));toward=Vector((0,-.819152044288992,.573576436351046));a,b,c=[rv[i]for i in [4,5,6]];normal=(b-a).cross(c-a).normalized()
 def plane_point(x,y):
  p=Vector((x,0,0))+down*y;return p+toward*(normal.dot(a-p)/normal.dot(toward))
 top=[rv[4],rv[5]]+[plane_point(x,y)for x,y in [(1782.5,480),(1791.5,454),(1797.5,433),(1799.5,414)]];n=len(top);bottom=[v-Vector((0,0,2))for v in top]
 for p in bottom[2:]:p.x-=.75
 faces=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)]
 def replace(o,verts,polys):
  mesh=bpy.data.meshes.new(o.name+' / corrected return');mesh.from_pydata([o.matrix_world.inverted()@v for v in verts],[],polys);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);bm.to_mesh(mesh);bm.free()
  for m in o.data.materials:mesh.materials.append(m)
  mesh.uv_layers.new(name='UVMap');o.data=mesh
 oldv=[roof.matrix_world@v.co for v in roof.data.vertices];oldf=[tuple(f.vertices)for f in roof.data.polygons];n=len(oldv);replace(roof,oldv+top+bottom,oldf+[tuple(i+n for i in f)for f in faces])
 bv=[body.matrix_world@v.co for v in body.data.vertices];foot=[Vector((1794,bv[0].y,0)),Vector((1794,-1000,0)),bv[1].copy(),bv[2].copy(),bv[3].copy()];upper=[]
 for p in foot:
  p.z=68
  q=p.copy();q.z=a.z-(normal.x*(q.x-a.x)+normal.y*(q.y-a.y))/normal.z-2.25;upper.append(q)
 faces=[tuple(range(4,-1,-1)),tuple(range(5,10))]+[(i,(i+1)%5,(i+1)%5+5,i+5)for i in range(5)];replace(body,foot+upper,faces)
 board=objects['building-553']
 vv=[board.matrix_world@v.co for v in board.data.vertices];ba,bb,bc=[vv[i]for i in [4,7,6]];bn=(bb-ba).cross(bc-ba).normalized()
 for i,(sx,sy) in enumerate([(1791,514),(1771,548),(1755.5,537.5),(1775,501.5)]):
  q=Vector((sx,0,0))+down*sy;vv[i+4]=q+toward*(bn.dot(ba-q)/bn.dot(toward));vv[i]=vv[i+4]-Vector((0,0,2))
 replace(board,vv,[tuple(f.vertices)for f in board.data.polygons])
 # The facade recess follows only the independently owned board source domain.
 from PIL import Image
 from mathutils.geometry import tessellate_polygon
 manifest=json.loads((WORK/'round-38/assets/nottingham-north-dormer-house/source-masks.json').read_text());ip=Path(manifest['mask_inventory']);inv=json.loads(ip.read_text());row=next(r for r in inv['masks']if r['index']==526);im=Image.open(ip.parent/row['png']).convert('L');ox,oy=row['box_top_left'];occupied={(x+ox,y+oy)for y in range(im.height)for x in range(im.width)if im.getpixel((x,y))>127};edges={}
 for x,y in occupied:
  for neighbor,u,v in [((x,y-1),(x,y),(x+1,y)),((x+1,y),(x+1,y),(x+1,y+1)),((x,y+1),(x+1,y+1),(x,y+1)),((x-1,y),(x,y+1),(x,y))]:
   if neighbor not in occupied:edges[u]=v
 poly=[];start=next(iter(edges));cur=start
 while True:
  poly.append(cur);cur=edges.pop(cur)
  if cur==start:break
 # Simplify the native perimeter conservatively; retain painted plank edges.
 def rdp(points,tolerance=.25):
  if len(points)<3:return points
  a=Vector(points[0]);b=Vector(points[-1]);d=b-a
  distances=[(Vector(p)-a-d*max(0,min(1,(Vector(p)-a).dot(d)/d.length_squared))).length for p in points[1:-1]];distance=max(distances,default=0)
  if distance<=tolerance:return [points[0],points[-1]]
  i=distances.index(distance)+1;return rdp(points[:i+1],tolerance)[:-1]+rdp(points[i:],tolerance)
 start=min(range(len(poly)),key=lambda i:poly[i]);ring=poly[start:]+poly[:start];split=max(range(1,len(ring)),key=lambda i:(Vector(ring[i])-Vector(ring[0])).length_squared);hull=rdp(ring[:split+1])[:-1]+rdp(ring[split:]+[ring[0]])[:-1];cx=sum(x for x,y in hull)/len(hull);cy=sum(y for x,y in hull)/len(hull);hull=[(cx+(x-cx)*1.0005,cy+(y-cy)*1.0005)for x,y in hull];top=[]
 for sx,sy in hull:
  q=Vector((sx,0,0))+down*sy;top.append(q+toward*(bn.dot(ba-q)/bn.dot(toward)))
 nn=len(top);bottom=[v-toward*2 for v in top];oldverts=[board.matrix_world@v.co for v in board.data.vertices];straps=oldverts[8:];strapfaces=[tuple(i-8+nn*2 for i in f.vertices)for f in board.data.polygons[6:]];shell=[tuple(range(nn)),tuple(range(nn*2-1,nn-1,-1))]+[(i,(i+1)%nn,(i+1)%nn+nn,i+nn)for i in range(nn)];replace(board,top+bottom+straps,shell+strapfaces)
 poly=[p for i,p in enumerate(poly)if (p[0]-poly[i-1][0])*(poly[(i+1)%len(poly)][1]-p[1])!=(p[1]-poly[i-1][1])*(poly[(i+1)%len(poly)][0]-p[0])];n=len(poly);verts=[]
 for depth in [-.5,200]:
  for sx,sy in poly:
   q=Vector((sx,0,0))+down*sy;verts.append(q+toward*(bn.dot(ba-q)/bn.dot(toward)+depth))
 faces=[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)];lookup={(float(x),float(y)):i for i,(x,y)in enumerate(poly)}
 for off,rev in [(0,True),(n,False)]:
  for tri in tessellate_polygon([[Vector((x,y,0))for x,y in poly]]):
   ix=tuple((v if isinstance(v,int)else lookup[(float(v.x),float(v.y))])+off for v in tri);faces.append(ix[::-1]if rev else ix)
 mesh=bpy.data.meshes.new('Board contact cutter');mesh.from_pydata(verts,[],faces);mesh.update();cut=bpy.data.objects.new('Board contact cutter',mesh);bpy.context.collection.objects.link(cut);bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 for obj in [cut,body]:
  bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.001);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);bm.to_mesh(obj.data);bm.free()
 bpy.context.view_layer.objects.active=body;body.select_set(True);mod=body.modifiers.new('Source-fitted board recess','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;mod.use_self=True;mod.use_hole_tolerant=True;bpy.context.view_layer.update();bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
 bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces)
 unseen=set(bm.verts);components=[]
 while unseen:
  component={unseen.pop()};stack=list(component)
  while stack:
   v=stack.pop()
   for e in v.link_edges:
    neighbor=e.other_vert(v)
    if neighbor in unseen:unseen.remove(neighbor);component.add(neighbor);stack.append(neighbor)
  components.append(component)
 for component in sorted(components,key=len)[:-1]:
  points=[body.matrix_world@v.co for v in component];assert max(max(p[i]for p in points)-min(p[i]for p in points)for i in range(3))<1;bmesh.ops.delete(bm,geom=list(component),context='VERTS')
 bm.to_mesh(body.data);bm.free()
 return dict(changed_nodes=['building-122','building-123','building-553'],roof_return_source=[[1782.5,480],[1791.5,454],[1797.5,433],[1799.5,414]],body_bend_world=[1794,-1000],base_elevation=68,inference='Short timber return followed by source-edge-on hidden side; top follows existing roof plane. Roof outer edge follows visible tile boundary. Concealed return depth, raised base and board recess require user review. Board stays at its original plane; its perimeter follows native526 within0.25sourcepixel.')
def main():
 from freeze_tooling import select_tooling
 from render_slots import acquire,release
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 import refinement_workspace as rw
 from refinement_review import render_review
 from reproject_map import reproject_map
 from source_projection_bake import bake
 old=WORK/'round-38/assets/nottingham-north-dormer-house';w=WORK/'texture-generation/projection-corrections/north-dormer-v19/nottingham-north-dormer-house'
 layers=json.loads((old/'preserved-projection-layers.json').read_text())['layers']
 def render(config,output,baseline=None):
  result=render_review(output,scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=config['asset_id'],source_path=config['source_path'],frame_manifest=baseline,width=256,height=320,context_padding=35,framing_padding=1.1,projection_layers=layers,source_mask_manifest=config['source_mask_manifest'],allow_projection_revision=bool(baseline),allow_mask_revision=bool(baseline))
  result['component_ownership']=config['component_ownership'];(Path(output)/'views.json').write_text(json.dumps(result,indent=2)+'\n');return result
 def project(config,directory):
  nodes=['building-122','building-123','building-124','building-125'];source=layers[0]['source_path'];directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
  report=reproject_map('nottingham',source,directory/'source.json',receiver_nodes=nodes,occluder_nodes=layers[0]['occluder_nodes'],projection_label='exterior',receiver_asset_id=config['asset_id'])
  report['ownership']=bake('nottingham',source,directory/'ownership.json',projection_label='exterior',receiver_nodes=nodes,occluder_nodes=layers[0]['occluder_nodes'],elevation_deg=35,preserve_authored=False,source_mask_manifest=config['source_mask_manifest'],receiver_asset_id=config['asset_id'])
  propnodes=['building-553'];source=layers[1]['source_path']
  report['board']=reproject_map('nottingham',source,directory/'board-source.json',receiver_nodes=propnodes,occluder_nodes=layers[1]['occluder_nodes'],projection_label='mission-custom1',receiver_asset_id=config['asset_id'])
  report['board_ownership']=bake('nottingham',source,directory/'board-ownership.json',projection_label='mission-custom1',receiver_nodes=propnodes,occluder_nodes=layers[1]['occluder_nodes'],elevation_deg=35,preserve_authored=False,source_mask_manifest=config['source_mask_manifest'],receiver_asset_id=config['asset_id'])
  return report
 rw._render=render
 acquire()
 try:
  if not w.exists():
   config=json.loads((old/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
   rw._reproject=lambda config,directory: {'status':'PRESERVED-APPROVED-BASELINE'}
   rw.prepare(w,asset_id=config['asset_id'],scene_name=config['scene_name'],collection_name=config['collection_name'],source_path=old/'reference/source.png',grouping_manifest=WORK/'grouping/catalog-v15.json',inventory_path=Path(json.loads((WORK/'coordinator-audit/batch6-grouping/donor-workspaces.json').read_text())['grouped_scene']).with_suffix('.evidence')/'inventory.json',review_path=WORK/'grouping/grouping-review-v15.json',source_mask_manifest=build_domain(old),width=256,height=320,context_padding=35,framing_padding=1.1)
   shutil.copy2(old/'preserved-projection-layers.json',w/'preserved-projection-layers.json')
   (w/'candidate.json').write_text(json.dumps(dict(status='refinement-in-progress',approval_status='pending',geometry_refined=True),indent=2)+'\n')
  rw._reproject=project;bpy.ops.wm.open_mainfile(filepath=str(w/'baseline.blend'));bpy.context.view_layer.update();r=apply();bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));(w/'return-correction.json').write_text(json.dumps(r,indent=2)+'\n');rw.modified(w);print(r,flush=True)
 finally:release()
if __name__=='__main__':main()
