"""Reject crossed ground outlines and sloped full-height masonry faces."""
import bpy,json
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'inspection/south-vertical-v13'
def cross(a,b):return a.x*b.y-a.y*b.x
records=[]
for node in ('building-023','building-042'):
    obj=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
    mesh=obj.data;world=[obj.matrix_world@v.co for v in mesh.vertices];bottom=min(p.z for p in world)
    edge_counts={}
    for f in mesh.polygons:
        if max(world[i].z for i in f.vertices)>bottom+.005:continue
        for pair in f.edge_keys:edge_counts[pair]=edge_counts.get(pair,0)+1
    edges=[e for e,n in edge_counts.items() if n==1]
    crossings=[]
    for i,(ia,ib) in enumerate(edges):
        a,b=world[ia].to_2d(),world[ib].to_2d();d=b-a
        for ja,jb in edges[i+1:]:
            if len({ia,ib,ja,jb})<4:continue
            p,q=world[ja].to_2d(),world[jb].to_2d();e=q-p;det=cross(d,e)
            if abs(det)<1e-8:continue
            t=cross(p-a,e)/det;u=cross(p-a,d)/det
            if 1e-5<t<1-1e-5 and 1e-5<u<1-1e-5:crossings.append([ia,ib,ja,jb])
    sloped=[]
    for f in mesh.polygons:
        zs=[world[i].z for i in f.vertices]
        if max(zs)-min(zs)>100 and abs(f.normal.z)>1e-4:sloped.append(f.index)
    rec={'node':node,'ground_outline_edges':len(edges),'ground_crossings':crossings,'sloped_full_height_faces':sloped}
    crown=max(p.z for p in world)
    floors={f.index for f in mesh.polygons if abs(f.normal.z)>.99 and all(crown-30<p.z<crown-15 for p in (world[i] for i in f.vertices))}
    adjacency={}
    for f in mesh.polygons:
        if f.index in floors:
            for pair in f.edge_keys:adjacency.setdefault(pair,[]).append(f.index)
    neighbors={i:set() for i in floors}
    for fs in adjacency.values():
        for i in fs:neighbors[i].update(fs)
    components=[]
    while floors:
        todo=[floors.pop()];component=[]
        while todo:
            i=todo.pop();component.append(i)
            nxt=neighbors[i]&floors;floors-=nxt;todo.extend(nxt)
        components.append(component)
    rec['saved_mesh_opening_floor_components']=len(components)
    assert len(components)==(17 if node=='building-023' else 9),rec
    if node=='building-042':
        original=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==node and o.hide_render and 'modeled battlements' not in o.name)
        ends=[original.matrix_world@original.data.vertices[i].co for i in (37,38)]
        rec['postern_contact_top_error_world']=[min((p-v).length for v in world) for p in ends]
        assert max(rec['postern_contact_top_error_world'])<.002,rec
    records.append(rec)
    print(rec)
(out/'vertical-wall-validation.json').write_text(json.dumps(records,indent=2)+'\n')
assert all(not r['ground_crossings'] and not r['sloped_full_height_faces'] for r in records)
