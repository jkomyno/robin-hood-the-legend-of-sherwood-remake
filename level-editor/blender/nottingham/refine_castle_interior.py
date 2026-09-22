"""Source-aligned hall furniture and hanging fixture with explicit hidden depth."""
import json
import math
from pathlib import Path


def refine(workspace):
    import bpy
    from mathutils import Vector
    from refine_castle_secondary import replace_mesh
    work=Path(__file__).resolve().parents[2]/'work/nottingham-refinement'
    native=json.loads((work/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    collection=bpy.data.collections['nottingham Working']
    sources={int(o['source_node'][9:]):o for o in collection.all_objects
             if o.type=='MESH' and o.get('asset_group')=='nottingham-castle-main-hall'
             and not o.get('castle_hall_generated')}
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    rows=[]
    stair=sources[500]
    if stair.get('castle_refinement') != 'nottingham-castle-measured-stairs-v1':
        from refine_castle import stairs
        result=stairs(stair,9)
        rows.append({'source_node':'building-500','change':'Nine-riser continuation of measured exposed stair pitch',
            'visible_edge_fractions':[.054,.162,.280,.380],
            'modeled_edge_fractions':[.0438,.1549,.2660,.3771],
            'hidden_count_inferred':True,'evidence':'castle-audit/hall-stair-count-comparison.png',**result})
    def world(x,y,z):return Vector((x,-y/sine,z/cosine))
    def prism(vertices,faces,outline,low,high):
        start=len(vertices); n=len(outline)
        vertices.extend(world(x,y,z) for z in (low,high) for x,y in outline)
        faces.extend([tuple(reversed(range(start,start+n))),tuple(range(start+n,start+2*n))])
        faces.extend((start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n) for i in range(n))
    for number in (378,488,489,490,499,503,508,510,511,512,513,525,526,529):
        obj=sources[number]
        if obj.get('hall_closed_envelope')=='native-closed-v1':continue
        from mathutils.kdtree import KDTree
        old=[obj.matrix_world@v.co for v in obj.data.vertices]
        tree=KDTree(len(old))
        for i,point in enumerate(old):tree.insert(point,i)
        tree.balance()
        points=native[number]['points'];count=len(points)
        vertices=[world(p['x'],p['y'],p[key]) for key in ('z_top','z_bottom') for p in points]
        drift=max(tree.find(v)[2] for v in vertices)
        faces=[tuple(range(count)),tuple(reversed(range(count,2*count)))]
        faces.extend((i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count))
        inverse=obj.matrix_world.inverted()
        result=replace_mesh(obj,[inverse@v for v in vertices],faces)
        obj['hall_closed_envelope']='native-closed-v1'
        rows.append({'source_node':obj['source_node'],'change':'Close imported face seams using exact native footprint/top/bottom anchors',
            'maximum_vertex_anchor_drift':drift,'world_transform_drift':0,**result})
    for number in (533,534,535):
        obj=sources[number]
        if obj.get('hall_furniture_recipe')=='raised-furniture-v1':continue
        points=native[number]['points']; top=sum(p['z_top'] for p in points)/len(points)
        outline=[(p['x'],p['y']) for p in points]
        cx=sum(x for x,y in outline)/len(outline); cy=sum(y for x,y in outline)/len(outline)
        vertices=[];faces=[]
        if number==533:
            rx=(max(x for x,y in outline)-min(x for x,y in outline))/2
            ry=(max(y for x,y in outline)-min(y for x,y in outline))/2
            outline=[(cx+rx*math.cos(i*math.tau/24),cy+ry*math.sin(i*math.tau/24)) for i in range(24)]
        thickness=3 if number!=535 else top-native[number]['points'][0]['z_bottom']
        prism(vertices,faces,outline,top-thickness,top)
        # Four supports are a depth hypothesis inside the source silhouette.
        corners=[(p['x'],p['y']) for p in points]
        for x,y in corners:
            x=cx+(x-cx)*.7;y=cy+(y-cy)*.7
            prism(vertices,faces,[(x-1.2,y-.7),(x+1.2,y-.7),(x+1.2,y+.7),(x-1.2,y+.7)],420.001,top-thickness)
        inv=obj.matrix_world.inverted()
        result=replace_mesh(obj,[inv@v for v in vertices],faces)
        obj['hall_furniture_recipe']='raised-furniture-v1'
        rows.append({'source_node':obj['source_node'],'change':'Replace below-floor column with seat/tabletop and four inferred supports','legs':4,**result})
    wall=sources[504]
    if wall.get('hall_fireplace_recipe')!='arched-recess-v1':
        from refine_castle_secondary import native_prism
        import bmesh
        native_prism(wall,native[504]['points'],bottom=0)
        aperture=[(390.5,662),(390.5,636),(393,620),(399,610),(408,605),(417,607),(424,614),(427,624),(427,650)]
        a,b=native[504]['points'][8],native[504]['points'][7]
        normal=Vector(((b['y']-a['y'])/-sine,-(b['x']-a['x']),0)).normalized()
        front=[]
        for x,y in aperture:
            native_y=a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])
            front.append(world(x,native_y,native_y-y))
        points=[p+normal for p in front]+[p-normal*4 for p in front]
        count=len(front)
        faces=[tuple(range(count)),tuple(reversed(range(count,2*count)))]
        faces.extend((i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count))
        mesh=bpy.data.meshes.new('Hall fireplace recess cutter')
        mesh.from_pydata(points,[],faces)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        cutter=bpy.data.objects.new('Hall fireplace recess cutter',mesh);collection.objects.link(cutter)
        bpy.context.view_layer.objects.active=wall
        modifier=wall.modifiers.new('Source-measured shallow fireplace recess','BOOLEAN')
        modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
        bm=bmesh.new();bm.from_mesh(wall.data)
        bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);bm.free()
        if bad or deg:raise ValueError(f'Invalid fireplace recess: {bad} nonmanifold edges/{deg} degenerate faces')
        wall['hall_fireplace_recipe']='arched-recess-v1'
        rows.append({'source_node':'building-504','change':'Measured arched shallow fireplace recess',
            'source_aperture':aperture,'inferred_recess_depth':4,'nonmanifold_edges':bad,'degenerate_faces':deg,
            'evidence':'castle-audit/fireplace-source.png'})
    name='building-504__castle-hall-chandelier'
    if not bpy.data.objects.get(name):
        primary=sources[504]; vertices=[];faces=[]
        cx,cy,top,low=503.,1124.,552.,548.
        count=48
        for z in (low,top):
            for rx,ry in ((28.,12.),(24.,9.)):
                vertices.extend(world(cx+rx*math.cos(i*math.tau/count),cy+ry*math.sin(i*math.tau/count),z) for i in range(count))
        for i in range(count):
            j=(i+1)%count
            faces.extend([(i,j,2*count+j,2*count+i),(count+j,count+i,3*count+i,3*count+j),
                          (2*count+i,2*count+j,3*count+j,3*count+i),(j,i,count+i,count+j)])
        def rod(a,b,radius):
            delta=(b-a).normalized();u=delta.cross(Vector((0,0,1)))
            if u.length<.01:u=Vector((1,0,0))
            u.normalize();v=delta.cross(u);start=len(vertices);n=8
            for p in (a,b):vertices.extend(p+radius*(u*math.cos(i*math.tau/n)+v*math.sin(i*math.tau/n)) for i in range(n))
            faces.extend([tuple(reversed(range(start,start+n))),tuple(range(start+n,start+2*n))])
            faces.extend((start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n) for i in range(n))
        anchor=world(cx,cy,630)
        for angle in (0,math.tau/3,2*math.tau/3):
            rod(world(cx+26*math.cos(angle),cy+10.5*math.sin(angle),552),anchor,.65)
        rod(anchor,world(cx,cy,635),1.)
        obj=bpy.data.objects.new(name,primary.data.copy());collection.objects.link(obj)
        obj.parent=primary.parent;obj.matrix_parent_inverse=primary.matrix_parent_inverse.copy();obj.matrix_world=primary.matrix_world.copy()
        for key in primary.keys():obj[key]=primary[key]
        inv=obj.matrix_world.inverted();result=replace_mesh(obj,[inv@v for v in vertices],faces)
        obj['castle_hall_generated']=True;obj['projection_component']='castle-hall-chandelier'
        obj['reveal_component_patch_id']='patch-008';obj['reveal_component_role']='interior-receiver'
        rows.append({'source_node':'building-504','component':'castle-hall-chandelier','change':'Source-centered closed iron ring and three suspension supports',
                     'source_center':[503,574],'native_ring_height':[548,552],**result})
    if rows:
        report_path=Path(workspace)/'interior-detail-report.json'
        if report_path.exists():
            previous=json.loads(report_path.read_text())
            rows=previous.get('changes',[])+rows
        (Path(workspace)/'interior-detail-report.json').write_text(json.dumps({'version':1,'changes':rows,
            'limitations':['Chandelier depth and support angles are inferred from a single projection; candle stems and fine chain links remain texture detail.',
                           'Furniture support positions are inferred inside source bounds; no unknown colors are invented.']},indent=2)+'\n')
    return rows
