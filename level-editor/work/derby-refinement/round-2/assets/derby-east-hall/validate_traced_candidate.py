import bpy,bmesh,json,hashlib,pickle,sys
from mathutils.kdtree import KDTree
from pathlib import Path
W=Path(__file__).parent;D=W/'next-zigzag-v3'
changed={f'building-{i}' for i in [183,184,185,189,191,192,194,198]}
def capture():
    protected={};lower={};topology={}
    for o in bpy.data.objects:
        if o.type!='MESH':continue
        vs=[o.matrix_world@v.co for v in o.data.vertices]
        if not o.hide_render and o.get('source_node') in changed:
            lower[o.name]=[tuple(v) for v in vs if v.z<365-.01]
            bm=bmesh.new();bm.from_mesh(o.data)
            topology[o.name]=dict(vertices=len(vs),faces=len(o.data.polygons),
                                  degenerate_faces=sum(p.area<1e-8 for p in o.data.polygons),
                                  boundary_edges=sum(e.is_boundary for e in bm.edges),
                                  nonmanifold_edges=sum(not e.is_manifold for e in bm.edges))
            bm.free()
        else:
            data=([list(v) for v in vs],[list(p.vertices) for p in o.data.polygons],o.hide_render)
            protected[o.name]=hashlib.sha256(pickle.dumps(data)).hexdigest()
    return protected,lower,topology
bpy.ops.wm.open_mainfile(filepath=str(W/'next-casement/model.blend'))
before,low_before,before_topology=capture()
candidate=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else D/'traced-runs-candidate.blend'
bpy.ops.wm.open_mainfile(filepath=str(candidate.resolve()))
after,low_after,topology=capture()
protected_changes=[key for key in before.keys()|after.keys() if before.get(key)!=after.get(key)]
lower_missing={};lower_distances={}
for key,points in low_before.items():
    target=low_after[key];tree=KDTree(len(target))
    for i,p in enumerate(target):tree.insert(p,i)
    tree.balance();distances=[tree.find(p)[2] for p in points]
    lower_missing[key]=sum(d>.002 for d in distances)
    lower_distances[key]=max(distances,default=0)
result=dict(protected_mesh_count=len(before),protected_changes=protected_changes,
            lower_missing_vertices=lower_missing,lower_max_displacement=lower_distances,topology=topology,before_topology=before_topology)
(D/'candidate-validation.json').write_text(json.dumps(result,indent=2))
assert not protected_changes,protected_changes
assert not any(lower_missing.values()),lower_missing
print(json.dumps(result),flush=True)
