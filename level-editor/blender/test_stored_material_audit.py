"""Tiny Blender fixture for real stored-material export/render and fail-closed graph checks."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Matrix
from audit_stored_materials import inspect, run


def check():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    collection = bpy.data.collections.new('Fixture Working')
    bpy.context.scene.collection.children.link(collection)
    mesh = bpy.data.meshes.new('quad')
    mesh.from_pydata([(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0)],[],[(0,1,2,3)])
    obj = bpy.data.objects.new('quad',mesh)
    obj['asset_group']='fixture'
    obj['source_node']='part-0'
    collection.objects.link(obj)
    parent = bpy.data.objects.new('outside parent',None)
    bpy.context.scene.collection.objects.link(parent)
    obj.parent=parent
    mat=bpy.data.materials.new('owned')
    mat.use_nodes=True
    mat['source_ownership_bake']=True
    mat['source_ownership_label']='exterior'
    mesh.materials.append(mat)
    assert inspect([obj])[1], 'Missing owned image/UV graph must fail'
    mat.node_tree.nodes.clear()
    layer=mesh.uv_layers.new(name='atlas')
    for entry,uv in zip(layer.data,[(0,0),(1,0),(1,1),(0,1)]):entry.uv=uv
    image=bpy.data.images.new('red atlas',width=4,height=4)
    image.pixels[:]=[1,0,0,1]*16
    image.pack()
    uv=mat.node_tree.nodes.new('ShaderNodeUVMap');uv.uv_map='atlas'
    texture=mat.node_tree.nodes.new('ShaderNodeTexImage');texture.image=image
    output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(uv.outputs['UV'],texture.inputs['Vector'])
    mat.node_tree.links.new(texture.outputs['Color'],output.inputs['Surface'])
    assert not inspect([obj])[1]
    other=obj.copy();other.data=mesh.copy();collection.objects.link(other)
    other.data.materials[0]=mat.copy()
    assert any('image shared' in p for p in inspect([obj,other])[1])
    bpy.data.objects.remove(other,do_unlink=True)
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)
        (path/'workspace.json').write_text(json.dumps({'collection_name':collection.name,'asset_id':'fixture'}))
        (path/'modified').mkdir()
        matrix=Matrix.Translation((0,0,10))
        frames={'tile_size':[16,16],'views':[{'index':i,'ortho_scale':3,'camera_matrix_world':[list(r) for r in matrix]} for i in range(8)]}
        (path/'modified/views.json').write_text(json.dumps(frames))
        bpy.ops.wm.save_as_mainfile(filepath=str(path/'model.blend'))
        report=run(path,path/'audit',render=True,export=True)
        assert report['status']=='STRUCTURAL-PASS',report['problems']
        assert len(report['artifact_sha256'])==10
        image=bpy.data.images.load(str(path/'audit/view-0.png'))
        pixel=list(image.pixels)[(8*16+8)*4:][:3]
        assert pixel[0]>.9 and pixel[1]<.01 and pixel[2]<.01,pixel
    print('PASS: missing graph/shared image guards; isolated parented asset GLB; actual red atlas eight-view render; artifact hashes')

if __name__=='__main__':check()
