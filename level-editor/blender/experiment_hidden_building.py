"""Rear-image generation experiment, isolated from the published asset scene."""
import json
import math
import shutil
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import render_views
import setup_map


def prepare(output_dir, asset_id="derby-south-gatehouse", width=900):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    scene = bpy.data.scenes["Derby Refinement"]
    bpy.context.window.scene = scene
    scene.render.threads_mode = "FIXED"; scene.render.threads = 2
    objects = [o for o in bpy.data.collections["Derby Working"].objects
               if o.type == "MESH" and o.get("asset_group") == asset_id and not o.hide_render]
    if not objects:
        raise ValueError("Asset has no visible geometry")
    for obj in bpy.data.collections["Derby Working"].objects:
        if obj.type == "MESH" and obj not in objects:
            obj.hide_render = True
    scene.render.resolution_x = width; scene.render.resolution_y = width
    scene.render.film_transparent = True
    points = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
    target = (Vector(tuple(min(p[a] for p in points) for a in range(3))) +
              Vector(tuple(max(p[a] for p in points) for a in range(3)))) / 2
    views = {"source": "Derby reference"}
    setup_map.fit_camera(bpy.data.objects["Derby reference"], objects, 1)
    for label, yaw in (("rear", 155), ("rear-left", 130), ("rear-right", 180)):
        camera = bpy.data.objects["Derby west"].copy(); camera.data = camera.data.copy()
        scene.collection.objects.link(camera); camera.name = "Whole building trial " + label
        angle, pitch = math.radians(yaw), math.radians(35)
        camera.location = target + Vector((math.sin(angle)*math.cos(pitch),
                                          -math.cos(angle)*math.cos(pitch),math.sin(pitch))) * 1600
        camera.rotation_euler = (target-camera.location).to_track_quat("-Z", "Y").to_euler()
        setup_map.fit_camera(camera, objects, 1)
        views[label] = camera.name
    render_views.render_views(scene.name, views, output / "before", width=width)
    shutil.copyfile(output / "before/rear-solid.png", output / "tile.png")
    shutil.copyfile(output / "before/source-textured.png", output / "context.png")
    structural = bpy.data.images.load(str(output / "tile.png"), check_existing=False)
    pixels = list(structural.pixels)
    mask = bpy.data.images.new("Whole building silhouette edit mask", width=width, height=width, alpha=True)
    values = []
    for index in range(0, len(pixels), 4):
        values.extend((1, 1, 1, 0 if pixels[index+3] > 0.99 else 1))
    mask.pixels.foreach_set(values); mask.file_format = "PNG"
    mask.filepath_raw = str(output / "mask.png"); mask.save()
    bpy.data.images.remove(mask); bpy.data.images.remove(structural)
    record = {"asset_id": asset_id, "views": views, "width": width,
              "objects": [obj.name for obj in objects], "model": "gpt-image-2.5-sunburst"}
    (output / "setup.json").write_text(json.dumps(record, indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "prepared.blend"))
    return record


