"""Build four source-traced shed dormers on the keep's existing roof planes."""
import bpy,bmesh,json,math,sys
from pathlib import Path
from mathutils import Vector
SI,CO=math.sin(math.radians(35)),math.cos(math.radians(35))
# Coordinates measured in the archived covered source crop (origin 420,235).
DORMERS=[
 ('D1',287,[(394,138),(415,116),(350,138),(374,116)],[(350,156),(374,134)]),
 ('D2',287,[(349,185),(372,164),(307,185),(330,164)],[(307,203),(330,182)]),
 ('D3',288,[(486,160),(500,147),(544,194),(558,181)],[(544,212),(558,199)]),
 ('D4',288,[(436,210),(450,197),(494,244),(508,231)],[(494,262),(508,249)]),
]

def main(w):
 collection=bpy.data.collections['Leicester Working'];rows=[]
 for old in list(collection.all_objects):
  if old.get('north_dormer'):bpy.data.objects.remove(old,do_unlink=True)
 for number,node,top,foot in DORMERS:
  source=next(o for o in collection.all_objects if o.get('source_node')==f'building-{node}' and o.get('north_keep_baseline'))
  vs=[source.matrix_world@v.co for v in source.data.vertices];face=max(source.data.polygons,key=lambda p:p.area);p0,p1,p2=[vs[i] for i in list(face.vertices)[:3]];normal=(p1-p0).cross(p2-p0).normalized()
  def ground(pixel):
   x,y=pixel;x+=420;y+=235;origin=Vector((x,-y/SI,0));direction=Vector((0,-CO,SI));return origin+direction*(normal.dot(p0-origin)/normal.dot(direction))
  rear=[ground(p) for p in top[:2]];base=[ground(p) for p in foot];front=[p+Vector((0,0,(foot[i][1]-top[i+2][1])/CO)) for i,p in enumerate(base)]
  verts=rear+base+front;faces=[(0,1,5,4),(0,2,3,1),(2,4,5,3),(0,4,2),(1,3,5)]
  mesh=bpy.data.meshes.new(number+' shed dormer');mesh.from_pydata([source.matrix_world.inverted()@p for p in verts],[],faces);mesh.uv_layers.new(name='UVMap')
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);bm.to_mesh(mesh);bm.free()
  for m in source.data.materials:mesh.materials.append(m)
  obj=source.copy();obj.data=mesh;collection.objects.link(obj);obj.name='Great Keep / '+number+' roof dormer';obj.hide_render=False;obj.hide_set(False)
  for key in ['north_keep_baseline','north_keep_recipe']:obj.pop(key,None)
  obj['north_dormer']=number;obj['projection_component']=number+'-dormer';obj['reveal_component_patch_id']='patch-006';obj['reveal_component_role']='removable-cover';obj['todo']='Source silhouette traces roof and front wall; hidden cheeks and roof connection depth are inferred.'
  rows.append({'id':number,'source_node':obj['source_node'],'source_crop_origin':[420,235],'roof_pixels':top,'front_foot_pixels':foot,'vertices_world':[list(v) for v in verts]})
 p=w/'projection-layers.json';manifest=json.loads(p.read_text());r=manifest['projection_reviews']['patch-006']
 for key in ('exclude_occluder_components',):r[key]=[x for x in r[key] if not x.get('projection_component','').endswith('-dormer')]
 r['render_visibility']['revealed']['hidden_components']=[x for x in r['render_visibility']['revealed']['hidden_components'] if not x.get('projection_component','').endswith('-dormer')]
 for row in rows:
  sel={'source_node':row['source_node'],'projection_component':row['id']+'-dormer','patch_id':'patch-006'}
  r['render_visibility']['revealed']['hidden_components'].append(sel);r['exclude_occluder_components'].append(sel)
 r['geometry_ready']=False;r['evidence']+=' Four source-traced roof dormers added after user review; revised state review pending.'
 p.write_text(json.dumps(manifest,indent=2)+'\n');(w/'dormer-geometry.json').write_text(json.dumps(rows,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
if __name__=='__main__':main(Path(sys.argv[sys.argv.index('--')+1]).resolve())
