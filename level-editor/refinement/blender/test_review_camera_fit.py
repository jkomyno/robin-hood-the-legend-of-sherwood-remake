"""Blender fixture for tightly fitted, unclipped review cameras."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from setup_map import fit_camera

mesh = bpy.data.meshes.new("Slender diagonal asset")
points = [Vector((x + offset, x - offset, z))
          for x in (-10, 10) for offset in (-.5, .5) for z in (0, 5)]
mesh.from_pydata(points, [], [])
mesh.update()
obj = bpy.data.objects.new(mesh.name, mesh)
bpy.context.scene.collection.objects.link(obj)
bpy.context.view_layer.update()
camera = bpy.data.objects.new("Fit fixture", bpy.data.cameras.new("Fit fixture"))
bpy.context.scene.collection.objects.link(camera)
camera.data.type = "ORTHO"
camera.location = (30, 30, 20)
camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
aspect = 384 / 512
fit_camera(camera, [obj], aspect)
old_scale = camera.data.ortho_scale
fit_camera(camera, [obj], aspect, points=points, padding=1.04)
assert camera.data.ortho_scale < old_scale * .9
rotation = camera.rotation_euler.to_matrix()
xs = [(p-camera.location).dot(rotation.col[0]) for p in points]
ys = [(p-camera.location).dot(rotation.col[1]) for p in points]
half_height = camera.data.ortho_scale / 2
assert max(abs(x) for x in xs) <= half_height * aspect
assert max(abs(y) for y in ys) <= half_height
occupancy = max(max(abs(x) for x in xs)/(half_height*aspect),
                max(abs(y) for y in ys)/half_height)
assert math.isclose(occupancy, 1/1.04, rel_tol=1e-5)
print(f"PASS: all vertices fit; limiting-axis occupancy {occupancy:.1%}; scale {old_scale:.2f} -> {camera.data.ortho_scale:.2f}")

# An undersized proxy may reserve room for later source-supported additions.
# Changing the setting after the input is frozen must never refit its cameras.
import tempfile
from array import array
from refinement_review import render_review, _save

with tempfile.TemporaryDirectory(prefix='review-framing-') as directory:
    output = Path(directory)
    source = output/'source.png'
    _save(source, 64, 64, array('f', [1., .5, .25, 1.])*4096)
    collection = bpy.data.collections.new('Framing fixture')
    bpy.context.scene.collection.children.link(collection)
    bpy.ops.mesh.primitive_cube_add(size=4, location=(20, -20, 3))
    proxy = bpy.context.object
    collection.objects.link(proxy)
    proxy['asset_group'] = 'proxy'
    proxy['source_node'] = 'building-001'
    options = dict(scene_name=bpy.context.scene.name, collection_name=collection.name,
                   asset_id='proxy', source_path=source, width=8, height=8, context_padding=10)
    normal = render_review(output/'normal', **options)
    roomy = render_review(output/'roomy', **options, framing_padding=2.2)
    assert normal['context_crop'] == roomy['context_crop']
    for first, second in zip(normal['views'], roomy['views']):
        assert math.isclose(second['ortho_scale']/first['ortho_scale'], 2.2/1.04, rel_tol=1e-5)
    proxy.scale.z = 1.5
    bpy.context.view_layer.update()
    modified = render_review(output/'modified', **options, frame_manifest=roomy, framing_padding=5)
    assert modified['framing_padding'] == 2.2
    assert modified['context_crop'] == roomy['context_crop']
    for first, second in zip(roomy['views'], modified['views']):
        for key in ('camera_location', 'camera_rotation_euler', 'ortho_scale'):
            assert first[key] == second[key], key
    for invalid in (0.9, float('inf'), float('nan')):
        try:
            render_review(output/'invalid', **options, framing_padding=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid framing multiplier accepted')
print('PASS: configurable initial camera padding preserves fixed modified cameras and independent context crop')
