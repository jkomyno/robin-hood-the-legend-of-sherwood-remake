"""Blender fixture for exact texture geometry/planar UV guards and ground export."""
import json
from pathlib import Path
import sys
import tempfile
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from texture_staging import verify_baked_geometry
from export_editor import export_asset_library
from review_evidence import sha


def check():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.name='Fixture Scene'
        collection=bpy.data.collections.new('Fixture Working');bpy.context.scene.collection.children.link(collection)
        mesh=bpy.data.meshes.new('Planar ground');mesh.from_pydata([(0,0,0),(4,0,0),(4,3,0),(0,3,0)],[],[(0,1,2,3)])
        mesh.uv_layers.new(name='UVMap')
        for entry,value in zip(mesh.uv_layers[0].data,[(0,0),(1,0),(1,1),(0,1)]):entry.uv=value
        obj=bpy.data.objects.new('Reviewed ground',mesh);collection.objects.link(obj)
        obj['source_node']='ground';obj['asset_group']='fixture-ground';obj['asset_name']='Fixture Ground'
        source=root/'approved.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source))
        baked=root/'baked.blend';bpy.ops.wm.save_as_mainfile(filepath=str(baked))
        plan={'asset_id':'fixture-ground','object_names':[obj.name],'source_nodes':['ground'],
            'approved_source_blend':str(source),'blend_path':str(baked),'blend_sha256':sha(baked),
            'protected_files':{str(source):sha(source),str(baked):sha(baked)},
            'projection_kind':'planar-atlas','scene_name':'Fixture Scene','collection_name':'Fixture Working'}
        assert verify_baked_geometry(plan)['planar_uv_verified']
        level=root/'level.json';level.write_text('{"sight_obstacles":[]}')
        export_asset_library('Fixture',root/'library',level,asset_ids=['fixture-ground'])
        descriptor=json.loads((root/'library/fixture-ground/asset.json').read_text())
        assert descriptor['parts']==[]
        assert [c['source_node'] for c in descriptor['components']]==['ground']
        # A freshly hashed but modified bake must still fail geometry/UV checks.
        for change in ('uv','geometry'):
            bpy.ops.wm.open_mainfile(filepath=str(source));obj=bpy.data.objects['Reviewed ground']
            if change=='uv':obj.data.uv_layers[0].data[0].uv.x+=.125
            else:obj.location.x+=1
            bpy.ops.wm.save_as_mainfile(filepath=str(baked))
            plan['blend_sha256']=sha(baked);plan['protected_files'][str(baked)]=sha(baked)
            try:verify_baked_geometry(plan)
            except ValueError:pass
            else:raise AssertionError('Accepted changed planar '+change)
    print('PASS: approved/baked geometry, exact planar UV guard and ground GLB with no obstacle parts')


if __name__=='__main__':check()
