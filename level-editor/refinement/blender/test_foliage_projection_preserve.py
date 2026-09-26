"""Blender regression: physical alpha stays distinct from ownership during bake."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from source_projection_bake import bake


def check():
    collection=bpy.data.collections.new('FoliageFixture Working');bpy.context.scene.collection.children.link(collection)
    material=bpy.data.materials.new('physical foliage');material.use_nodes=True
    material['foliage_physical_opacity']=True;material['projection_preserve']=True
    material['opacity_semantics']='physical-coverage'
    material['source_ownership_semantics']='separate-mask'
    material['source_ownership_channel']='vertex-color-r'
    image=bpy.data.images.new('cutout',width=2,height=2)
    image.pixels[:]=[1,0,0,1, 0,1,0,0, 0,0,1,.5, 1,1,1,1]
    texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=image
    material.node_tree.links.new(texture.outputs['Alpha'],material.node_tree.nodes.get('Principled BSDF').inputs['Alpha'])
    opaque=material.copy();del opaque['foliage_physical_opacity']
    meshes=[]
    for i,mat in enumerate((material,opaque)):
        mesh=bpy.data.meshes.new('part'+str(i));mesh.from_pydata([(i*8,-8,0),(i*8+6,-8,0),(i*8+6,-1,0),(i*8,-1,0)],[],[(0,1,2,3)])
        mesh.materials.append(mat);mesh.uv_layers.new(name='authored')
        color=mesh.color_attributes.new(name='SourceOwnership',type='FLOAT_COLOR',domain='CORNER')
        for value in color.data:value.color=(1,0,0,1)
        obj=bpy.data.objects.new(mesh.name,mesh);obj['source_node']=mesh.name
        collection.objects.link(obj);meshes.append(mesh)
    original=list(image.pixels);uv=[tuple(x.uv) for x in meshes[0].uv_layers[0].data]
    colors=[tuple(x.color) for x in meshes[0].color_attributes[0].data]
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);source=bpy.data.images.new('source',width=16,height=16)
        source.pixels[:]=[1,0,0,1]*256;source.filepath_raw=str(root/'source.png');source.file_format='PNG';source.save()
        report=bake('FoliageFixture',root/'source.png',root/'report.json',preserve_authored=False,
                    reproject_authored_nodes=['part0','part1'])
        assert meshes[0].materials[meshes[0].polygons[0].material_index]==material
        assert list(image.pixels)==original
        assert [tuple(x.uv) for x in meshes[0].uv_layers[0].data]==uv
        assert [tuple(x.color) for x in meshes[0].color_attributes[0].data]==colors
        assert report['objects'][0]['physical_opacity_faces_preserved']==1
        assert meshes[1].materials[meshes[1].polygons[0].material_index]!=opaque
        material['source_ownership_channel']='alpha'
        try:bake('FoliageFixture',root/'source.png',root/'invalid.json',preserve_authored=False)
        except ValueError:pass
        else:raise AssertionError('Conflated physical opacity and ownership accepted')
    print('PASS: physical RGB/alpha, UV and ownership color preserved under forced bake; ordinary opaque material rebaked; invalid contract rejected')

if __name__=='__main__':check()
