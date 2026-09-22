"""Rebuild south crenels using both cap edges and flat, constant-height crowns."""
import sys,json,math,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(root.parents[4]/'blender')]
import bpy,bmesh
from mathutils import Vector
from derby_asset_lower_west_curtain import _wall
out=root/'inspection/south-cap-fit-v9';out.mkdir(parents=True,exist_ok=True)
observations=json.loads((out/'source-correspondences.json').read_text())['corners']
s,c=math.sin(math.radians(35)),math.cos(math.radians(35))
working=bpy.data.collections['Derby Working']
def fp(o):return hashlib.sha256(json.dumps([[tuple(o.matrix_world@v.co) for v in o.data.vertices],[list(f.vertices) for f in o.data.polygons]]).encode()).hexdigest()
protected={o.name:fp(o) for o in working.objects if o.type=='MESH' and o.get('source_node') not in observations}
def project(p):return Vector((p.x,-p.y*s-p.z*c))
def inverse(q,z):return Vector((q[0],-(q[1]+z*c)/s,z))
def cross(a,b):return a.x*b.y-a.y*b.x
def interpolate(t,rows):
    if t<=rows[0][0]:return rows[0][1].copy()
    for (a,p),(b,q) in zip(rows,rows[1:]):
        if t<=b:return p.lerp(q,(t-a)/(b-a))
    return rows[-1][1].copy()
