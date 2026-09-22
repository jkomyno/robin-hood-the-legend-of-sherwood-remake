"""Close unedited castle envelopes from exact native anchors, then reproject."""
import hashlib
import json
import math
from pathlib import Path
import sys

WORK=Path(__file__).resolve().parents[2]/'work/nottingham-refinement'


def apply(workspace):
    import bpy
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    from refine_castle_secondary import replace_mesh
    from refinement_workspace import modified
    config=json.loads((workspace/'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    rows=[]
    for obj in bpy.data.collections[config['collection_name']].all_objects:
        if obj.type!='MESH' or obj.get('asset_group')!=config['asset_id'] or obj.hide_render:continue
        if obj.get('castle_refinement') or obj.get('secondary_castle_recipe') or obj.get('castle_hall_generated') or obj.get('castle_native_closed'):continue
        number=int(obj['source_node'][9:]);points=native[number]['points'];count=len(points)
        if min(p['z_top']-p['z_bottom'] for p in points)<=.0001:
            raise ValueError(f'Native envelope has zero thickness: {obj.name}')
        old=[obj.matrix_world@v.co for v in obj.data.vertices];tree=KDTree(len(old))
        for i,p in enumerate(old):tree.insert(p,i)
        tree.balance()
        vertices=[Vector((p['x'],-p['y']/sine,p[k]/cosine)) for k in ('z_top','z_bottom') for p in points]
        drift=max(tree.find(v)[2] for v in vertices)
        faces=[tuple(range(count)),tuple(reversed(range(count,2*count)))]
        faces.extend((i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count))
        inverse=obj.matrix_world.inverted();matrix=obj.matrix_world.copy()
        result=replace_mesh(obj,[inverse@v for v in vertices],faces)
        if obj.matrix_world!=matrix:raise ValueError('Native closure changed world transform')
        obj['castle_native_closed']='exact-native-v1'
        rows.append({'source_node':obj['source_node'],'maximum_anchor_drift':drift,'world_transform_drift':0,**result})
    if not rows:return
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    validation=modified(workspace)
    (workspace/'closed-envelope-report.json').write_text(json.dumps({'version':1,'changes':rows,'validation':validation,
        'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
    candidate=workspace/'candidate.json'
    if candidate.exists():
        data=json.loads(candidate.read_text());data['status']='refinement-in-progress';data['geometry_reviewed']=False;data['inspected_views']=[]
        data['model_sha256']=hashlib.sha256((workspace/'model.blend').read_bytes()).hexdigest()
        data['modified_views_sha256']=hashlib.sha256((workspace/'modified/views.json').read_bytes()).hexdigest()
        candidate.write_text(json.dumps(data,indent=2)+'\n')
    print('CLOSED CASTLE ENVELOPES '+config['asset_id'],flush=True)


def main():
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    select_tooling()
    for value in sys.argv[sys.argv.index('--')+1:]:apply(Path(value).resolve())


if __name__=='__main__':main()
