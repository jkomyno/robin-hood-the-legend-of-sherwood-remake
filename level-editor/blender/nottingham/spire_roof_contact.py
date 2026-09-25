"""Build a planar roof extension and its explicitly inferred concealed tower recess."""
import math

def apply(body, roof_vertices, roof_faces, source_polygon, *, roof_face=1,
          name='Hall roof contact extension', thickness=2.0, clearance=.05,
          contact_cap_offset=.5):
    import bpy,bmesh
    from mathutils import Vector
    vertices=[Vector(p)for p in roof_vertices];ids=roof_faces[roof_face]
    normal=(vertices[ids[1]]-vertices[ids[0]]).cross(vertices[ids[2]]-vertices[ids[0]]).normalized()
    if normal.z<=0:raise ValueError('Expected the existing upward roof plane')
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    toward=Vector((0,-cosine,sine));down=Vector((0,-sine,-cosine))
    def on_plane(x,y):
        base=Vector((x,0,0))+down*y
        return base+toward*(normal.dot(vertices[ids[0]]-base)/normal.dot(toward)+contact_cap_offset)
    def make(label,points,faces):
        mesh=bpy.data.meshes.new(label);mesh.from_pydata(points,[],faces);mesh.update()
        obj=bpy.data.objects.new(label,mesh);bpy.context.scene.collection.objects.link(obj)
        return obj
    def clean(obj):
        mesh=bmesh.new();mesh.from_mesh(obj.data)
        bmesh.ops.remove_doubles(mesh,verts=list(mesh.verts),dist=.0001)
        bmesh.ops.dissolve_degenerate(mesh,edges=list(mesh.edges),dist=.0001)
        bmesh.ops.triangulate(mesh,faces=list(mesh.faces))
        bmesh.ops.recalc_face_normals(mesh,faces=list(mesh.faces));mesh.to_mesh(obj.data);mesh.free()
    def topology(obj):
        mesh=bmesh.new();mesh.from_mesh(obj.data)
        result=dict(vertices=len(mesh.verts),faces=len(mesh.faces),nonmanifold_edges=sum(not e.is_manifold for e in mesh.edges),degenerate_faces=sum(f.calc_area()<1e-8 for f in mesh.faces),signed_volume=mesh.calc_volume(signed=True))
        mesh.free()
        if result['nonmanifold_edges'] or result['degenerate_faces']:raise ValueError((obj.name,result))
        return result
    count=len(source_polygon);top=[on_plane(x,y)for x,y in source_polygon]
    faces=[tuple(range(count)),tuple(range(2*count-1,count-1,-1))]+[(i,(i+1)%count,(i+1)%count+count,i+count)for i in range(count)]
    extension=make(name,top+[p-normal*thickness for p in top],faces);clean(extension)
    front_depth=max((body.matrix_world@v.co).dot(toward)for v in body.data.vertices)+10
    base=[p-toward*clearance for p in top];front=[p+toward*(front_depth-p.dot(toward))for p in top]
    cutter=make(name+' temporary contact cutter',base+front,faces);clean(cutter)
    before=topology(body);clean(body);bpy.context.view_layer.objects.active=body
    modifier=body.modifiers.new('Inferred concealed roof contact','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name);bpy.data.objects.remove(cutter,do_unlink=True);clean(body)
    report=dict(method='Continue the existing roof slope with a closed contact tile cap; subtract only its source-traced footprint from the tower ahead of the cap.',body_before=before,body_after=topology(body),extension_topology=topology(extension),roof_normal=list(normal),thickness=thickness,clearance=clearance,contact_cap_offset_toward_source=contact_cap_offset,source_polygon=source_polygon,contact_vertices=[dict(source=p,roof_world=list(q))for p,q in zip(source_polygon,top)],limitation='Closed contact tile cap is 2 world units thick and offset 0.5 toward the source camera (0.287 vertically), overlapping the existing roof rather than floating. Concealed joint/recess is inferred and requires renewed paired user geometry review.')
    return extension,report


def trim_unsupported_side(body, *, source_x=303.0, source_y=446.0):
    """Close the tower's concealed side at the measured native body silhouette."""
    import bpy
    import bmesh
    from mathutils import Vector
    toward = Vector((0, -math.cos(math.radians(35)), math.sin(math.radians(35))))
    down = Vector((0, -math.sin(math.radians(35)), -math.cos(math.radians(35))))
    world = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
    right = max(point.x for point in world) + 10
    bottom = max(point.dot(down) for point in world) + 10
    depths = [min(point.dot(toward) for point in world)-10,
              max(point.dot(toward) for point in world)+10]
    outline = [(source_x, source_y), (right, source_y), (right, bottom), (source_x, bottom)]
    points = [Vector((x, 0, 0)) + down*y + toward*depth
              for depth in depths for x, y in outline]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7)] + [(i, (i+1)%4, (i+1)%4+4, i+4) for i in range(4)]
    mesh = bpy.data.meshes.new('Unsupported tower side cutter')
    mesh.from_pydata(points, [], faces)
    mesh.update()
    cutter = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.scene.collection.objects.link(cutter)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    bpy.context.view_layer.objects.active = body
    modifier = body.modifiers.new('Native body silhouette at hall attachment', 'BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.solver = 'EXACT'
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.0001)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=.0001)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    report = dict(source_x=source_x, source_y=source_y,
                  nonmanifold_edges=sum(not edge.is_manifold for edge in bm.edges),
                  degenerate_faces=sum(face.calc_area()<1e-8 for face in bm.faces),
                  signed_volume=bm.calc_volume(signed=True),
                  rationale='Below the roof eave, native spire442 ends at source column302. Close the unsupported right side at x303 to expose the hall roof and leave the background gap outside the asset.',
                  limitation='The concealed flat side joining the hall is inferred from the source silhouette.')
    assert report['nonmanifold_edges'] == report['degenerate_faces'] == 0 and report['signed_volume'] > 0
    bm.to_mesh(body.data)
    bm.free()
    return report
