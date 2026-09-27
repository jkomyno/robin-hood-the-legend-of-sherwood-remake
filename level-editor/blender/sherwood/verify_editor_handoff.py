"""Independently compare the legacy scene, migrated worker and exported geometry."""
import json,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils.kdtree import KDTree
EDITOR=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(Path(__file__).parent),str(EDITOR/'refinement'),str(EDITOR/'refinement/blender')]
from editor_catalog import source_node
from lossy_assets import read_glb,accessor_array,mesh_instances
from render_slots import acquire


def points(objects):
    result=[]
    for obj in objects:
        count=len(obj.data.vertices);raw=np.empty(count*3,dtype=np.float64)
        obj.data.vertices.foreach_get('co',raw);matrix=np.array(obj.matrix_world)
        result.append(raw.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3])
    return np.concatenate(result)


def deviation(left,right):
    tree=KDTree(len(left))
    for i,p in enumerate(left):tree.insert(p,i)
    tree.balance()
    return max(tree.find(p)[2] for p in right)


def main(stage):
    stage=Path(stage).resolve();acquire()
    bpy.ops.wm.open_mainfile(filepath=str(stage/'editor-migration.blend'))
    bpy.context.window.scene=bpy.data.scenes['Sherwood Editor Migration']
    original={}
    for c in bpy.data.scenes['Sherwood Refinement'].collection.children:
        if c.hide_render or c.name.startswith(('07','11')):continue
        for obj in c.all_objects:
            if obj.type=='MESH' and not obj.hide_render:
                node=source_node(c.name,{'name':obj.name,'props':{k:str(obj[k]) for k in obj.keys()}})
                original.setdefault(node,[]).append(obj)
    working={}
    groups={}
    for obj in bpy.data.collections['Sherwood Working'].objects:
        if obj.type=='MESH':
            working.setdefault(obj['source_node'],[]).append(obj)
            groups.setdefault(obj['asset_group'],[]).append(obj)
    assert set(original)==set(working)
    worker_max=0
    for node,objects in original.items():
        before,after=points(objects),points(working[node]);assert len(before)==len(after),node
        assert sum(len(o.data.polygons) for o in objects)==sum(len(o.data.polygons) for o in working[node]),node
        drift=max(deviation(before,after),deviation(after,before));assert drift<.001,(node,drift)
        worker_max=max(worker_max,drift)
    rows=[]
    document=json.loads((stage/'sherwood.rhlos-map.json').read_text())
    for ref in document['assetSources']+document['sceneAssets']:
        descriptor=json.loads((stage/'map-assets'/ref['descriptor']).read_text())
        gltf,binary,_=read_glb(stage/'map-assets'/ref['model']);instances=mesh_instances(gltf);exported=[];triangles=0
        for i,m in enumerate(gltf.get('meshes',[])):
            matrix=instances[i]
            for primitive in m['primitives']:
                p=accessor_array(gltf,binary,primitive['attributes']['POSITION'],True)
                exported.append(p@matrix[:3,:3].T+matrix[:3,3]+descriptor.get('source_origin_scene',[0,0,0]))
                triangles+=len(accessor_array(gltf,binary,primitive['indices']))//3
        expected=points(groups[ref['id']]);actual=np.concatenate(exported)
        drift=max(deviation(expected,actual),deviation(actual,expected));assert drift<.001,(ref['id'],drift)
        expected_triangles=0
        for obj in groups[ref['id']]:obj.data.calc_loop_triangles();expected_triangles+=len(obj.data.loop_triangles)
        assert triangles==expected_triangles,(ref['id'],triangles,expected_triangles)
        rows.append({'asset_id':ref['id'],'triangles':triangles,'maximum_world_vertex_drift':drift})
    report={'status':'PASS','native_parts':len(original),'native_to_worker_maximum_world_vertex_drift':worker_max,
            'exported':rows,'source_scene_preserved':True}
    (stage/'handoff-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','assets':len(rows),'maximum_world_vertex_drift':max(r['maximum_world_vertex_drift'] for r in rows)}))

if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1])
