"""Isolated source-curve vessel revisions; approved workers remain read-only."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys


def run(workspace, profile_path):
    import bpy
    import bmesh
    from mathutils import Vector
    import refinement_workspace as worker
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    profiles=json.loads(Path(profile_path).read_text());profile=next(p for p in profiles.values() if p['asset_id']==config['asset_id'])
    targets,_=worker._ownership(config)
    if len(targets)!=1 or targets[0].get('source_node')!=profile['node']:raise ValueError('Expected exactly the owned vessel')
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open isolated revision worker')
    worker.validate(workspace);obj=targets[0];matrix=obj.matrix_world.copy();inverse=matrix.inverted()
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35));base=profile['base_source_y'];n=profile['segments'];vertices=[]
    for cx,cy,rx,depth in profile['rings']:
        z=(base-cy)/cosine
        for i in range(n):
            t=math.tau*i/n
            world=Vector((cx+rx*math.cos(t),-(base+depth*math.sin(t))/sine,z))
            vertices.append(inverse@world)
    faces=[tuple(reversed(range(n)))]
    for j in range(len(profile['rings'])-1):
        for i in range(n):faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    faces.append(tuple(range((len(profile['rings'])-1)*n,len(profile['rings'])*n)))
    mesh=bpy.data.meshes.new(obj.name+' source-curve fit');mesh.from_pydata(vertices,[],faces);mesh.update()
    for material in obj.data.materials:mesh.materials.append(material)
    mesh.uv_layers.new(name='Source projection pending')
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    topology={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)}
    if any(topology.values()):raise ValueError(str(topology))
    bm.to_mesh(mesh);bm.free();obj.data=mesh
    obj['vessel_source_fit']='joint-native-curve-v1';obj['vessel_source_fit_profile']=json.dumps(profile,sort_keys=True)
    if obj.matrix_world!=matrix:raise ValueError('Object transform drift')
    worker.validate(workspace);bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    (workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection/source-curve-fit.json').write_text(json.dumps({'profile':profile,'topology':topology,'source_projection':'pending shared modified pass','approval':'pending new geometry review'},indent=2)+'\n')
    shutil.copyfile(__file__,workspace/'recipe.py')
    worker.modified(workspace)


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace');p.add_argument('profiles');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.workspace,a.profiles)