def apply(output_dir):
    output = Path(output_dir)
    record = json.loads((output / "setup.json").read_text())
    scene = bpy.data.scenes["Derby Refinement"]; bpy.context.window.scene = scene
    objects = [bpy.data.objects[name] for name in record["objects"]]
    source_camera = bpy.data.objects[record["views"]["source"]]
    rear_camera = bpy.data.objects[record["views"]["rear"]]
    bpy.context.view_layer.update()
    directions = {"source": source_camera.rotation_euler.to_matrix() @ Vector((0, 0, 1)),
                  "rear": rear_camera.rotation_euler.to_matrix() @ Vector((0, 0, 1))}
    vertices, triangles = [], []
    for obj in objects:
        start = len(vertices)
        vertices.extend(obj.matrix_world @ vertex.co for vertex in obj.data.vertices)
        obj.data.calc_loop_triangles()
        triangles.extend(tuple(start+i for i in t.vertices) for t in obj.data.loop_triangles)
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    image = bpy.data.images.load(str(output / "completed.png"), check_existing=False)
    image_pixels = list(image.pixels)
    image_width, image_height = image.size
    material = bpy.data.materials.new("Whole building generated rear projection")
    material.use_nodes = True
    nodes = material.node_tree.nodes; nodes.clear()
    shader = nodes.new("ShaderNodeEmission"); texture = nodes.new("ShaderNodeTexImage"); texture.image = image
    texture.interpolation = "Linear"
    uvnode = nodes.new("ShaderNodeUVMap"); uvnode.uv_map = "Whole building rear projection"
    terminal = nodes.new("ShaderNodeOutputMaterial")
    links = material.node_tree.links
    links.new(uvnode.outputs["UV"], texture.inputs["Vector"])
    links.new(texture.outputs["Color"], shader.inputs["Color"])
    links.new(shader.outputs[0], terminal.inputs["Surface"])
    changed = []
    rejected = []
    for obj in objects:
        mesh = obj.data
        active = mesh.uv_layers.active_index
        render_uv = next((layer.name for layer in mesh.uv_layers if layer.active_render), None)
        uv = mesh.uv_layers.new(name="Whole building rear projection")
        world = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        projection = [world_to_camera_view(scene, rear_camera, p) for p in world]
        for loop in mesh.loops:
            p = projection[loop.vertex_index]; uv.data[loop.index].uv = (p.x, p.y)
        index = len(mesh.materials); mesh.materials.append(material)
        for face in mesh.polygons:
            normal = (obj.matrix_world.to_3x3().inverted().transposed() @ face.normal).normalized()
            # Strict back-facing ownership protects the original source artwork,
            # even where partially occluded front faces would need polygon splits.
            if normal.dot(directions["source"]) >= -0.03 or normal.dot(directions["rear"]) <= 0.08:
                continue
            points = [world[i] for i in face.vertices]
            center = sum(points, Vector()) / len(points)
            samples = [center] + [p.lerp(center, 0.01) for p in points]
            rear_visible = all(tree.ray_cast(p + directions["rear"]*0.05, directions["rear"])[0] is None for p in samples)
            front_hidden = all(tree.ray_cast(p + directions["source"]*0.05, directions["source"])[0] is not None for p in samples)
            painted = True
            paint_samples = list(samples)
            for triangle in mesh.loop_triangles:
                if triangle.polygon_index != face.index:
                    continue
                a,b,c = (world[i] for i in triangle.vertices)
                paint_samples.extend((a*i+b*j+c*(12-i-j))/12
                                     for i in range(1,12) for j in range(1,12-i))
            for point in paint_samples:
                q = world_to_camera_view(scene, rear_camera, point)
                px = min(image_width-1,max(0,round(q.x*(image_width-1))))
                py = min(image_height-1,max(0,round(q.y*(image_height-1))))
                offset = (py*image_width+px)*4
                if max(image_pixels[offset:offset+3]) < 0.08:
                    painted = False
                    break
            if painted and rear_visible and front_hidden and all(0 <= projection[i].x <= 1 and 0 <= projection[i].y <= 1 for i in face.vertices):
                previous_material = face.material_index
                face.material_index = index
                changed.append({"object":obj.name,"face":face.index,"source_node":obj.get("source_node"),
                                "previous_material":previous_material,"trial_material":index})
        mesh.uv_layers.active_index = active
        if render_uv: mesh.uv_layers[render_uv].active_render = True
    if not changed:
        raise RuntimeError("No camera-safe rear projection receivers were found")
    # Ray samples cannot protect every rasterized shared edge. Admit each face
    # only when the complete source render remains byte-identical after adding it.
    reference = bpy.data.images.load(str(output / "before/source-textured.png"), check_existing=False)
    reference_pixels = list(reference.pixels)
    bpy.data.images.remove(reference)
    for entry in changed:
        bpy.data.objects[entry["object"]].data.polygons[entry["face"]].material_index = entry["previous_material"]
    accepted = []
    for number, entry in enumerate(changed):
        face = bpy.data.objects[entry["object"]].data.polygons[entry["face"]]
        face.material_index = entry["trial_material"]
        capture = output / "source-tests" / str(number)
        render_views.render_views(scene.name, {"source":record["views"]["source"]}, capture,
                                  modes=("textured",), width=record["width"])
        test = bpy.data.images.load(str(capture / "source-textured.png"), check_existing=False)
        identical = list(test.pixels) == reference_pixels
        bpy.data.images.remove(test)
        if identical:
            accepted.append(entry)
        else:
            face.material_index = entry["previous_material"]
            rejected.append({**entry,"reason":"source_render_changed"})
    changed = accepted
    render_views.render_views(scene.name, record["views"], output / "after", modes=("textured",), width=record["width"])
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "experiment.blend"))
    result = {"changed_faces": changed, "rejected_faces":rejected, "source_visible_faces_changed": 0,
              "source_verification":"Each accepted face preserves the complete original render exactly."}
    (output / "application.json").write_text(json.dumps(result, indent=2))
    return result
