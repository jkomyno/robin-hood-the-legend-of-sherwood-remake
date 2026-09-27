"""Actual-material eight-view sheets for foliage assets (cutout alpha rendered with Cycles).

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/trees_render.py -- \
      --output <sheet.png> (--glb <model.glb> | --blend <file.blend> --asset <asset_group>) [...more]

Each input becomes one row of eight orbit views (35 degree elevation, 45 degree yaw steps,
view 0 = source camera). Every row shares one orthographic scale, so sizes compare
directly. Tiles show the saved materials, not the source sampler.
"""
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slots import acquire  # noqa: E402

TILE = 320


def load_glb(path):
    import bpy
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in set(bpy.data.objects) - before if o.type == 'MESH']


_LOADED = {}


def load_blend(path, asset):
    """Append each blend's objects once; later assets from the same file reuse them."""
    import bpy
    key = str(Path(path).resolve())
    if key not in _LOADED:
        with bpy.data.libraries.load(key, link=False) as (source, target):
            target.objects = [name for name in source.objects]
        _LOADED[key] = [o for o in target.objects if o is not None and o.type == 'MESH']
    objects = [o for o in _LOADED[key] if o.get('asset_group') == asset]
    if not objects:
        raise ValueError(f'No meshes for {asset} in {path}')
    for obj in objects:
        bpy.context.scene.collection.objects.link(obj)
    return objects


def bounds(objects):
    from mathutils import Vector
    points = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    low = Vector([min(p[i] for p in points) for i in range(3)])
    high = Vector([max(p[i] for p in points) for i in range(3)])
    return low, high


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--glb', type=Path, action='append', default=[])
    parser.add_argument('--blend', type=Path, action='append', default=[])
    parser.add_argument('--asset', action='append', default=[])
    parser.add_argument('--label', action='append', default=[])
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if len(args.blend) != len(args.asset):
        raise ValueError('Each --blend needs one --asset')
    acquire()
    import bpy
    import numpy as np
    from mathutils import Vector
    from PIL import Image, ImageDraw
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.cycles.transparent_max_bounces = 128
    scene.cycles.device = 'CPU'
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = TILE
    scene.view_settings.view_transform = 'Standard'
    world = bpy.data.worlds.new('neutral'); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.6, .6, .6, 1)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 2.5
    sun.rotation_euler = (math.radians(42), 0, math.radians(-31))
    scene.collection.objects.link(sun)
    rows = []
    for path in args.glb:
        rows.append((path.parent.name, load_glb(path)))
    for path, asset in zip(args.blend, args.asset):
        rows.append((asset, load_blend(path, asset)))
    labels = args.label + [name for name, _ in rows][len(args.label):]
    extent = 0
    for _, objects in rows:
        low, high = bounds(objects)
        extent = max(extent, (high - low).length)
    camera = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = extent * 1.05
    camera.data.clip_end = 100000
    scene.collection.objects.link(camera)
    scene.camera = camera
    sheet = Image.new('RGBA', (TILE * 8, TILE * len(rows) + 18 * len(rows)), (40, 40, 40, 255))
    draw = ImageDraw.Draw(sheet)
    elevation = math.radians(35)
    scratch = args.output.with_suffix('.tile.png')
    for row, (label, (_, objects)) in enumerate(zip(labels, rows)):
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                obj.hide_render = obj not in objects
        low, high = bounds(objects)
        target = (low + high) / 2
        for view in range(8):
            yaw = math.radians(view * 45)
            direction = Vector((math.sin(yaw) * math.cos(elevation), -math.cos(yaw) * math.cos(elevation), math.sin(elevation)))
            camera.location = target + direction * 20000
            camera.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(scratch)
            bpy.ops.render.render(write_still=True)
            tile = Image.open(scratch).convert('RGBA')
            background = Image.new('RGBA', tile.size, (40, 40, 40, 255))
            sheet.paste(Image.alpha_composite(background, tile), (view * TILE, row * (TILE + 18) + 18))
        draw.text((4, row * (TILE + 18) + 3), f'{label}  (views 0-7, 45 deg steps, shared ortho scale {extent * 1.05:.0f} px)', fill=(255, 255, 0, 255))
    scratch.unlink(missing_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert('RGB').save(args.output)
    print('TREES_RENDER_COMPLETE', args.output, flush=True)


if __name__ == '__main__':
    main()
