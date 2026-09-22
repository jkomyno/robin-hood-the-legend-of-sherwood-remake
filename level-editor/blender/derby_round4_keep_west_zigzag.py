"""West Tower rear parapet traced in original covered-image coordinates.

Withdraws the previous unmeasured front-gap additions. Rear136--138 crowns
change; the recessed door, room rim, floor, and front131--133 remain intact.
"""
import bpy,bmesh,math
from mathutils import Vector,Matrix
TAG='west-rear-parapet-source-trace-v2'
PROFILES={
137:[(375.3,361.2),(380,362.5),(380,394),(401,399),(401,382),(423.3,387)],
138:[(423.162,426),(437.5,429.5),(437.5,409),(452,412.5),(452,434.5),(470,439),(470,416.5),(487,420.5),(487,443),(505,447),(505,424.5),(522,428.5),(522,450.5),(539.872,454.9)]}

def refine():
 working=bpy.data.collections['Derby Working'];results=[]
 for node,profile in PROFILES.items():
  visible=[o for o in working.objects if o.type=='MESH' and not o.hide_render and o.get('source_node')==f'building-{node:03}']
  if len(visible)!=1:raise ValueError(f'Expected one visible shell for {node}')
  current=visible[0]
  if current.get('west_zigzag_recipe')==TAG:raise ValueError('Run once from preserved v4')
  if node==138:
   source=next(o for o in working.objects if o.get('source_node')=='building-138' and not o.get('crenellation_notches'))
   ai,bi,ii=18,19,17
  else:source=current;ai,bi,ii=17,18,16
  a,b,inner=[source.matrix_world@source.data.vertices[i].co for i in (ai,bi,ii)]
  offset=inner-a;offset.z=0
  sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35));front=[]
  for x,sy in profile:
   p=a.lerp(b,(x-a.x)/(b.x-a.x));p.z=(-sy-p.y*sine)/cosine;front.append(p)
  front=[Vector((front[0].x,front[0].y,0)),*front,Vector((front[-1].x,front[-1].y,0))]
  vertices=front+[v+offset for v in front];n=len(front)
  faces=[tuple(range(n)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
  mesh=bpy.data.meshes.new(f'West Tower / source-traced rear parapet {node}');mesh.from_pydata(vertices,[],faces)
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
  quality={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces),'volume':bm.calc_volume()}
  assert quality['nonmanifold_edges']==0 and quality['degenerate_faces']==0 and quality['volume']>0,quality
  bm.to_mesh(mesh);bm.free()
  neutral=bpy.data.materials.get('West parapet unverified') or bpy.data.materials.new('West parapet unverified');neutral.diffuse_color=(.25,.25,.25,1);mesh.materials.append(neutral)
  obj=bpy.data.objects.new(current.name+' / source-traced',mesh);working.objects.link(obj);obj.parent=current.parent;obj.matrix_world=Matrix.Identity(4)
  for k in current.keys():
   if not k.startswith('reprojection_'):obj[k]=current[k]
  obj['west_zigzag_recipe']=TAG;obj['crenellation_notches']=1 if node==137 else 4
  current.hide_render=True;current.hide_set(True);current['replaced_by']=obj.name
  actual=[(p.x,-p.y*sine-p.z*cosine) for p in front[1:-1]];errors=[math.dist(p,q) for p,q in zip(actual,profile)]
  results.append({'node':node,'quality':quality,'source_corners':profile,'result_corners':actual,'max_corner_error_px':max(errors),'gap_count':obj['crenellation_notches']})
 from derby_asset_east_hall import _refine
 source=next(o for o in working.objects if o.type=='MESH' and not o.hide_render and o.get('source_node')=='building-136')
 doorway_before=[tuple(source.matrix_world@v.co) for v in source.data.vertices if 300<(source.matrix_world@v.co).x<329 and 535<(source.matrix_world@v.co).z<596]
 cut=_refine(source,[(13,32,33,11,[(359,371)],27)])
 replacement=bpy.data.objects[source['replaced_by']];replacement['west_zigzag_recipe']=TAG
 vertices=[replacement.matrix_world@v.co for v in replacement.data.vertices]
 max_door_drift=max(min((Vector(p)-v).length for v in vertices) for p in doorway_before)
 assert max_door_drift<.01,max_door_drift
 results.append({'node':136,'cut':cut,'gap_count':1,'gap_outer_x':[359,371],'doorway_vertices_preserved':len(doorway_before),'doorway_vertex_max_drift':max_door_drift})
 return {'recipe':TAG,'changes':results,'preserved':'131--133, recessed doorway136, landing239, wall240, component-owned raised cut-wall'}
