"""Blender regression: asset-owned components sharing a node remain isolated."""
import math
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from reproject_map import reproject_map, restore_projection, reproject_layers
from source_projection_bake import bake


def snapshot(obj):
    mesh = obj.data
    return (mesh.as_pointer(), tuple(tuple(v.co) for v in mesh.vertices),
            tuple((tuple(p.vertices), p.material_index) for p in mesh.polygons),
            tuple((uv.name, tuple(tuple(v.uv) for v in uv.data)) for uv in mesh.uv_layers),
            tuple((m.as_pointer(), tuple((n.name, n.type, n.image.as_pointer() if n.type == 'TEX_IMAGE' and n.image else None)
                                        for n in m.node_tree.nodes) if m.use_nodes else ()) for m in mesh.materials),
            tuple(sorted((k, str(v)) for k, v in obj.items())))


def check():
    col = bpy.data.collections.new('AssetFixture Working')
    bpy.context.scene.collection.children.link(col)
    mat = bpy.data.materials.new('Shared fallback')
    mesh = bpy.data.meshes.new('Shared mesh')
    up = Vector((0, math.sin(math.radians(35)), math.cos(math.radians(35))))
    toward = Vector((0, -math.cos(math.radians(35)), math.sin(math.radians(35))))
    mesh.from_pydata([Vector((x, 0, 0)) + up*y for x,y in ((2,-14),(14,-14),(14,-2),(2,-2))], [], [(0,1,2,3)])
    mesh.materials.append(mat)
    mesh.uv_layers.new(name='Fallback')
    mesh.update()
    back = bpy.data.objects.new('back', mesh)
    front = bpy.data.objects.new('front', mesh)
    for obj, asset in ((back, 'A'), (front, 'B')):
        obj['source_node'] = 'building-001'
        obj['asset_group'] = asset
        obj['projection_component'] = asset + '-wall'
        col.objects.link(obj)
    front.location = toward * 2
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        source = bpy.data.images.new('Red source', width=16, height=16)
        source.pixels[:] = [1,0,0,1]*256
        source.filepath_raw = str(path/'source.png')
        source.file_format = 'PNG'
        source.save()
        untouched = snapshot(front)
        report = reproject_map('AssetFixture', path/'source.png', path/'project.json', receiver_asset_id='A')
        assert snapshot(front) == untouched
        assert report['projected_faces'] == 0
        assert report['objects'][0]['blocking_objects']['front'] > 0
        assert report['projected_object_selectors'][0]['projection_component'] == 'A-wall'
        report = bake('AssetFixture', path/'source.png', path/'bake.json', receiver_asset_id='A')
        assert report['known_texels'] == 0 and report['unknown_texels'] > 0
        assert snapshot(front) == untouched
        # Both objects remain visibility participants when their roles swap.
        back.location = toward * 4
        bpy.context.view_layer.update()
        untouched = snapshot(back)
        report = bake('AssetFixture', path/'source.png', path/'front.json', receiver_asset_id='B')
        assert report['known_texels'] == 0 and report['unknown_texels'] > 0
        assert snapshot(back) == untouched
        # Hidden canonical originals are immutable even under the same asset.
        original = bpy.data.objects.new("hidden original", back.data.copy())
        col.objects.link(original)
        original["source_node"] = "building-001"
        original["asset_group"] = "A"
        original.hide_render = True
        original.data.polygons[0].material_index = 0
        original.data.attributes["reprojection_fallback_material"].data[0].value = 1
        hidden_snapshot = snapshot(original)
        restore_projection("AssetFixture", receiver_asset_id="A")
        assert snapshot(original) == hidden_snapshot, "Scoped restore mutated hidden canonical original"
        # Restoration also detaches shared mesh data before mutating face slots.
        front.data = back.data
        untouched = snapshot(front)
        restore_projection('AssetFixture', receiver_asset_id='A')
        assert snapshot(front) == untouched
        # A foreign part can inherit a previously scoped projection material.
        reproject_map('AssetFixture', path/'source.png', path/'again.json', receiver_asset_id='A')
        front.data = back.data.copy()
        untouched = snapshot(front)
        reproject_map('AssetFixture', path/'source.png', path/'repeat.json', receiver_asset_id='A')
        assert snapshot(front) == untouched
        (path/'interior.png').write_bytes((path/'source.png').read_bytes())
        manifest = {'version': 1, 'map': 'AssetFixture', 'size': [16,16],
                    'elevation_degrees': 35, 'patches': [], 'projection_reviews': {},
                    'sources': {'exterior': 'source.png', 'interior': 'interior.png'}}
        (path/'layers.json').write_text(json.dumps(manifest))
        untouched = snapshot(front)
        report = reproject_layers(path/'layers.json', ownership_asset_id='A')
        assert snapshot(front) == untouched, 'Layer pass changed foreign appearance or annotations'
        assert snapshot(original) == hidden_snapshot
        assert report['ownership_asset_id'] == 'A'
        assert {s['asset_group'] for s in report['projected_object_selectors']} == {'A'}
        assert all(s['object'] == 'back' for s in report['projected_object_selectors'])
    print('PASS: component-scoped reprojection/bake/restoration preserve foreign data and mutual occlusion')


if __name__ == '__main__':
    check()
