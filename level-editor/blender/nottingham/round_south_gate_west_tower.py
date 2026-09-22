"""Round the south gate western tower while retaining its reviewed source extents.

The user requested a rounder drum. This replaces the six-sided footprint and
roof with a sampled ellipse; the source-facing width, front eave, height and
apex remain fixed. Rear continuation is explicitly inferred and source-unknown.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from refine_castle_secondary import WORK,replace_mesh,sha,write
ASSET='nottingham-south-gate-west-tower'
WORKSPACE=WORK/'round-1/assets'/ASSET


def geometry(native):
    pts=native[215]['points']
    cx=(min(p['x'] for p in pts)+max(p['x'] for p in pts))/2
    rx=(max(p['x'] for p in pts)-min(p['x'] for p in pts))/2
    roof_nodes=[216,217,218,222,223]
    apex_pts=[max(native[n]['points'],key=lambda p:p['z_top']) for n in roof_nodes]
    apex=tuple(sum(p[k] for p in apex_pts)/len(apex_pts) for k in ('x','y','z_top'))
    cy=apex[1];ry=max(p['y'] for p in pts)-cy
    eave=sum(p['z_top'] for p in pts)/len(pts)
    bounds=[math.atan2((p['y']-cy)/ry,(p['x']-cx)/rx)%(2*math.pi) for p in pts]
    cuts=sorted(set([i*2*math.pi/64 for i in range(64)]+bounds))
    def point(t,z=eave):return(cx+rx*math.cos(t),cy+ry*math.sin(t),z)
    ring=[point(t) for t in cuts]
    n=len(ring);vertices=[(x,y,0) for x,y,z in ring]+ring
    faces=[list(reversed(range(n)))]
    vertices.extend([(cx,cy,eave),apex]);center=2*n;tip=2*n+1
    rear_start,rear_end=bounds[4],bounds[5]
    for i,t in enumerate(cuts):
        j=(i+1)%n
        is_rear=rear_start-1e-8 <= t < rear_end-1e-8
        faces.append([n+i,n+j,tip if is_rear else center])
    a=cuts.index(bounds[4])+n;b=cuts.index(bounds[5])+n
    faces.extend([[center,a,tip],[tip,b,center]])
    faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
    output={215:(vertices,faces)}
    owners={216:(1,2),217:(2,3),218:(3,4),222:(0,1),223:(5,0),215:(4,5)}
    for node,(ai,bi) in owners.items():
        if node==215:continue
        start,end=bounds[ai],bounds[bi]
        if end<start:end+=2*math.pi
        angles=[start]+[t for t in cuts+[t+2*math.pi for t in cuts] if start+1e-8<t<end-1e-8]+[end]
        angles=sorted(set(angles));arc=[point(t) for t in angles]
        v=[(cx,cy,eave)]+arc+[apex];tip=len(v)-1
        f=[list(reversed(range(tip)))]+[[i,i+1,tip] for i in range(1,tip-1)]
        f.extend([[0,1,tip],[tip,tip-1,0]])
        if node==215:
            oldv,oldf=output[node];offset=len(oldv);output[node]=(oldv+v,oldf+[[i+offset for i in face] for face in f])
        else:output[node]=(v,f)
    return output,{'center_native':[cx,cy],'radii_native':[rx,ry],'eave_native':eave,'apex_native':apex,
        'ring_vertices':n,'preserved':'Source-facing horizontal extrema, front eave extent, eave height and measured apex',
        'inference':'The formerly flat hidden rear becomes the continuation of the source-facing elliptical drum and cone'}


def main():
    from freeze_tooling import select_tooling
    tooling=select_tooling()
    from render_slots import acquire
    acquire()
    import bpy
    from mathutils import Vector
    from refinement_workspace import validate,modified,_geometry
    workspace=WORKSPACE
    config=json.loads((workspace/'workspace.json').read_text())
    history=workspace/'inspection/rounder-drum-prior-revision'
    if not history.exists():
        history.mkdir(parents=True)
        for name in ['model.blend','candidate.json','validation.json']:
            shutil.copy2(workspace/name,history/name)
        shutil.copytree(workspace/'modified',history/'modified')
        write(history/'hashes.json',{str(p.relative_to(history)):sha(p) for p in history.rglob('*') if p.is_file()})
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    validate(workspace)
    collection=bpy.data.collections[config['collection_name']]
    objects=list(collection.all_objects)
    targets={int(o['source_node'].split('-')[-1]):o for o in objects if o.type=='MESH' and o.get('asset_group')==ASSET}
    if set(targets)!={215,216,217,218,222,223}:raise ValueError('Unexpected tower ownership')
    outside={o.name:_geometry(o) for o in objects if o not in targets.values()}
    native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    generated,parameters=geometry(native)
    changes=[];sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    for number,obj in targets.items():
        matrix=obj.matrix_world.copy();before=_geometry(obj);v,f=generated[number]
        inv=matrix.inverted();verts=[inv@Vector((x,-y/sine,z/cosine)) for x,y,z in v]
        report=replace_mesh(obj,verts,f)
        if matrix!=obj.matrix_world:raise ValueError('Tower transform changed')
        changes.append({'source_node':obj['source_node'],'before_sha256':before,'after_sha256':_geometry(obj),**report})
    if any(_geometry(bpy.data.objects[name])!=value for name,value in outside.items()):raise ValueError('Outside geometry changed')
    write(workspace/'inspection/rounder-drum-recipe.json',{'version':1,'asset_id':ASSET,
        'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),'tooling':tooling,
        'parameters':parameters,'changes':changes,'world_transform_drift':0,'outside_objects_preserved':len(outside),
        'user_request':'South gate western tower should be rounder; this is a revision request, not geometry approval.'})
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    modified(workspace)
    write(workspace/'candidate.json',{'version':1,'asset_id':ASSET,'name':'South gate western roofed tower',
        'geometry_refined':True,'geometry_reviewed':False,'status':'refinement-in-progress','inspected_views':[],
        'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),
        'model_sha256':sha(workspace/'model.blend'),'modified_views_sha256':sha(workspace/'modified/views.json'),
        'changes':['Rounded the six-sided drum and roof to a sampled ellipse while preserving source-facing extents and apex.'],
        'limitations':[parameters['inference'],'Decorative corbels, finial and window recesses remain projected detail.'],
        'user_approval':'pending','texture_generation':'not-started','publication':'not-started'})
    (workspace/'review.md').write_text('# South gate western roofed tower\n\nUser-requested rounder drum revision. '+parameters['preserved']+'. '+parameters['inference']+'.\n\nEight modified views require visual review. No approval or texture synthesis recorded.\n')


def finalize():
    candidate=json.loads((WORKSPACE/'candidate.json').read_text())
    if candidate['model_sha256']!=sha(WORKSPACE/'model.blend') or candidate['modified_views_sha256']!=sha(WORKSPACE/'modified/views.json'):
        raise ValueError('Review artifacts changed')
    candidate.update(status='ready-for-user',geometry_reviewed=True,inspected_views=list(range(8)),
                     recipe_sha256=sha(__file__),review='All eight solid and textured views inspected: rounded drum and continuous cone, no gaps or clipping; unknown back remains neutral.')
    write(WORKSPACE/'candidate.json',candidate)
    (WORKSPACE/'review.md').write_text('# South gate western roofed tower\n\nThe requested rounder drum and cone are ready for user review. All eight solid/textured views inspected; source-facing width, front eave and apex retained. Hidden rear ellipse continuation is inferred. Frozen input and outside geometry validation pass. This revision request is not approval.\n')


if __name__=='__main__':
    if '--finalize' in sys.argv:finalize()
    else:main()
