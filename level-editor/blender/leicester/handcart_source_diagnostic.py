"""Measure source-camera foreshortening without modifying the handcart model.

Usage: blender --background MODEL --python SCRIPT -- WORKSPACE OUTPUT_DIRECTORY
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


output = Path(sys.argv[sys.argv.index("--") + 2]).resolve()
output.mkdir(parents=True, exist_ok=True)
sine = math.sin(math.radians(35))
cosine = math.cos(math.radians(35))
toward = Vector((0, -cosine, sine))
records = []
for obj in bpy.data.objects:
    if obj.type != "MESH" or obj.get("asset_group") != "leicester-northeast-handcart":
        continue
    for face in obj.data.polygons:
        if face.area < 100:
            continue
        normal = (
            obj.matrix_world.to_3x3().inverted().transposed() @ face.normal
        ).normalized()
        points = [obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
        source = [(p.x, -p.y * sine - p.z * cosine) for p in points]
        records.append({
            "object": obj.name,
            "source_node": obj.get("source_node"),
            "face": face.index,
            "area": face.area,
            "normal": list(normal),
            "source_cosine": normal.dot(toward),
            "world_vertices": [list(p) for p in points],
            "source_vertices": source,
            "source_span": [
                max(p[i] for p in source) - min(p[i] for p in source)
                for i in (0, 1)
            ],
        })
if not records:
    raise RuntimeError("No measurable handcart faces found")
(output / "source-face-measurements.json").write_text(
    json.dumps(records, indent=2) + "\n"
)
print(f"Measured {len(records)} handcart faces; model unchanged")
