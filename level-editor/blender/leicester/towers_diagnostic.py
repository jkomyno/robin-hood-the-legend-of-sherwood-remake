import bpy,bmesh,json
for obj in bpy.data.objects:
 if obj.get('source_node') not in ['building-331','building-350','building-332','building-333','building-349']:continue
 bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.75);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.001)
 print(obj.name,'vertices',len(bm.verts),'faces',len(bm.faces),'boundary',[(tuple(round(c,1) for c in (obj.matrix_world@v.co))) for e in bm.edges if e.is_boundary for v in e.verts][:20]);bm.free()
