"""Blender fixture: alpha holes expose geometry without consulting ownership RGB."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from refinement_review import _tree
from review_sunlight import _surface
from source_visibility import first_source_hit


def check():
    image=bpy.data.images.new('physical mask',width=2,height=2)
    image.pixels[:]=[.7,.6,.5,0, .7,.6,.5,1]*2
    mat=bpy.data.materials.new('front physical');mat.use_nodes=True
    mat['foliage_physical_opacity']=True;mat['opacity_semantics']='physical-coverage'
    mat['foliage_card_sides']='paired-one-sided'
    texture=mat.node_tree.nodes.new('ShaderNodeTexImage');texture.image=image;texture.interpolation='Closest'
    mat.node_tree.links.new(texture.outputs['Alpha'],mat.node_tree.nodes.get('Principled BSDF').inputs['Alpha'])
    back=mat.copy();back.name='back neutral physical'
    def quad(name,z,material,reverse=False):
        mesh=bpy.data.meshes.new(name)
        mesh.from_pydata([(-1,-1,z),(1,-1,z),(1,1,z),(-1,1,z)],[],[(3,2,1,0) if reverse else (0,1,2,3)])
        if material:mesh.materials.append(material)
        uv=mesh.uv_layers.new(name='coverage')
        coords=[(0,0),(1,0),(1,1),(0,1)]
        for loop in mesh.loops:uv.data[loop.index].uv=coords[loop.vertex_index]
        ownership=mesh.color_attributes.new(name='SourceOwnership',type='FLOAT_COLOR',domain='CORNER')
        for value in ownership.data:value.color=(0 if reverse else 1,0,0,1)
        obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj)
        return obj
    front=quad('front',2,mat);rear=quad('back',1.8,back,True);trunk=quad('opaque trunk',0,None)
    bpy.context.view_layer.update()
    tree,owners,_=_tree([front,rear,trunk])
    for x,expected in ((-.5,trunk),(.5,front)):
        origin=Vector((x,0,10));direction=Vector((0,0,-1))
        hit,_,index,_=first_source_hit(tree,owners,origin,direction)
        assert owners[index]==expected,(x,owners[index].name)
    # From beneath the paired back card, no front-card backface may occlude it.
    tree,owners,_=_tree([front,rear])
    assert tree.ray_cast(Vector((-.5,0,-10)),Vector((0,0,1)))[0] is None
    assert owners[tree.ray_cast(Vector((.5,0,-10)),Vector((0,0,1)))[2]]==rear
    # Solid silhouette and shadow trees use precisely the same physical holes.
    solid_tree,*_=_surface([front,rear])
    assert solid_tree.ray_cast(Vector((-.5,0,10)),Vector((0,0,-1)))[0] is None
    assert solid_tree.ray_cast(Vector((.5,0,10)),Vector((0,0,-1)))[0] is not None
    for value in front.data.color_attributes[0].data:value.color=(0,0,0,1)
    tree,owners,_=_tree([front,rear,trunk])
    assert owners[tree.ray_cast(Vector((.5,0,10)),Vector((0,0,-1)))[2]]==front
    for distance in (float('nan'),-1,float('-inf')):
        try: solid_tree.ray_cast(Vector((0,0,10)),Vector((0,0,-1)),distance)
        except ValueError: pass
        else: raise AssertionError('Invalid distance accepted')
    # Oblique miss rays must remain misses through the opacity wrapper; an
    # explicit infinite BVH distance can instead produce non-finite UV hits.
    direction=Vector((0,.819152,-.573576)).normalized()
    for x in range(-10,11):
        origin=Vector((x, -20, 15))
        default=solid_tree.ray_cast(origin,direction)
        bounded=solid_tree.ray_cast(origin,direction,1000)
        assert (default[0] is None)==(bounded[0] is None),(x,default,bounded)
    print('PASS: front/back physical cutout holes reveal trunk or background; solid/shadow/source rays agree; ownership remains independent')

if __name__=='__main__':check()
