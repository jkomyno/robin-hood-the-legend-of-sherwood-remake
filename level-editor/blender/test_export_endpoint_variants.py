"""Blender regression for explicit endpoint inclusion and common asset anchors.

blender --background --factory-startup --python test_export_endpoint_variants.py
"""
import json
from pathlib import Path
import struct
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from export_editor import export_editor, export_asset_library


def document(path):
    data=path.read_bytes();size,kind=struct.unpack_from('<II',data,12)
    assert kind==0x4E4F534A
    return json.loads(data[20:20+size])


def check():
    collection=bpy.data.collections.new('EndpointFixture Working')
    bpy.context.scene.collection.children.link(collection)
    def component(name,node,hidden,offset=0,group='bridge'):
        mesh=bpy.data.meshes.new(name)
        mesh.from_pydata([(10+offset,20,2),(14+offset,20,2),(10+offset,26,4)],[],[(0,1,2)])
        obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj)
        obj['source_node']=node;obj['asset_group']=group;obj['asset_name']='Bridge';obj['part_name']=name
        obj.hide_render=hidden
        return obj
    initial=component('Reviewed initial leaf','building-001',False)
    applied=component('Reviewed applied leaf','building-002',True,offset=20)
    retained=component('Retained applied collision original','building-002',True,offset=100)
    unrelated=component('Unrelated hidden part','building-003',True,group='other')
    scene=bpy.context.window.scene
    flags={o.name:o.hide_render for o in collection.objects}
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        default=export_editor('EndpointFixture',root/'default/model.glb',asset_id='bridge')
        assert default['parts']==1 and default['meshes']==1
        assert default['asset']['source_origin_scene']==[12.,23.,2.]
        assert default['asset']['anchor']=='horizontal bounds center at lowest geometry point'
        assert default['asset']['parts'][0]['default_hidden'] is False
        pivot=[5.,15.,1.]
        both=export_editor('EndpointFixture',root/'both/model.glb',asset_id='bridge',
                           standalone_pivot=pivot,include_hidden_objects=[applied.name])
        assert both['parts']==2 and both['meshes']==2
        assert both['included_hidden_objects']==[applied.name]
        assert both['asset']['source_origin_scene']==pivot
        assert both['asset']['bounds_local_scene']=={'min':[5.,5.,1.],'max':[29.,11.,3.]}
        hidden={p['node']:p['default_hidden'] for p in both['asset']['parts']}
        assert hidden=={'building-001':False,'building-002':True}
        doc=document(root/'both/model.glb');nodes={n['name']:n for n in doc['nodes']}
        assert retained.name not in nodes and unrelated.name not in nodes
        assert nodes['building-002']['extras']['default_hidden'] is True
        assert nodes[applied.name]['extras']['default_hidden'] is True
        assert nodes['map']['extras']['default_hidden_source_nodes']==['building-002']
        assert 'animations' not in doc
        applied_mesh=doc['meshes'][nodes[applied.name]['mesh']]
        accessor=doc['accessors'][applied_mesh['primitives'][0]['attributes']['POSITION']]
        assert accessor['min']==[25.,5.,1.] and accessor['max']==[29.,11.,3.]
        map_report=export_editor('EndpointFixture',root/'map.glb')
        assert map_report['parts']==1 and map_report['included_hidden_objects']==[]
        map_doc=document(root/'map.glb')
        assert map_doc['accessors'][map_doc['meshes'][0]['primitives'][0]['attributes']['POSITION']]['min']==[10.,20.,2.]
        # Export each endpoint separately with the same anchor; a visibility
        # switch must not silently recenter the mesh or shift its hinge.
        first=export_editor('EndpointFixture',root/'initial/model.glb',asset_id='bridge',standalone_pivot=pivot)
        initial.hide_render=True;applied.hide_render=False
        second=export_editor('EndpointFixture',root/'applied/model.glb',asset_id='bridge',standalone_pivot=pivot)
        assert first['asset']['source_origin_scene']==second['asset']['source_origin_scene']==pivot
        assert second['asset']['bounds_local_scene']['min']==[25.,5.,1.]
        initial.hide_render=False;applied.hide_render=True
        level=root/'level.json'
        level.write_text(json.dumps({'sight_obstacles':[{'points':[{'x':10,'y':20,'z_bottom':0,'z_top':4}]} for _ in range(4)]}))
        library=export_asset_library('EndpointFixture',root/'library',level,
            standalone_pivots={'bridge':pivot},include_hidden_objects=[applied.name])
        descriptor=json.loads((root/'library/bridge/asset.json').read_text())
        assert library['assets']==1 and descriptor['source_origin_scene']==pivot
        assert len(descriptor['parts'])==2 and descriptor['parts'][1]['default_hidden'] is True
        assert len(descriptor['source_origin_game'])==3
        assert all('obstacle_local_game' in part for part in descriptor['parts'])
        for kwargs,name in [({'standalone_pivots':{'unknown':pivot}},'unused-pivot'),
                            ({'include_hidden_objects':['missing']},'unused-name')]:
            try:export_asset_library('EndpointFixture',root/name,level,**kwargs)
            except ValueError:pass
            else:raise AssertionError('Library accepted '+name)
            assert not (root/name).exists()
        # A specifically requested inactive-only group is exported rather than
        # silently ignored because it has no visible mesh.
        hidden_library=export_asset_library('EndpointFixture',root/'hidden-library',level,
            include_hidden_objects=[unrelated.name])
        assert hidden_library['assets']==2
        assert json.loads((root/'hidden-library/other/asset.json').read_text())['parts'][0]['default_hidden'] is True
        subset=export_asset_library('EndpointFixture',root/'subset',level,
            asset_ids=['bridge'],standalone_pivots={'bridge':pivot})
        assert subset['assets']==1
        assert [e['id'] for e in json.loads((root/'subset/index.json').read_text())['assets']]==['bridge']
        for selected in (['missing'],['bridge','bridge'],[]):
            try:export_asset_library('EndpointFixture',root/'invalid-subset',level,asset_ids=selected)
            except ValueError:pass
            else:raise AssertionError('Invalid library subset accepted')
        assert not (root/'invalid-subset').exists()
        cases=[({'include_hidden_objects':['missing']},'missing-name'),
               ({'include_hidden_objects':['building-002']},'source-selector'),
               ({'include_hidden_objects':[unrelated.name]},'wrong-asset'),
               ({'include_hidden_objects':[applied.name,applied.name]},'duplicate'),
               ({'standalone_pivot':[0,float('nan'),0]},'invalid-pivot')]
        for kwargs,name in cases:
            try:export_editor('EndpointFixture',root/name/'model.glb',asset_id='bridge',**kwargs)
            except ValueError:pass
            else:raise AssertionError('Accepted '+name)
            assert not (root/name/'model.glb').exists()
        del applied['source_node']
        try:export_editor('EndpointFixture',root/'unowned/model.glb',asset_id='bridge',include_hidden_objects=[applied.name])
        except ValueError:pass
        else:raise AssertionError('Accepted missing source ownership')
        applied['source_node']='building-002'
        try:export_editor('EndpointFixture',root/'map-pivot.glb',standalone_pivot=pivot)
        except ValueError:pass
        else:raise AssertionError('Accepted standalone pivot for map export')
        # A hidden same-node extra cannot be encoded by one part.hidden flag.
        retained['source_node']='building-001'
        try:export_editor('EndpointFixture',root/'mixed/model.glb',asset_id='bridge',include_hidden_objects=[retained.name])
        except ValueError:pass
        else:raise AssertionError('Accepted mixed canonical part visibility')
        retained['source_node']='building-002'
    assert bpy.context.window.scene==scene
    assert flags=={o.name:o.hide_render for o in collection.objects}
    assert not any(o.name.startswith('Export / ') for o in bpy.data.objects)
    print('PASS: default export, explicit hidden endpoint, retained exclusion, common pivot, ownership failures and source-state preservation')


if __name__=='__main__':check()
