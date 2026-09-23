"""Cut the east tower opening from reviewed raised drawbridge evidence."""
import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def cut_east_doorway(obj, workspace):
    from towers import diagnostics

    evidence = Path(__file__).resolve().parents[2] / 'work/leicester-refinement/round-1/north-inspection/east-tower-doorway.json'
    record = json.loads(evidence.read_text())
    outline = [Vector(p) for p in record['world_outline']]
    # The reviewed image constrains the visible aperture, while its concealed
    # depth remains unknown. Sweep the measured contour along its source rays
    # so wall thickness cannot shift or enlarge the visible stone boundaries.
    normal = Vector((0, -math.cos(math.radians(35)), math.sin(math.radians(35))))
    half = 400
    vertices = [p + normal * d for d in (-half, half) for p in outline]
    n = len(outline)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    mesh = bpy.data.meshes.new('Reviewed east doorway cutter')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    cutter = bpy.data.objects.new('Reviewed east doorway cutter', mesh)
    bpy.context.scene.collection.objects.link(cutter)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    before = diagnostics(obj)
    if before['nonmanifold_edges']:
        raise RuntimeError('Closed wall prerequisite failed before doorway: ' + str(before))
    modifier = obj.modifiers.new('Source supported raised leaf opening', 'BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.solver = 'EXACT'
    modifier.object = cutter
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    after = diagnostics(obj)
    if before == after:
        raise RuntimeError('Doorway boolean did not change east tower geometry')
    if after['nonmanifold_edges'] or after['degenerate_faces']:
        raise RuntimeError('Doorway boolean produced invalid topology: ' + str(after))
    obj['doorway_evidence_sha256'] = hashlib.sha256(evidence.read_bytes()).hexdigest()
    report = dict(record, source_node=obj['source_node'], before=before, after=after,
                  cutter_extrusion=list(normal), cutter_depth=2*half,
                  hidden_depth_hypothesis='Source-ray sweep through the wall; concealed jamb depth and orientation need owner review.',
                  status='physical opening applied; source ray and fixed view review pending')
    (workspace / ('inspection/east-doorway-'+obj['source_node']+'.json')).write_text(json.dumps(report, indent=2)+'\n')
    return ([list(obj.matrix_world @ v.co) for v in obj.data.vertices],
            [tuple(f.vertices) for f in obj.data.polygons])