reports=[]
for node,outer_ids,inner_ids,axis in [('building-023',[76,66,67],[70,69,68],1),('building-042',[35,36],[40,39],0)]:
    old=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
    source=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')==node and o.hide_render and 'modeled battlements' not in o.name)
    pts=[source.matrix_world@v.co for v in source.data.vertices]
    outer=[pts[i] for i in outer_ids];inner=[pts[i] for i in inner_ids];top=max(p.z for p in outer)
    starts=[0.]
    for a,b in zip(outer,outer[1:]):starts.append(starts[-1]+(b-a).length)
    def coordinate(p):
        candidates=[]
        for i,(a,b) in enumerate(zip(outer,outer[1:])):
            d=(b-a).to_2d();length=d.length;d.normalize();normal=Vector((-d.y,d.x))
            if (inner[i]-a).to_2d().dot(normal)<0:normal=-normal
            u=max(0.,min(1.,(p-a).to_2d().dot(d)/length));near=a.lerp(b,u)
            edge=(inner[i+1]-inner[i]).to_2d()
            thickness=cross((inner[i]-near).to_2d(),edge)/cross(normal,edge)
            lateral=(p-near).to_2d().dot(normal)
            candidates.append(((p-near).to_2d().length,starts[i]+u*length,lateral/thickness,near,normal,thickness))
        return min(candidates,key=lambda x:x[0])
    def on_outer(q):
        for i,(a,b) in enumerate(zip(outer,outer[1:])):
            aa,bb=project(a)[axis],project(b)[axis]
            if min(aa,bb)-.01<=q<=max(aa,bb)+.01:return a.lerp(b,(q-aa)/(bb-aa))
        raise ValueError(('source station outside span',q))
    rows=observations[node]
    cuts=[]
    for i,(a,b) in enumerate(zip(outer,outer[1:])):
        lo,hi=sorted((project(a)[axis],project(b)[axis]));intervals=[]
        for left,right in zip(rows[::2],rows[1::2]):
            l,r=sorted((left[0][axis],right[0][axis]));l=max(l,lo-.1);r=min(r,hi+.1)
            if r>l:intervals.append((l,r))
        if node=='building-023' and i==1:intervals += [(1976,1986),(1997,2007),(2018,2028)]
        cuts.append((outer_ids[i],outer_ids[i+1],axis,intervals))
    if node=='building-023':cuts += [(80,76,0,((295,310),)),(79,80,0,((265,274),)),(75,74,0,((267,280),)),(74,73,0,((305,319),))]
    depth=20/c if node=='building-023' else 19.6/c
    result=_wall(source,cuts,notch_depth=depth,allow_corner_cuts=True)
    new=bpy.data.objects[result['object']]
    # Store target near/far rails at the same construction station. Fixed crown
    # Z means every cap stays horizontal; two-edge tracing controls thickness.
    targets_near=[];targets_far=[]
    for near,far,floor in rows:
        station=on_outer(near[axis]);t=coordinate(station)[1]
        targets_near.append((t,inverse(near,top)));targets_far.append((t,inverse(far,top)))
    for p in [outer[0],on_outer(1985) if node=='building-023' else outer[-1]]:
        targets_near.sort(key=lambda x:x[0]);targets_far.sort(key=lambda x:x[0])
        _,t,_,near,n,width=coordinate(p)
        if node=='building-042' and t>targets_near[-1][0]:
            # Continue the traced terminal rails. Snapping back to the old
            # far footprint in the remaining0.4pixel creates a false wedge.
            ta,a=targets_near[-2];tb,b=targets_near[-1]
            tf,af=targets_far[-2];tg,bf=targets_far[-1]
            targets_near.append((t,a.lerp(b,(t-ta)/(tb-ta))))
            targets_far.append((t,af.lerp(bf,(t-tf)/(tg-tf))))
            continue
        targets_near.append((t,near));targets_far.append((t,near+Vector((n.x*width,n.y*width,0))))
    targets_near.sort(key=lambda x:x[0]);targets_far.sort(key=lambda x:x[0])
    bm=bmesh.new();bm.from_mesh(new.data)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=Vector((0,0,190)),plane_no=Vector((0,0,1)),dist=1e-6,clear_inner=False,clear_outer=False)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=Vector((0,0,196)),plane_no=Vector((0,0,1)),dist=1e-6,clear_inner=False,clear_outer=False)
    # Add vertices at every control station before deforming: otherwise a long
    # original face would skip the measured bend and interpolate past it.
    for t,_ in targets_near:
        if t<=.01 or t>=starts[-1]-.01:continue
        for i,(a,b) in enumerate(zip(outer,outer[1:])):
            if starts[i]-.01<=t<=starts[i+1]+.01:
                u=(t-starts[i])/(starts[i+1]-starts[i]);p=a.lerp(b,u);d=(b-a).normalized()
                bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=p,plane_no=d,dist=1e-6,clear_inner=False,clear_outer=False)
                break
    bm.to_mesh(new.data);bm.free()
    before=[v.co.copy() for v in new.data.vertices]
    for v,p in zip(new.data.vertices,before):
        if p.z<=190:continue
        q=project(Vector((p.x,p.y,top)))[axis]
        if node=='building-023' and not 1805<=q<=1985:continue
        if node=='building-042' and not 386<=q<=526:continue
        _,t,fraction,_,_,_=coordinate(p)
        if not -.03<=fraction<=1.03:continue
        target=interpolate(t,targets_near).lerp(interpolate(t,targets_far),fraction)
        # Keep the visible parapet faces vertical down through every notch
        # floor; confine the transition to a narrow band below the openings.
        weight=min(1.,(p.z-190)/6)
        v.co.x=p.x+(target.x-p.x)*weight;v.co.y=p.y+(target.y-p.y)*weight
    bm=bmesh.new();bm.from_mesh(new.data)
    # World Y is around4000; float32 bisect results can differ by several ULPs.
    # Merge below0.001worldunit (<0.001sourcepixel), not a visible shape change.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001)
    bmesh.ops.dissolve_degenerate(bm,dist=1e-6,edges=list(bm.edges))
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.dissolve_degenerate(bm,dist=.001,edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    validation={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces),'volume':bm.calc_volume(signed=True)}
    if validation['degenerate_faces']:
        print('DEGENERATE',[(f.calc_area(),[tuple(v.co) for v in f.verts]) for f in bm.faces if f.calc_area()<1e-8])
    assert validation['nonmanifold_edges']==0 and validation['degenerate_faces']==0 and validation['volume']>0,validation
    bm.to_mesh(new.data);bm.free()
    oldname=old.name;bpy.data.objects.remove(old,do_unlink=True);new.name=oldname
    reports.append({'node':node,'source_corners':rows,'source_visible_gaps':len(rows)//2,'cuts':cuts,'notch_depth_world':depth,'validation':validation})
assert protected=={o.name:fp(o) for o in working.objects if o.type=='MESH' and o.get('source_node') not in observations}
(out/'geometry.json').write_text(json.dumps({'status':'UNREVIEWED_CANDIDATE','protected_meshes_unchanged':len(protected),'walls':reports},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
