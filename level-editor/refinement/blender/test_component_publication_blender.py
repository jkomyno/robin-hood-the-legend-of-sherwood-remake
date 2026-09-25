"""Blender fixture: split source exports keep exact meshes, identities and footprints."""
from pathlib import Path
import json
import sys
import tempfile
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from export_editor import export_editor, export_asset_library
from verify_publication_assets import verify, gltf


def check():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        collection=bpy.data.collections.new('Fixture Working')
        bpy.context.scene.collection.children.link(collection)
        catalog={'version':2,'map':'Fixture','canonical_owners':{'building-001':'left'},'groups':[]}
        for name,x in [('left',0),('right',10)]:
            catalog['groups'].append({'id':name,'name':name.title(),'parts':[{'obstacle':1,'name':'Shared base','components':['base-'+name]}]})
            mesh=bpy.data.meshes.new(name)
            mesh.from_pydata([(x,0,0),(x+2,0,0),(x+2,3,0),(x,3,0),(x,0,4),(x+2,0,4),(x+2,3,4),(x,3,4)],[],[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)])
            obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj)
            for key,value in {'asset_group':name,'asset_name':name.title(),'part_name':'Shared base','source_node':'building-001','source_obstacle':1,'projection_component':'base-'+name}.items():obj[key]=value
        obstacle={'points':[{'x':x,'y':y,'z_bottom':0,'z_top':100}for x,y in [(-100,-100),(100,-100),(100,100),(-100,100)]],'opaque':True,'solid':True,'mouse':True,'projection_area':[0,0],'show_shadow_polygon':False,'default_material':0,'material_indices':[]}
        level={'sight_obstacles':[obstacle,obstacle]};level_path=root/'level.json';level_path.write_text(json.dumps(level));catalog_path=root/'catalog.json';catalog_path.write_text(json.dumps(catalog))
        report=export_editor('Fixture',root/'fixture.scene.glb',catalog=catalog,level=level)
        export_asset_library('Fixture',root/'assets',level_path,catalog=catalog)
        (root/'stage.json').write_text(json.dumps({'map':report,'generated_materials':{}}))
        verify(root,catalog_path)
        for name in ['left','right']:
            descriptor=json.loads((root/'assets'/name/'asset.json').read_text());part=descriptor['parts'][0]
            assert part['node']=='building-001--component-base-'+name
            assert part['source_node']=='building-001'and part['source_components']==['base-'+name]
            assert part['source_obstacle']==1 and part['obstacle_local_game']['solid']is True
            points=part['obstacle_local_game']['points'];assert max(p['x']for p in points)-min(p['x']for p in points)==2
            assert len(descriptor['components'])==1
            nodes=gltf(root/'assets'/name/'model.glb')['nodes']
            assert len([n for n in nodes if 'mesh'in n])==1
            mesh_node=next(n for n in nodes if 'mesh'in n)
            assert mesh_node['extras']['source_node']=='building-001'
        # A standalone collision scope cannot silently lose its component provenance.
        path=root/'assets/left/asset.json';saved=path.read_text();bad=json.loads(saved);bad['parts'][0]['source_components']=['base-right'];path.write_text(json.dumps(bad))
        try:verify(root,catalog_path)
        except ValueError:pass
        else:raise AssertionError('Accepted mismatched component collision provenance')
        path.write_text(saved)
        bad=json.loads(saved);bad['parts'][0]['obstacle_local_game']['points'][0]['x']-=1000;path.write_text(json.dumps(bad))
        try:verify(root,catalog_path)
        except ValueError:pass
        else:raise AssertionError('Accepted collision expansion outside exported component metadata')
        path.write_text(saved)
        bpy.data.objects['right']['projection_component']='base-left'
        try:export_editor('Fixture',root/'bad.glb',catalog=catalog,level=level)
        except ValueError:pass
        else:raise AssertionError('Accepted overlapping mesh selector')
    print('PASS split map/library mesh subsets, source provenance, component footprints, and tamper rejection')


if __name__=='__main__':check()
