"""Cut the mill hay mound behind its source-traced masonry foot.

This preserves source-visible hay and fixes ownership without moving the shaft.
The supplied derived mask is intentionally separate from the native inventory.
"""
def apply(mask_path):
 import bpy, math
 from pathlib import Path
 from mathutils import Vector
 from mathutils.geometry import tessellate_polygon
 from PIL import Image
 obs=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')=='nottingham-village-mill']
 mound=next(o for o in obs if o.get('source_node')=='building-240')
 chimney=next(o for o in obs if o.get('source_node')=='building-241')
 for i in range(4):chimney.data.vertices[i].co+=chimney.matrix_world.inverted().to_3x3()@Vector((0,-.4,0))
 for i in [3,7]:chimney.data.vertices[i].co+=chimney.matrix_world.inverted().to_3x3()@Vector((-.75,0,0))
 chimney.data.update();bpy.context.view_layer.update()
 im=Image.open(Path(mask_path)).convert('L');ox,oy=1675,2615
 occupied={(x+ox,y+oy)for y in range(im.height)for x in range(im.width)if im.getpixel((x,y))and y+oy>=2695};edges={}
 for x,y in occupied:
  for neighbor,a,b in [((x,y-1),(x,y),(x+1,y)),((x+1,y),(x+1,y),(x+1,y+1)),((x,y+1),(x+1,y+1),(x,y+1)),((x-1,y),(x,y+1),(x,y))]:
   if neighbor not in occupied:edges[a]=b
 loops=[]
 while edges:
  start=next(iter(edges));poly=[];cur=start
  while True:
   poly.append(cur);cur=edges.pop(cur)
   if cur==start:break
  loops.append(poly)
 poly=max(loops,key=len);poly=[p for i,p in enumerate(poly)if (p[0]-poly[i-1][0])*(poly[(i+1)%len(poly)][1]-p[1])!=(p[1]-poly[i-1][1])*(poly[(i+1)%len(poly)][0]-p[0])]
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));down=Vector((0,-s,-c));low,high=3909.1095428466797,3986.1872539520264
 verts=[Vector((x,0,0))+down*y+toward*t for t in [low,high]for x,y in poly];n=len(poly);faces=[]
 for i in range(n):j=(i+1)%n;faces.append((i,j,n+j,n+i))
 for ring,rev in [(0,True),(n,False)]:
  tris=tessellate_polygon([[Vector((x,y,0))for x,y in poly]])
  lookup={(float(x),float(y)):i for i,(x,y)in enumerate(poly)}
  for tri in tris:
   ix=tuple((v if isinstance(v,int) else lookup[(float(v.x),float(v.y))])+ring for v in tri);faces.append(ix[::-1]if rev else ix)
 mesh=bpy.data.meshes.new('Source-traced stone curtain');mesh.from_pydata(verts,[],faces);mesh.update();import bmesh;bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));print('cutter nonmanifold',sum(not e.is_manifold for e in bm.edges));bm.to_mesh(mesh);bm.free();cut=bpy.data.objects.new('Mill stone source-depth cutter',mesh);bpy.context.collection.objects.link(cut)
 bpy.context.view_layer.objects.active=mound;mound.select_set(True);mod=mound.modifiers.new('Stone source silhouette exclusion','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True);bpy.context.view_layer.update()
 bm=bmesh.new();bm.from_mesh(mound.data)
 nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free()
 if nonmanifold:raise RuntimeError(f'Mill contact cut has {nonmanifold} nonmanifold edges')
 return dict(source_polygon_vertices=n, cutter_depth=[low,high], nonmanifold_edges=nonmanifold, vertices=len(mound.data.vertices), faces=len(mound.data.polygons), shaft_above_native40_unchanged=True, ground_height_unchanged=True, inference='Concealed hay contact is trimmed behind painted masonry. Pixel-boundary contact must be inspected in all views.')
