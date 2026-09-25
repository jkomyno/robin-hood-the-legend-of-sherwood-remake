"""Blender regression: ignore only material slots unused by mesh faces."""
from pathlib import Path
import sys
import tempfile
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_staged_handoffs import snapshot


def rejected(collection):
    try:snapshot(collection)
    except ValueError as e:
        assert 'Unpacked publication image' in str(e)
    else:raise AssertionError('Accepted assigned external image')


def check():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    c=bpy.data.collections.new('Check');bpy.context.scene.collection.children.link(c)
    m=bpy.data.meshes.new('Mesh');m.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
    o=bpy.data.objects.new('Mesh',m);c.objects.link(o)
    active=bpy.data.materials.new('Active');m.materials.append(active)
    unused=bpy.data.materials.new('Unused source');unused.use_nodes=True;m.materials.append(unused)
    node=unused.node_tree.nodes.new('ShaderNodeTexImage')
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'source.png'
        im=bpy.data.images.new('source',width=2,height=2);im.filepath_raw=str(path);im.file_format='PNG';im.save()
        bpy.data.images.remove(im);im=bpy.data.images.load(str(path));node.image=im
        before=snapshot(c.name)
        m.polygons[0].material_index=1;rejected(c.name)
        path.unlink();rejected(c.name)
        m.polygons[0].material_index=0
        assert snapshot(c.name)==before
        modifier=o.modifiers.new('Possible assignment change','NODES');rejected(c.name)
        o.modifiers.remove(modifier)
        # Packed, assigned images remain protected byte-for-byte.
        im=bpy.data.images.new('packed',width=2,height=2);node.image=im
        im.filepath_raw=str(path);im.file_format='PNG';im.save()
        data=path.read_bytes();im.pack(data=data,data_len=len(data));m.polygons[0].material_index=1
        packed=snapshot(c.name)
        im.pixels[0]=.4;im.update();im.save()
        data=path.read_bytes();im.pack(data=data,data_len=len(data))
        assert snapshot(c.name)!=packed
    print('PASS: unused missing source allowed; assigned external/missing images and modifier ambiguity rejected; packed pixels protected')

if __name__=='__main__':check()
