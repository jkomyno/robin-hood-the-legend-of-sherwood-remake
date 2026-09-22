"""Close three source-measured roofs and their concealed supporting envelopes."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import shutil
import bpy
import bmesh
from mathutils import Vector
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p/'level-editor/blender/nottingham/freeze_tooling.py').is_file())
WORK = ROOT / 'level-editor/work/nottingham-refinement'
TAG = 'nottingham_town_closed_shells_v1'
SIN = math.sin(math.radians(35))
COS = math.cos(math.radians(35))


def replace(obj, pieces):
    vertices, faces = [], []
    for points in pieces:
        n, offset = len(points), len(vertices)
        vertices.extend(Vector((p['x'], -p['y']/SIN, p[k]/COS))
                        for k in ['z_bottom', 'z_top'] for p in points)
        local = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
        local += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
        faces.extend(tuple(offset+i for i in f) for f in local)
    mesh = bpy.data.meshes.new(obj.name+' / closed measured envelope')
    inverse = obj.matrix_world.inverted()
    mesh.from_pydata([inverse@v for v in vertices], [], faces)
    mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    defects = {'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
               'degenerate_faces': sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(defects.values()): raise ValueError(defects)
    bm.to_mesh(mesh); bm.free()
    mesh.uv_layers.new(name='UVMap')
    for mat in obj.data.materials: mesh.materials.append(mat)
    obj.data = mesh
    obj['projection_min_cosine'] = .18
    return {'source_node': obj['source_node'], 'vertices': len(mesh.vertices),
            'faces': len(mesh.polygons), **defects}


def refine(asset_id):
    objects = {int(o['source_node'].split('-')[-1]): o
               for o in bpy.data.collections['nottingham Working'].all_objects
               if o.type=='MESH' and o.get('asset_group')==asset_id}
    native_path = WORK/'baseline/nottingham.rhp.json'
    native = json.loads(native_path.read_text())['sight_obstacles']
    p = {n: copy.deepcopy(native[n]['points']) for n in objects}
    changes, inference, edits = [], [], {}
    if asset_id=='nottingham-southeast-stone-annex':
        # Preserve the front hip apex and its eave; complete the opposite hips.
        apex = copy.deepcopy(p[51][0])
        ring = copy.deepcopy(p[49])
        for q in ring: q['z_top']=207.751
        triangles = []
        for i in range(4):
            tri = [copy.deepcopy(ring[i]), copy.deepcopy(ring[(i+1)%4]), copy.deepcopy(apex)]
            for q in tri: q['z_bottom']=q['z_top']-2.2
            triangles.append(tri)
        edits={51:[triangles[1]], 52:[triangles[i] for i in [0,2,3]]}
        changes=['Completed all four finite-thickness hip slopes around the measured apex; removed exposed flat wall-top areas behind the two front roof triangles.']
        inference=['Two concealed rear hip slopes follow the existing masonry footprint; roof thickness is inferred as 2.2 source vertical units.']
    elif asset_id=='nottingham-upper-west-house':
        roof=copy.deepcopy(p[164])
        for q in roof:q['z_bottom']=q['z_top']-2.2
        walls=copy.deepcopy(roof)
        for q in walls:q['z_top']=q['z_bottom'];q['z_bottom']=0
        edits={163:[walls],164:[roof]}
        changes=['Replaced the disconnected pitched slice and irregular reverse wall with one closed ground-to-roof support and a thin roof slab sharing all four contact anchors.']
        inference=['Source-hidden rear walls follow the roof footprint. The detached canonical pillar 166 is preserved in place pending grouping review.']
    elif asset_id=='nottingham-west-red-house':
        front=copy.deepcopy(p[96])
        for q in front:q['z_bottom']=q['z_top']-2.2
        right=[copy.deepcopy(front[3]),copy.deepcopy(front[2]),copy.deepcopy(p[95][2])]
        back_left=copy.deepcopy(p[92][3]);back_left['z_top']=131.06201
        back=[copy.deepcopy(right[2]),copy.deepcopy(front[2]),copy.deepcopy(front[1]),back_left]
        left=[copy.deepcopy(front[0]),copy.deepcopy(front[1]),copy.deepcopy(back_left)]
        for piece in [right,back,left]:
            for q in piece:q['z_bottom']=q['z_top']-2.2
        # Lift the flat base just enough to meet the lower roof underside.
        for q in p[92]:q['z_top']=max(v['z_top']-2.2 for v in [front[0],front[3],right[2],back_left])
        edits={95:[right,back,left],96:[front],92:[p[92]]}
        changes=['Completed the orange tiled main roof with closed front, end and reverse slopes sharing exact ridge anchors; removed crossed isolated triangular receivers.']
        inference=['Concealed reverse eave follows the existing rear envelope; thin underside caps and the concealed left gable are inferred. The supporting volume reaches the highest eave underside, with up to 1.6 source units of intentional overlap at the lower eave. Existing dormer 094 and stepped front volumes 088/089 retain their measured source datums; their intersection lines are not openings.']
    else:raise ValueError(asset_id)
    transforms={n:o.matrix_world.copy() for n,o in objects.items()}
    reports=[replace(objects[n],pieces) for n,pieces in edits.items()]
    assert all(objects[n].matrix_world==transforms[n] for n in objects)
    report={'status':'refined','asset_id':asset_id,'objects':reports,'changes':changes,
            'inference':inference+['Unknown reverse pixels remain neutral; faces below 0.18 source-facing cosine are excluded.'],
            'transform_drift':0,'source_native_sha256':hashlib.sha256(native_path.read_bytes()).hexdigest()}
    objects[min(objects)][TAG]=json.dumps(report)
    return report


def main():
    sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
    from freeze_tooling import select_tooling
    from render_slots import acquire
    select_tooling(); acquire()
    from refinement_workspace import modified
    for aid in sys.argv[sys.argv.index('--')+1:]:
        workspace=WORK/'round-1/assets'/aid
        archive=workspace/'inspection/pre-shell-model.blend'
        if not archive.exists():shutil.copy2(workspace/'model.blend',archive)
        bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
        report=refine(aid)
        (workspace/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
        shutil.copy2(__file__,workspace/'recipe.py')
        bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
        result=modified(workspace)
        print(aid,result['status'],flush=True)

if __name__=='__main__':main()
