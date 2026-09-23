"""Rebuild south crenels using both cap edges and flat, constant-height crowns."""
import sys,json,math,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(root.parents[4]/'blender')]
import bpy,bmesh
from mathutils import Vector
from derby_asset_lower_west_curtain import _wall
out=root/'inspection/south-vertical-v13';out.mkdir(parents=True,exist_ok=True)
observations=json.loads((root/'south_cap_source_v13.json').read_text())['corners']
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
for node,outer_ids,inner_ids,axis in [('building-023',[76,66,67],[70,69,68],1),('building-042',[34,35,36],[32,40,39],0)]:
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
    # Fit two parallel source-image rails, retaining each opening station.
    # This avoids turning1pixel annotation noise into a fluted full-height wall.
    independent=1 if node=='building-023' else 0
    dependent=1-independent
    groups=[[row[k] for row in rows] for k in (0,1)]
    means=[(sum(p[independent] for p in group)/len(group),sum(p[dependent] for p in group)/len(group)) for group in groups]
    numerator=sum((p[independent]-mx)*(p[dependent]-my) for group,(mx,my) in zip(groups,means) for p in group)
    denominator=sum((p[independent]-mx)**2 for group,(mx,my) in zip(groups,means) for p in group)
    slope=numerator/denominator;intercepts=[my-slope*mx for mx,my in means]
    def regularize(point,side):
        q=list(point);q[dependent]=slope*q[independent]+intercepts[side];return q
    fit_error=max(abs(regularize(row[k],k)[dependent]-row[k][dependent]) for row in rows for k in (0,1))
    assert fit_error<2,fit_error
    cuts=[]
    for i,(a,b) in enumerate(zip(outer,outer[1:])):
        lo,hi=sorted((project(a)[axis],project(b)[axis]));intervals=[]
        for left,right in zip(rows[::2],rows[1::2]):
            l,r=sorted((left[0][axis],right[0][axis]));l=max(l,lo-.1);r=min(r,hi+.1)
            if r>l:intervals.append((l,r))
        if node=='building-023' and i==1:intervals += [(1960,1970),(1979,1989),(1998,2008),(2017,2027),(2036,2046),(2055,2065)]
        cuts.append((outer_ids[i],outer_ids[i+1],axis,intervals))
    if node=='building-042':
        # Continue every opening across the previously omitted incoming bend.
        cuts += [(34,35,1,((2074,2084),(2094,2104),(2112,2119.2))), (35,36,1,((2118.0,2122),))]
    if node=='building-023':cuts += [(80,76,0,((295,310),)),(79,80,0,((265,274),)),(75,74,0,((267,280),)),(74,73,0,((305,319),))]
    depth=20/c if node=='building-023' else 19.6/c
    print('BUILDING',node,flush=True)
    result=_wall(source,cuts,notch_depth=depth,allow_corner_cuts=True)
    new=bpy.data.objects[result['object']]
    # Store target near/far rails at the same construction station. Fixed crown
    # Z means every cap stays horizontal; two-edge tracing controls thickness.
    targets_near=[];targets_far=[]
    for near,far,floor in rows:
        station=on_outer(near[axis]);t=coordinate(station)[1]
        targets_near.append((t,inverse(regularize(near,0),top)));targets_far.append((t,inverse(regularize(far,1),top)))
    for p in ([outer[0],on_outer(1985)] if node=='building-023' else [outer[0],outer[1],outer[-1]]):
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
    # Add vertices at every control station before deforming: otherwise a long
    # original face would skip the measured bend and interpolate past it.
    for t,_ in targets_near:
        if t<=.01 or t>=starts[-1]-.01:continue
        for i,(a,b) in enumerate(zip(outer,outer[1:])):
            if starts[i]-.01<=t<=starts[i+1]+.01:
                u=(t-starts[i])/(starts[i+1]-starts[i]);p=a.lerp(b,u);d=(b-a).normalized()
                bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=p,plane_no=d,dist=1e-6,clear_inner=False,clear_outer=False)
                break
    if node=='building-042':
        # Subdivide the old straight terminal spur before rebuilding its curved
        # plan. Its far endpoints remain at the protected postern contact.
        for i in range(1,12):
            t=i/12;a=pts[36].lerp(pts[37],t);b=pts[39].lerp(pts[38],t)
            edge=b-a;normal=Vector((-edge.y,edge.x,0))
            bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=a,plane_no=normal,dist=1e-6,clear_inner=False,clear_outer=False)
    bm.to_mesh(new.data);bm.free()
    before=[v.co.copy() for v in new.data.vertices]
    for v,p in zip(new.data.vertices,before):
        if node=='building-042':
            if project(Vector((p.x,p.y,top))).y<=2113.8:continue
            ring=[pts[i].to_2d() for i in (34,35,40,32)]
            signs=[cross(b-a,p.to_2d()-a) for a,b in zip(ring,ring[1:]+ring[:1])]
            if all(d>=-.02 for d in signs) or all(d<=.02 for d in signs):continue
        q=project(Vector((p.x,p.y,top)))[axis]
        if node=='building-023' and not 1805<=q<=1985:continue
        if node=='building-042' and not 375<=q<=526:continue
        _,t,fraction,_,_,_=coordinate(p)
        if not -.03<=fraction<=1.03:continue
        target=interpolate(t,targets_near).lerp(interpolate(t,targets_far),fraction)
        # Apply the corrected plan through the entire wall height. This
        # explicitly changes the footprint instead of introducing a ledge.
        weight=1.
        v.co.x=p.x+(target.x-p.x)*weight;v.co.y=p.y+(target.y-p.y)*weight
    if node=='building-042':
        a,b,far_a,far_b=[pts[i].to_2d() for i in (36,37,39,38)]
        near_start=targets_near[-1][1];far_start=targets_far[-1][1]
        near_end=pts[37];far_end=pts[38]
        near_control=inverse((project(near_start).x,project(near_end).y-6),top)
        far_control=inverse((project(far_start).x+4,project(far_end).y-6),top)
        def bezier(a,control,b,t):return a*((1-t)**2)+control*(2*t*(1-t))+b*(t*t)
        for v,p in zip(new.data.vertices,before):
            q=p.to_2d();u=.5;t=.5
            for _ in range(10):
                near=a.lerp(b,t);far=far_a.lerp(far_b,t);delta=near.lerp(far,u)-q
                du=far-near;dt=(b-a)*(1-u)+(far_b-far_a)*u;det=cross(du,dt)
                if abs(det)<1e-10:break
                u-=cross(delta,dt)/det;t-=cross(du,delta)/det
            if -.0001<=u<=1.0001 and -.0001<=t<=1.0001:
                u=max(0.,min(1.,u));t=max(0.,min(1.,t))
                target=bezier(near_start,near_control,near_end,t).lerp(bezier(far_start,far_control,far_end,t),u)
                v.co.x=target.x;v.co.y=target.y
    max_xy_displacement=max((v.co-p).to_2d().length for v,p in zip(new.data.vertices,before))
    bm=bmesh.new();bm.from_mesh(new.data)
    # World Y is around4000; float32 bisect results can differ by several ULPs.
    # Merge below0.001worldunit (<0.001sourcepixel), not a visible shape change.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001)
    bmesh.ops.dissolve_degenerate(bm,dist=1e-6,edges=list(bm.edges))
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.dissolve_degenerate(bm,dist=.001,edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:
        bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    validation={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces),'volume':bm.calc_volume(signed=True)}
    if validation['degenerate_faces']:
        print('DEGENERATE',[(f.calc_area(),[tuple(v.co) for v in f.verts]) for f in bm.faces if f.calc_area()<1e-8])
    assert validation['nonmanifold_edges']==0 and validation['degenerate_faces']==0 and validation['volume']>0,validation
    bm.to_mesh(new.data);bm.free()
    oldname=old.name;bpy.data.objects.remove(old,do_unlink=True);new.name=oldname
    reports.append({'node':node,'source_corners':rows,'rail_fit':{'slope':slope,'intercepts':intercepts,'max_source_pixel_shift':fit_error},'source_visible_gaps':len(rows)//2,'opening_count_full':17 if node=='building-023' else 9,'cuts':cuts,'notch_depth_world':depth,'footprint_changed':True,'max_xy_displacement':max_xy_displacement,'validation':validation})
assert protected=={o.name:fp(o) for o in working.objects if o.type=='MESH' and o.get('source_node') not in observations}
(out/'geometry.json').write_text(json.dumps({'status':'UNREVIEWED_CANDIDATE','protected_meshes_unchanged':len(protected),'walls':reports},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
