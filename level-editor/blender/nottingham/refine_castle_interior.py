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
    def world(x,y,z):return Vector((x,-y/sine,z/cosine))
    def prism(vertices,faces,outline,low,high):
        start=len(vertices); n=len(outline)
        vertices.extend(world(x,y,z) for z in (low,high) for x,y in outline)
        faces.extend([tuple(reversed(range(start,start+n))),tuple(range(start+n,start+2*n))])
        faces.extend((start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n) for i in range(n))
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
        (Path(workspace)/'interior-detail-report.json').write_text(json.dumps({'version':1,'changes':rows,
            'limitations':['Chandelier depth and support angles are inferred from a single projection; candle stems and fine chain links remain texture detail.',
                           'Furniture support positions are inferred inside source bounds; no unknown colors are invented.']},indent=2)+'\n')
    return rows
