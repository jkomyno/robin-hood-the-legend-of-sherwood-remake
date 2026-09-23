"""Source-traced layered castle gateway and angled discrete portcullis states."""
import sys,json,hashlib,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-castle-gate-arch'
sys.path.insert(0,str(Path(__file__).parent))
# Screen-space samples run from the left foot to the right foot.
PROFILES=[
[(896,1507),(896,1435),(901,1415),(913,1396),(929,1377),(945,1361),(958,1365),(976,1373),(989,1382),(997,1394),(999,1404),(999,1492)],
[(900,1505),(900,1436),(906,1419),(918,1401),(934,1383),(947,1370),(960,1374),(976,1381),(987,1388),(992,1399),(994,1407),(994,1493)],
[(905,1502),(905,1433),(913,1419),(925,1405),(938,1392),(949,1382),(961,1386),(974,1391),(983,1398),(987,1407),(989,1415),(989,1492)],
[(910,1500),(910,1432),(918,1420),(929,1409),(940,1400),(949,1396),(959,1399),(969,1404),(978,1410),(983,1418),(984,1426),(984,1490)]]
DEPTH=[0,3,0,-6]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def native(x,sy,offset=0):
    y=1617-(x-910)*.348+offset
    return (x,y,y-sy)
def refine():
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    from refine_church import replace_native,SIN,COS
    objs=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
    body=next(o for o in objs if o['source_node']=='building-333' and not o.get('animation_state'))
    if body.get('castle_arch_profile_recipe')=='v1':return
    verts=[];faces=[]
    # A single closed wall shell with the stepped aperture incorporated in its
    # boundary: the rear opening is conservative, the measured front is exact.
    outer=PROFILES[0]
    left=882.;right=1025.
    plane=lambda x:1617-(x-910)*.348
    front=[(left,plane(left),108)]+[native(x,y) for x,y in outer]+[(right,plane(right),108),(right,plane(right),275),(left,plane(left),275)]
    # The first/last aperture feet have a sloping source threshold, retained
    # through the back of the tunnel rather than an invented horizontal sill.
    n=len(front);verts+=front+[(x,y-30,z) for x,y,z in front]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    vectors=[Vector((x,z,0)) for x,y,z in front]
    for tri in tessellate_polygon([vectors]):
        ids=[v if isinstance(v,int) else min(range(n),key=lambda i:(vectors[i]-v).length_squared) for v in tri]
        faces.extend([tuple(ids),tuple(n+i for i in reversed(ids))])
    # Bevels/jambs form a closed separate dressed-stone shell meeting the body.
    start=len(verts);m=len(outer)
    rings=[[native(x,y,d) for x,y in p] for p,d in zip(PROFILES,DEPTH)]
    rings += [[(x,y-30,z) for x,y,z in rings[-1]],[(x,y-30,z) for x,y,z in rings[0]]]
    for ring in rings:verts+=ring
    for r in range(len(rings)):
        r2=(r+1)%len(rings)
        for i in range(m-1):faces.append(tuple(start+k for k in (r*m+i,r*m+i+1,r2*m+i+1,r2*m+i)))
    # End sections follow the layered boundary; triangulate their plane.
    for i in [0,m-1]:
        ids=[start+r*m+i for r in range(len(rings))]
        # Feet differ slightly in height across profiles; close with triangles.
        for k in range(1,len(ids)-1):faces.append((ids[0],ids[k],ids[k+1]))
    replace_native(body,verts,faces)
    body['castle_arch_profile_recipe']='v1'
    body['source_trace_note']='Four observed masonry profiles; concealed 30-unit tunnel depth is inferred.'
    for o in objs:
        if not o.get('animation_state'):continue
        # Retain authoritative opaque sprite geometry/RGB but place it in the
        # sloped gateway plane rather than an unrelated screen-facing plane.
        inv=o.matrix_world.inverted()
        for v in o.data.vertices:
            w=o.matrix_world@v.co;x=w.x;y=-w.y*SIN;z=w.z*COS
            delta=-(x-910)*.348-11
            v.co=inv@Vector((x,-(y+delta)/SIN,(z+delta)/COS))
        o['castle_arch_profile_recipe']='v1'
    topology={}
    for o in objs:
        bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        topology[o.name]={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)}
        bm.to_mesh(o.data);bm.free()
    if any(any(v.values()) for v in topology.values()):raise ValueError(topology)
    return topology

def main():
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
    import bpy
    from refinement_workspace import prepare,modified
    old=WORK/'round-4/assets'/ASSET;out=WORK/'round-23/assets'/ASSET
    mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'all'
    if mode not in {'all','modify'}:raise ValueError('Expected all or modify')
    if mode=='all':
        bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
        prepare(out,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',projection_manifest=old/'projection-layers.json',source_mask_manifest=old/'source-masks.json',width=320,height=400,context_padding=35,framing_padding=1.18)
    else:bpy.ops.wm.open_mainfile(filepath=str(out/'baseline.blend'))
    topology=refine()
    from refine_church import fingerprint
    owned=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
    once={o.name:fingerprint(o) for o in owned}
    refine()
    if once!={o.name:fingerprint(o) for o in owned}:raise ValueError('Recipe is not idempotent')
    p=out/'source-masks.json';mask=json.loads(p.read_text());rows=mask['projections']['exterior']['assignments']
    initial=next(a for a in mask['projections']['portcullis-initial']['assignments'] if a.get('projection_component')=='portcullis-initial')
    row=next(a for a in rows if a.get('projection_component')=='portcullis-initial');row.update(copy.deepcopy(initial));row['review_note']='Initial door source is part of the covered artwork; retain exact sprite alpha in the base review as well as endpoint review.'
    p.write_text(json.dumps(mask,indent=2)+'\n')
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
    report=modified(out)
    proof={'source_sha256':sha(WORK/'source-states/covered.png'),'profiles':PROFILES,'depth_offsets':DEPTH,'topology':topology,'idempotent':True,'tooling':tooling,'validation':report,'model_sha256':sha(out/'model.blend'),'limitations':['Measured contours have approximately 2px interpretation uncertainty.','Concealed 30-unit vault depth is inferred; the sprite door is a thin discrete-state extrusion.']}
    (out/'arch-profile-report.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('ARCH_PROFILE_COMPLETE',proof['model_sha256'],flush=True)
if __name__=='__main__':main()
