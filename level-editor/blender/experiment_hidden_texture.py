"""Prepare/apply a masked texture trial on one camera-hidden gate roof face."""
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


def prepare(output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    bpy.context.view_layer.update()
    objects = bpy.data.collections["Derby Working"].objects
    target = next(o for o in objects if o.get("source_node") == "building-015"
                  and o.get("south_gate_roof") and not o.hide_render)
    direction = Vector((0, -math.cos(math.radians(35)), math.sin(math.radians(35))))
    face = next(p for p in target.data.polygons if p.index % 4 == 0 and p.normal.dot(direction) < -0.2)
    donor_layer = target.data.uv_layers["South gate roof donor"]
    donor_uv = {target.data.loops[i].vertex_index % 4: donor_layer.data[i].uv.copy()
                for i in face.loop_indices}
    image = next(i for i in bpy.data.images if i.filepath.endswith("covered.png"))
    source = list(image.pixels)
    width, height = image.size
    side = 256
    tile, mask, full = [], [], []
    for y in range(side):
        for x in range(side):
            v, u = y / (side - 1), x / (side - 1)
            a, b = v, u - v / 2
            c = 1 - a - b
            inside = min(a, b, c) >= 0
            hole = min(a, b, c) > 0.09
            if inside:
                uv = donor_uv[0] * a + donor_uv[1] * b + donor_uv[2] * c
                sx = min(width - 1, max(0, round(uv.x * width)))
                sy = min(height - 1, max(0, round(uv.y * height)))
                index = 4 * (sy * width + sx)
                rgb = source[index:index + 3]
            else:
                rgb = [0.3, 0.3, 0.3]
            tile.extend((*rgb, 0 if hole else 1))
            mask.extend((1, 1, 1, 0 if hole else 1))
            full.extend((*rgb, 1))
    for name, pixels in (("tile", tile), ("mask", mask), ("source-full", full)):
        result = bpy.data.images.new("Hidden roof trial " + name, width=side, height=side, alpha=True)
        result.pixels.foreach_set(pixels)
        result.filepath_raw = str(output / (name + ".png")); result.file_format = "PNG"; result.save()
        bpy.data.images.remove(result)
    record = {"object": target.name, "source_node": target["source_node"], "face": face.index,
              "normal_camera_cosine": face.normal.dot(direction), "model": "gpt-image-2.5-sunburst"}
    (output / "face.json").write_text(json.dumps(record, indent=2))
    return record


def apply(output_dir):
    output = Path(output_dir)
    record = json.loads((output / "face.json").read_text())
    obj = bpy.data.objects[record["object"]]
    face = obj.data.polygons[record["face"]]
    direction = Vector((0, -math.cos(math.radians(35)), math.sin(math.radians(35))))
    if face.normal.dot(direction) >= -0.2:
        raise RuntimeError("Experimental face is no longer hidden from the source camera")
    material = bpy.data.materials.new("Experimental concealed roof completion")
    material.use_nodes = True
    nodes = material.node_tree.nodes; nodes.clear()
    shader = nodes.new("ShaderNodeEmission"); texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(output / "completed.png"), check_existing=False)
    uvnode = nodes.new("ShaderNodeUVMap"); uvnode.uv_map = "Hidden texture trial"
    terminal = nodes.new("ShaderNodeOutputMaterial")
    links = material.node_tree.links
    links.new(uvnode.outputs["UV"], texture.inputs["Vector"])
    links.new(texture.outputs["Color"], shader.inputs["Color"])
    links.new(shader.outputs[0], terminal.inputs["Surface"])
    active_uv = obj.data.uv_layers.active_index
    render_uv = next((layer.name for layer in obj.data.uv_layers if layer.active_render), None)
    layer = obj.data.uv_layers.new(name="Hidden texture trial")
    positions = {0: (0.5, 1), 1: (1, 0), 2: (0, 0)}
    for loop_id in face.loop_indices:
        layer.data[loop_id].uv = positions[obj.data.loops[loop_id].vertex_index % 4]
    index = len(obj.data.materials); obj.data.materials.append(material)
    face.material_index = index
    obj.data.uv_layers.active_index = active_uv
    if render_uv:
        obj.data.uv_layers[render_uv].active_render = True
    return {**record, "model": "gpt-image-2.5-sunburst", "changed_faces": 1,
            "source_visible_faces_changed": 0}
