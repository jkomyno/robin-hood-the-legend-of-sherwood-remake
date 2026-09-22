"""Blender regression: stored atlases reject the same grazing surfaces as review."""
import math
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from source_projection_bake import bake


def check():
    collection=bpy.data.collections.new('GrazingFixture Working')
    bpy.context.scene.collection.children.link(collection)
    angle=math.radians(35)
    toward=Vector((0,-math.cos(angle),math.sin(angle)))
    down=Vector((0,-math.sin(angle),-math.cos(angle)))
    objects=[]
    for i,cosine in enumerate((.02,.1)):
        normal=toward*cosine-down*math.sqrt(1-cosine*cosine)
        axis=Vector((1,0,0));vertical=normal.cross(axis)
        center=Vector((4+i*8,0,0))+down*8
        mesh=bpy.data.meshes.new('grazing-'+str(i))
        mesh.from_pydata([center+axis*x+vertical*y for x,y in ((-3,-5),(3,-5),(3,5),(-3,5))],[],[(0,1,2,3)])
        mesh.update()
        obj=bpy.data.objects.new(mesh.name,mesh);obj['source_node']=mesh.name
        # Explicit lower values must not bypass the conservative review floor.
        obj['projection_min_cosine']=.0001
        collection.objects.link(obj);objects.append(obj)
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)
        image=bpy.data.images.new('red',width=16,height=16);image.pixels[:]=[1,0,0,1]*256
        image.filepath_raw=str(path/'source.png');image.file_format='PNG';image.save()
        report=bake('GrazingFixture',path/'source.png',path/'report.json')
        assert report['objects'][0]['known_texels']==0, report['objects'][0]
        assert report['objects'][1]['known_texels']>0, report['objects'][1]
        mat=objects[0].data.materials[objects[0].data.polygons[0].material_index]
        atlas=next(n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE')
        pixels=list(atlas.pixels)
        assert all(abs(r-g)<1e-6 and abs(r-b)<1e-6 for r,g,b in zip(pixels[0::4],pixels[1::4],pixels[2::4]))
    print('PASS: .02 grazing face remains neutral; .1 face receives source; low override cannot bypass floor')

if __name__=='__main__':check()
