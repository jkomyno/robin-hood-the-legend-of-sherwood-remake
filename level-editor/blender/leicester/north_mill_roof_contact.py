"""Recess supporting wall caps below the measured mill cottage roof slabs."""
import hashlib
import json
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

workspace = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
helpers = Path(__file__).resolve().parents[2] / 'refinement' / 'blender'
sys.path.insert(0, str(helpers))
from refinement_workspace import validate

config = json.loads((workspace / 'workspace.json').read_text())
assert config['asset_id'] == 'leicester-mill-south-cottage'
validate(workspace)
objects = [o for o in bpy.data.collections[config['collection_name']].all_objects if o.type == 'MESH']
def digest(obj):
    return hashlib.sha256(json.dumps({'vertices': [list(v.co) for v in obj.data.vertices], 'faces': [list(f.vertices) for f in obj.data.polygons], 'matrix': [list(row) for row in obj.matrix_world]}, sort_keys=True).encode()).hexdigest()
before = {o.name: digest(o) for o in objects}
owned = {o.get('source_node'): o for o in objects if o.get('asset_group') == config['asset_id'] and not o.get('projection_component')}
reports = []
changed_names = []
for wall_node, roof_node, underside_index in [('building-042', 'building-041', 13), ('building-043', 'building-040', 1)]:
    wall, roof = owned[wall_node], owned[roof_node]
    underside = roof.data.polygons[underside_index]
    normal = (roof.matrix_world.to_3x3().inverted().transposed() @ underside.normal).normalized()
    if normal.z >= -.5:
        raise ValueError('Expected measured roof underside plane')
    point = roof.matrix_world @ roof.data.vertices[underside.vertices[0]].co
    changes = []
    for vertex in wall.data.vertices:
        world = wall.matrix_world @ vertex.co
        z = (normal.dot(point) - normal.x * world.x - normal.y * world.y) / normal.z
        if world.z > z:
            if world.z < 100 or z < 60:
                raise ValueError('Unexpected wall cap correction')
            old = list(world); world.z = z
            vertex.co = wall.matrix_world.inverted() @ world
            changes.append({'vertex': vertex.index, 'before': old, 'after': list(world)})
    bm = bmesh.new(); bm.from_mesh(wall.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bad = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
    if bad or degenerate:
        raise ValueError(f'Invalid wall cap {wall_node}: {bad}/{degenerate}')
    bm.to_mesh(wall.data); bm.free(); wall.data.update()
    changed_names.append(wall.name)
    reports.append({'wall': wall_node, 'roof': roof_node, 'underside_face': underside_index, 'changes': changes, 'nonmanifold_edges': bad, 'degenerate_faces': degenerate})
unchanged = {o.name: before[o.name] == digest(o) for o in objects if o.name not in changed_names}
if not all(unchanged.values()):
    raise ValueError('Unrelated geometry changed')
report = {'revision': 'wall-roof-contact-v1', 'reports': reports, 'other_meshes_unchanged': unchanged, 'roof_geometry_unchanged': True, 'inference': 'Concealed supporting wall caps terminate at existing roof undersides; roof corner positions, slope, source masks and all other components remain unchanged.'}
(workspace / 'inspection' / 'wall-roof-contact.json').write_text(json.dumps(report, indent=2) + '\n')
validate(workspace)
bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
print(json.dumps({'changed_walls': changed_names, 'other_meshes_unchanged': len(unchanged)}))
