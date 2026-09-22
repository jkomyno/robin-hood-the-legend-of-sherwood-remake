"""Repair imported village shells while retaining source ownership and UVs.

Run against a prepared worker model. Repairs weld close vertices and close only
planar horizontal or sloping underside openings. Artistic roofs and missing machinery need separate
measured recipes; this pass does not claim to reconstruct those details.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
import bmesh

VERSION = 'village-shells-v2'

def shape(obj):
    return hashlib.sha256(json.dumps({'vertices':[list(v.co) for v in obj.data.vertices], 'faces':[list(p.vertices) for p in obj.data.polygons]},sort_keys=True).encode()).hexdigest()

def repair(obj):
    before = shape(obj)
    transform = [list(row) for row in obj.matrix_world]
    bm = bmesh.new(); bm.from_mesh(obj.data)
    old = {'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges)}
    if obj.get('leicester_shell_recipe') != VERSION:
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.75)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=0.0001)
        # Close only planar, upward-facing boundary cycles. Vertical openings
        # may be deliberate doors/windows and remain untouched for review.
        remaining=set(e for e in bm.edges if e.is_boundary)
        while remaining:
            first=remaining.pop();component={first};front=[first]
            while front:
                edge=front.pop()
                adjacent={other for v in edge.verts for other in v.link_edges if other in remaining}
                remaining-=adjacent;component|=adjacent;front.extend(adjacent)
            vertices={v for e in component for v in e.verts}
            if not all(sum(e in component for e in v.link_edges)==2 for v in vertices):continue
            points=[obj.matrix_world@v.co for v in vertices]
            origin=points[0];normal=None
            for i in range(1,len(points)-1):
                candidate=(points[i]-origin).cross(points[i+1]-origin)
                if candidate.length>0.001:normal=candidate.normalized();break
            if normal is not None and abs(normal.z)>0.25 and max(abs((point-origin).dot(normal)) for point in points)<0.2:
                bmesh.ops.holes_fill(bm, edges=list(component), sides=0)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data);obj.data.update()
        obj['leicester_shell_recipe']=VERSION
    after = {'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges), 'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges), 'degenerate_faces':sum(f.calc_area()<0.0001 for f in bm.faces)}
    bm.free()
    assert transform == [list(row) for row in obj.matrix_world],obj.name
    return {'object':obj.name,'source_node':obj['source_node'],'before':old,'after':after,'before_geometry_sha256':before,'after_geometry_sha256':shape(obj),'transform_drift':0,'inferred_surfaces':'Planar hidden underside closure; not source-visible artwork.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    workspace=a.workspace.resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open prepared model.blend')
    sys.path.insert(0,str(next(p/'level-editor/blender' for p in Path(__file__).resolve().parents if (p/'level-editor/blender/refinement_workspace.py').exists())))
    from refinement_workspace import validate
    validate(workspace)
    targets=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    if not targets:raise ValueError('Missing target meshes')
    report={'recipe':VERSION,'asset_id':config['asset_id'],'objects':[repair(o) for o in targets],'limitations':['This topology pass retains inherited silhouette and intersecting component hypotheses.','Source-supported overhangs, windows and machinery are not reconstructed by this pass.'],'projection_status':'STALE until refinement_workspace modified runs','approval_status':'refinement in progress'}
    validate(workspace)
    (workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection'/'shell-repair.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    print(json.dumps(report))
if __name__=='__main__':main()
