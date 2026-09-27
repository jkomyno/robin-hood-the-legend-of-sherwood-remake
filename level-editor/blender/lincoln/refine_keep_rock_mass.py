"""Round-8 recipe: close the void under the great hall front inside the merged keep rock mass.

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/refine_keep_rock_mass.py -- <workspace>

The great hall's south-east and south front walls (building-233/256/261, not owned) stop at
z 439.5, while the hall floor rests at z 512.7 on raised ground 465 whose front sits ~185 px behind
the wall line. The artwork paints the rock mass directly under the hall front, down to the keep
plateau (z 268.6). This recipe adds a solid block to 465 whose front faces lie 0.5 px behind
the two hall front wall lines (from the west corner (1216.6, -2592.1) via (1424.2, -2638.2) to
(1622.9, -2509.2)), 230 px deep, from the plateau top to the hall floor. The wall faces keep
covering everything above z 439.5; below it the new faces receive the rock artwork. Only 465 is
edited (the block is a separate closed shell of 465; an exact boolean union with the sculpted
non-manifold rock returns an empty mesh); geometry is read from the workspace scene. Idempotent: rerunning on an edited model is
refused. Then runs the workspace `modified` packet.
"""
import json
import math
from pathlib import Path
import subprocess
import sys

WALL_CORNERS = ((1216.6, -2592.1), (1424.2, -2638.2), (1622.9, -2509.2))  # hall front bottom line
INSET, DEPTH = 0.5, 230.0
PLATEAU_TOP, HALL_FLOOR = 268.5, 512.0  # just below the hall floor (512.7) to avoid coplanar faces


def main(workspace):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement'))
    from render_slots import acquire
    acquire()
    import bpy
    import bmesh
    from mathutils import Vector
    workspace = Path(workspace).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    working = bpy.data.collections['lincoln Working']
    meshes = [o for o in working.all_objects if o.type == 'MESH' and not o.hide_render]
    targets = [o for o in meshes if o.get('source_node') == 'building-465']
    if len(targets) != 1:
        raise ValueError('Expected one visible 465 mesh')
    target = targets[0]
    if target.get('asset_group') != 'lincoln-castle-hill-keep-plateau':
        raise ValueError('465 is not owned by the merged keep plateau asset')
    if target.get('round8_hall_front_fill'):
        raise ValueError('Round-8 fill already applied; start from the prepared model')
    # Verify the hall front wall line against the unowned walls' actual bottom vertices.
    bottoms = [tuple(round(c, 1) for c in (obj.matrix_world @ v.co)[:2])
               for obj in meshes if obj.get('source_node') in ('building-233', 'building-256', 'building-261')
               for v in obj.data.vertices if (obj.matrix_world @ v.co).z < 441]
    for corner in WALL_CORNERS:
        if min(math.dist(corner, b) for b in bottoms) > 0.2:
            raise ValueError(f'Hall front corner moved: {corner}')
    block = bmesh.new()
    for (ax, ay), (bx, by) in zip(WALL_CORNERS, WALL_CORNERS[1:]):
        edge = Vector((bx - ax, by - ay, 0))
        inward = Vector((-edge.y, edge.x, 0)).normalized()  # left of the west-to-east line points into the hall
        a, b = Vector((ax, ay, 0)) + inward * INSET, Vector((bx, by, 0)) + inward * INSET
        footprint = [a, b, b + inward * DEPTH, a + inward * DEPTH]
        verts = [block.verts.new((p.x, p.y, z)) for z in (PLATEAU_TOP, HALL_FLOOR) for p in footprint]
        bottom, top = verts[:4], verts[4:]
        block.faces.new(list(reversed(bottom)))
        block.faces.new(top)
        for i in range(4):
            j = (i + 1) % 4
            block.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(block, faces=block.faces)
    block.verts.index_update()
    # An exact boolean union with the sculpted, non-manifold 465 rock returns an empty mesh, so the
    # block is added as a separate closed shell of the same mesh; its hidden back part lies inside 465.
    block.transform(target.matrix_world.inverted())
    before = len(target.data.polygons)
    merged = bmesh.new()
    merged.from_mesh(target.data)
    added = [merged.verts.new(v.co) for v in block.verts]
    for face in block.faces:
        new = merged.faces.new([added[v.index] for v in face.verts])
        new.material_index = 0
    block.free()
    merged.to_mesh(target.data)
    merged.free()
    target.data.update()
    after = len(target.data.polygons)
    co = [target.matrix_world @ v.co for v in target.data.vertices]
    report = {'faces_before': before, 'faces_after': after,
              'bounds_min': [round(min(p[i] for p in co), 2) for i in range(3)],
              'bounds_max': [round(max(p[i] for p in co), 2) for i in range(3)],
              'wall_corners': WALL_CORNERS, 'inset': INSET, 'depth': DEPTH,
              'z_range': [PLATEAU_TOP, HALL_FLOOR]}
    target['round8_hall_front_fill'] = json.dumps(report, sort_keys=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    (workspace / 'inspection').mkdir(exist_ok=True)
    (workspace / 'inspection' / 'round8-fill.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ROUND8 FILL', json.dumps(report), flush=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
