"""Read-only source-facing face measurements for held cottage revisions."""
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

asset, output = sys.argv[sys.argv.index('--') + 1:]
angle = math.radians(35)
toward = Vector((0, -math.cos(angle), math.sin(angle)))
rows = []
for obj in bpy.data.objects:
    if obj.type != 'MESH' or obj.get('asset_group') != asset or obj.hide_render:
        continue
    world = [obj.matrix_world @ v.co for v in obj.data.vertices]
    faces = []
    for face in obj.data.polygons:
        normal = (obj.matrix_world.to_3x3().inverted().transposed() @ face.normal).normalized()
        vertices = [world[i] for i in face.vertices]
        pixels = [[v.x, -v.y * math.sin(angle) - v.z * math.cos(angle)] for v in vertices]
        faces.append({'index': face.index, 'normal': list(normal), 'source_facing_cosine': normal.dot(toward), 'area_local': face.area, 'world_vertices': [list(v) for v in vertices], 'source_pixels': pixels})
    rows.append({'object': obj.name, 'source_node': obj.get('source_node'), 'projection_component': obj.get('projection_component'), 'projection_min_cosine': obj.get('projection_min_cosine', .05), 'faces': faces})
p = Path(output); p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({'asset': asset, 'model': bpy.data.filepath, 'read_only': True, 'objects': rows}, indent=2) + '\n')
print(json.dumps({'output': str(p), 'objects': len(rows)}))
