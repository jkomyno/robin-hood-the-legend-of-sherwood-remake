"""Background Blender integration: V2 component prepare and modified packets."""
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refinement_workspace import prepare, modified, validate
from workspace_components import appearance_state


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected(obj):
    return {'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'matrix': [list(row) for row in obj.matrix_world],
            'hidden': obj.hide_render, 'properties': dict(obj.items()),
            'appearance': appearance_state(obj)}


def main():
    scene = bpy.data.scenes.new('PacketScope Refinement')
    bpy.context.window.scene = scene
    collection = bpy.data.collections.new('PacketScope Working')
    scene.collection.children.link(collection)
    material = bpy.data.materials.new('Unmodified common material')
    material.use_nodes = True
    up = Vector((0, math.sin(math.radians(35)), math.cos(math.radians(35))))
    def part(name, component, asset, x, hidden=False):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([Vector((x+dx, 0, 0))+up*y
                          for dx,y in ((0,-14),(6,-14),(6,-4),(0,-4))], [], [(0,1,2,3)])
        mesh.uv_layers.new(name='Baseline UV')
        mesh.materials.append(material)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        obj['source_node'] = 'building-000'
        obj['asset_group'] = asset
        if component:
            obj['projection_component'] = component
        obj.hide_render = hidden
        return obj
    original = part('Canonical original', None, 'left', 2, True)
    owned = part('Left wall', 'left-wall', 'left', 2)
    foreign = part('Right wall', 'right-wall', 'right', 11)
    bpy.context.view_layer.update()
    before = protected(foreign)
    hidden_before = protected(original)
    with tempfile.TemporaryDirectory(prefix='component-packet-') as directory:
        root = Path(directory)
        source = bpy.data.images.new('Packet source', width=32, height=32)
        source.pixels[:] = [.8,.2,.1,1]*1024
        source.filepath_raw = str(root/'source.png')
        source.file_format = 'PNG'
        source.save()
        catalog = {'version': 2, 'map': 'packetscope', 'canonical_owners': {'building-000': 'left'},
                   'groups': [{'id': asset, 'name': asset.title(),
                               'parts': [{'obstacle': 0, 'name': 'Wall', 'components': [asset+'-wall']}]}
                              for asset in ('left','right')]}
        inventory = {'map': 'packetscope', 'objects': [{'source_node': 'building-000'}]}
        (root/'catalog.json').write_text(json.dumps(catalog))
        (root/'inventory.json').write_text(json.dumps(inventory))
        (root/'review.json').write_text(json.dumps({'status': 'reviewed', 'reviewer': 'Integration fixture',
            'catalog_sha256': sha(root/'catalog.json'), 'inventory_sha256': sha(root/'inventory.json')}))
        bpy.ops.wm.save_as_mainfile(filepath=str(root/'scene.blend'))
        workspace = root/'asset'
        report = prepare(workspace, asset_id='left', scene_name=scene.name,
                         collection_name=collection.name, source_path=root/'source.png',
                         grouping_manifest=root/'catalog.json', inventory_path=root/'inventory.json',
                         review_path=root/'review.json', width=32, height=32, context_padding=3,
                         framing_padding=1.2)
        assert report['status'] == 'prepared'
        assert protected(foreign) == before, 'Prepare changed foreign component'
        assert protected(original) == hidden_before, 'Prepare changed hidden canonical geometry or appearance'
        assert validate(workspace)['status'] == 'PASS'
        immutable = {str(path.relative_to(workspace)): sha(path) for folder in ('input','reference')
                     for path in (workspace/folder).rglob('*') if path.is_file()}
        bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
        owned = bpy.data.objects['Left wall']
        foreign = bpy.data.objects['Right wall']
        original = bpy.data.objects['Canonical original']
        assert validate(workspace)['status'] == 'PASS'
        owned.data.vertices[0].co.x += .1
        owned.data.update()
        result = modified(workspace)
        assert result['status'] == 'PASS'
        assert protected(foreign) == before, 'Modified packet changed foreign component'
        assert protected(original) == hidden_before, 'Modified packet changed hidden canonical geometry or appearance'
        assert all(sha(workspace/path) == digest for path,digest in immutable.items())
        for folder in ('input','modified'):
            views = json.loads((workspace/folder/'views.json').read_text())
            assert views['component_ownership']['owned_components'] == [
                {'source_node':'building-000','projection_component':'left-wall'}]
            assert len(views['views']) == 8
            for sheet in ('solid.png','textured.png','context.png'):
                assert (workspace/folder/sheet).is_file()
    print('PASS: V2 prepare/edit/modified packets preserve foreign component and immutable evidence')


if __name__ == '__main__':
    main()
