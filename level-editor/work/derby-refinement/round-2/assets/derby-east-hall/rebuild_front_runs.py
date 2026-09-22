"""Rebuild only foreground parapet slabs from explicit artwork corners."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector,Matrix
W=Path(__file__).parent;D=W/'next-zigzag-v3'
traces={r['id']:r for r in json.loads((D/'source-corners.json').read_text())['runs']}
S=math.sin(math.radians(35));C=math.cos(math.radians(35));BASE=365.
western=traces['front-west']['points']+traces['front-south']['points']
eastern=traces['front-east']['points']
footprints=json.loads((D/'footprints.json').read_text())
def measured_depth(run):
    points=traces[run]['points'];a,b=points[0],points[3]
    return (b[0]-a[0],-(b[1]-a[1])/S,0)
west_depth=measured_depth('front-west-cap-depth');east_depth=measured_depth('front-east-cap-depth')
specs={184:[([28,29,27,26],western,west_depth)],
       191:[([28,29,27,26],western,west_depth)],
       192:[([19,16,18,17],western,west_depth)],
       194:[([18,19,17,16],western,west_depth)],
       183:[([4,6,12,13],western,west_depth),
            ([0,2,18,19],eastern,east_depth)],
       189:[([17,18,16,19],eastern,east_depth)]}

def profile_segment(points,left,right):
    points=[p[:] for p in points]
    if left<points[0][0]:
        a,b=points[:2];points.insert(0,[left,a[1]+(left-a[0])*(b[1]-a[1])/(b[0]-a[0])])
    if right>points[-1][0]:
        a,b=points[-2:];points.append([right,b[1]+(right-b[0])*(b[1]-a[1])/(b[0]-a[0])])
    out=[]
    for a,b in zip(points,points[1:]):
        if b[0]<left or a[0]>right:continue
        if a[0]==b[0]:
            if left<=a[0]<=right:out.extend([a,b])
        else:
            for x in [max(left,a[0]),min(right,b[0])]:
                out.append([x,a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])])
    clean=[]
    for p in out:
        if not clean or p!=clean[-1]:clean.append(p)
    return clean

reports=[]
for number,runs in specs.items():
    node=f'building-{number}'
    source=next(o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render and o.get('source_node')==node)
    record=next(r for r in footprints if r['node']==node and (r['hidden'] if number in [183,189,194] else not r['hidden']))
    coords={v[0]:Vector(v[1:]) for v in record['vertices']}
    bm=bmesh.new();bm.from_mesh(source.data)
    bmesh.ops.transform(bm,matrix=source.matrix_world,verts=list(bm.verts))
    before=sorted(tuple(round(c,5) for c in v.co) for v in bm.verts if v.co.z<BASE-.001)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.00001,plane_co=Vector((0,0,BASE)),plane_no=Vector((0,0,1)),clear_outer=True)
    fitted=[]
    def face(vertices):
        area=sum((vertices[i].co-vertices[0].co).cross(vertices[i+1].co-vertices[0].co).length for i in range(1,len(vertices)-1))
        if len(set(vertices))>2 and area>1e-8:
            try:bm.faces.new(vertices)
            except ValueError:pass
    if number==183:
        corner=coords[4].lerp(coords[6],(1415-coords[4].x)/(coords[6].x-coords[4].x))
        tw=corner-coords[4];te=coords[2]-corner
        m=Matrix(((tw.x,-te.x),(tw.y,-te.y)))
        offset=Vector((east_depth[0]-west_depth[0],east_depth[1]-west_depth[1]))
        along=m.inverted()@offset
        miter=corner+Vector(west_depth)+tw*along.x
    for indices,points,depth in runs:
        a,b,ia,ib=[coords[i].copy() for i in indices]
        old_a,old_b,old_ia,old_ib=a.copy(),b.copy(),ia.copy(),ib.copy()
        # The source cap runs to x1337 across the inherited mesh boundary.
        # Keep the lower wall boundary; extend only the parapet slab to its
        # observed shoulder instead of leaving the source step unmodeled.
        if number==194:
            shift=(b-a)*((1337-b.x)/(b.x-a.x));b+=shift;ib+=shift
        if number==183 and indices[0]==4:
            shift=(b-a)*((1337-a.x)/(b.x-a.x));a+=shift;ia+=shift
            b=corner.copy()
        if number==183 and indices[0]==0:a=corner.copy()
        profile=profile_segment(points,a.x,b.x)
        outer=[];inner=[]
        for x,y in profile:
            t=(x-a.x)/(b.x-a.x);p=a.lerp(b,t);p.z=(-y-p.y*S)/C
            q=p+Vector(depth)
            if number==183 and abs(x-corner.x)<.001:
                q=miter.copy();q.z=p.z
            outer.append(bm.verts.new(p));inner.append(bm.verts.new(q))
        ob=[bm.verts.new((v.co.x,v.co.y,BASE)) for v in [outer[0],outer[-1]]]
        ibottom=[bm.verts.new((v.co.x,v.co.y,BASE)) for v in [inner[0],inner[-1]]]
        old_inner=[bm.verts.new((p.x,p.y,BASE)) for p in [old_ia,old_ib]]
        old_outer=[bm.verts.new((p.x,p.y,BASE)) for p in [old_a,old_b]]
        face([ob[0],ob[1],*reversed(outer)])
        face([ibottom[1],ibottom[0],*inner])
        for i in range(len(profile)-1):face([outer[i],outer[i+1],inner[i+1],inner[i]])
        face([ob[0],outer[0],inner[0],ibottom[0]])
        face([outer[-1],ob[1],ibottom[1],inner[-1]])
        face([ibottom[0],ibottom[1],old_inner[1],old_inner[0]])
        face([ob[0],old_outer[0],old_outer[1],ob[1]])
        face([ob[0],ibottom[0],old_inner[0],old_outer[0]])
        face([ob[1],old_outer[1],old_inner[1],ibottom[1]])
        fitted.append(profile)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0005)
    seam=[v for v in bm.verts if abs(v.co.z-BASE)<.001]
    bmesh.ops.remove_doubles(bm,verts=seam,dist=.6)
    for edge in list(bm.edges):
        if not all(abs(v.co.z-BASE)<.001 for v in edge.verts):continue
        first,last=edge.verts;delta=last.co-first.co
        if delta.length_squared<1e-8:continue
        fractions=[]
        for v in list(bm.verts):
            if v in edge.verts or abs(v.co.z-BASE)>.001:continue
            t=(v.co-first.co).dot(delta)/delta.length_squared
            if .00001<t<.99999 and (first.co+delta*t-v.co).length<.6:fractions.append(t)
        previous=0;current=first
        for t in sorted(set(round(t,7) for t in fractions)):
            _,inserted=bmesh.utils.edge_split(edge,current,(t-previous)/(1-previous))
            previous=t;current=inserted
    bmesh.ops.remove_doubles(bm,verts=[v for v in bm.verts if abs(v.co.z-BASE)<.001],dist=.6)
    bm.verts.index_update();groups={}
    for f in list(bm.faces):groups.setdefault(tuple(sorted(v.index for v in f.verts)),[]).append(f)
    for group in groups.values():
        if len(group)>1:
            for f in group:bm.faces.remove(f)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    after=sorted(tuple(round(c,5) for c in v.co) for v in bm.verts if v.co.z<BASE-.001)
    assert before==after,f'Lower vertices changed: {node}'
    materials=list(source.data.materials)
    mesh=bpy.data.meshes.new(node+' / traced foreground slab trial')
    bm.to_mesh(mesh);bm.free()
    for m in materials:mesh.materials.append(m)
    source.data=mesh;source.matrix_world=Matrix.Identity(4)
    source['parapet_trace_trial']='foreground runs only; rear/stair tower outstanding'
    reports.append(dict(node=node,lower_vertices_unchanged=len(before),profiles=fitted))
bpy.ops.wm.save_as_mainfile(filepath=str(D/'front-runs-trial.blend'))
(D/'front-runs-validation.json').write_text(json.dumps(dict(state='Foreground trial; rear and stair tower handled separately',depth=dict(west=west_depth,east=east_depth),runs=reports),indent=2))
