"""Blender fixture: strict ownership equivalence for explicit material-state twins."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from refinement_review import _state_variant_pairs


def check():
    mesh=bpy.data.meshes.new('variant geometry')
    mesh.from_pydata([(0,0,0),(2,0,0),(0,2,0)],[],[(0,1,2)])
    first=bpy.data.objects.new('covered fixture',mesh)
    second=bpy.data.objects.new('revealed fixture',mesh.copy())
    for obj,state in ((first,'covered'),(second,'revealed')):
        bpy.context.scene.collection.objects.link(obj)
        obj['asset_group']='fixture';obj['source_node']='building-001'
        obj['reveal_component_patch_id']='004';obj['projection_state_variant_state']=state
    first['projection_state_variant_peer']=second.name
    second['projection_state_variant_peer']=first.name
    bpy.context.view_layer.update()
    catalog=[first,second]
    assert _state_variant_pairs(catalog,[first],True)=={first:second}
    assert _state_variant_pairs(catalog,[second],True)=={second:first}
    assert _state_variant_pairs(catalog,catalog,False)=={}
    def reject(displayed):
        try:_state_variant_pairs(catalog,displayed,True)
        except ValueError:return
        raise AssertionError('Invalid variant equivalence accepted')
    reject(catalog)
    second['source_node']='building-002';reject([first]);second['source_node']='building-001'
    second['projection_state_variant_peer']='missing';reject([first]);second['projection_state_variant_peer']=first.name
    second.data.vertices[0].co.x=.01;second.data.update();bpy.context.view_layer.update();reject([first])
    second.data.vertices[0].co.x=0;second.data.update()
    second.location.x=.1;bpy.context.view_layer.update();reject([first])
    print('PASS: explicit one-of-two reciprocal ownership, identical evaluated geometry, no cross-node or default-state fallback')

if __name__=='__main__':check()
