"""Verify a staged revealed material/cover state against the original worker."""
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_staged_handoffs import snapshot, compare_handoff


def verify(stage,handoff_path):
    handoff=json.loads(Path(handoff_path).read_text())
    collection=json.loads(Path(handoff['review_manifest']).read_text())['collection_name']
    group=handoff['asset_id'];patch=handoff['state_trigger']
    bpy.ops.wm.open_mainfile(filepath=handoff['revealed_worker'])
    reference=[r for r in snapshot(collection,True) if r['group']==group and not r['hidden']]
    if not reference:raise ValueError('Empty revealed reference')
    bpy.ops.wm.open_mainfile(filepath=str(Path(stage)/'worker.blend'))
    for obj in bpy.data.collections[collection].all_objects:
        if obj.get('asset_group')!=group or obj.type!='MESH':continue
        if obj.get('reveal_material_states'):
            record=json.loads(obj['reveal_material_states'])
            if record['patch']==patch:
                for face,slot in zip(obj.data.polygons,record['revealed']):face.material_index=slot
        if patch in obj.get('reveal_hide_when_applied',[]):obj.hide_render=True
    actual=[r for r in snapshot(collection,True) if r['group']==group and not r['hidden']]
    drift=compare_handoff(reference,actual)
    result={'status':'PASS','revealed_meshes':len(actual),'maximum_world_coordinate_drift':drift,
            'appearance':'Exact material graphs, assigned atlas bytes, UVs, topology and visibility'}
    (Path(stage)/'revealed-handoff-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':verify(*sys.argv[sys.argv.index('--')+1:])
