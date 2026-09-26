"""Blender regression: inherited shared atlases must separate before rebaking."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from source_projection_bake import bake


def check():
    collection = bpy.data.collections.new('SplitFixture Working')
    bpy.context.scene.collection.children.link(collection)
    image = bpy.data.images.new('Shared old atlas', width=8, height=8)
    image.pixels[:] = [0, 1, 0, 1] * 64
    material = bpy.data.materials.new('Shared old ownership material')
    material.use_nodes = True
    material['source_ownership_bake'] = True
    material['source_ownership_label'] = 'exterior'
    material.node_tree.nodes.new('ShaderNodeTexImage').image = image
    objects = []
    for i, (x, width) in enumerate(((0, 3), (8, 6))):
        mesh = bpy.data.meshes.new(f'part-{i}')
        mesh.from_pydata([(x,-16,0),(x+width,-16,0),(x+width,0,0),(x,0,0)], [], [(0,1,2,3)])
        mesh.materials.append(material)
        obj = bpy.data.objects.new(mesh.name, mesh)
        obj['source_node'] = mesh.name
        collection.objects.link(obj)
        objects.append(obj)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        source = bpy.data.images.new('Red and blue source', width=16, height=16)
        source.pixels[:] = [v for y in range(16) for x in range(16) for v in ((1,0,0,1) if x<8 else (0,0,1,1))]
        source.filepath_raw = str(path/'source.png')
        source.file_format = 'PNG'
        source.save()
        bake('SplitFixture', path/'source.png', path/'report.json', projection_label='exterior')
        materials = [o.data.materials[o.data.polygons[0].material_index] for o in objects]
        images = [next(n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE') for m in materials]
        assert materials[0] != materials[1], 'Split objects retained shared material'
        assert images[0] != images[1], 'Split objects retained shared image'
        assert images[0].size[:] != images[1].size[:], 'Different island dimensions were overwritten'
        p0,p1 = list(images[0].pixels),list(images[1].pixels)
        assert sum(p0[0::4]) > sum(p0[2::4]), 'First receiver lost red atlas'
        assert sum(p1[2::4]) > sum(p1[0::4]), 'Second receiver lost blue atlas'
        bake('SplitFixture', path/'source.png', path/'repeat.json', projection_label='exterior')
        assert list(images[0].pixels)==p0 and list(images[1].pixels)==p1, 'Repeat bake changed independent atlas pixels'
    print('PASS: split receiver material/image isolation, dimensions, source colors and repeat bake')

if __name__=='__main__':
    check()
