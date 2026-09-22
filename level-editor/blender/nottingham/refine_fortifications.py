"""Measured Nottingham town-fortification geometry recipes.

Run inside an isolated asset workspace, never on the frozen source scene:
blender --background <asset>/model.blend --python <this-script> -- --asset
nottingham-north-curtain-wall --report <asset>/inspection/geometry-recipe.json
Regenerate source projection and all fixed review cameras after this recipe.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / 'level-editor/work/nottingham-refinement/fortifications-audit'
# Native source-pixel measurements: notches between separately counted merlons.
NORTH_NOTCHES = [(1592,1607),(1632,1647),(1672,1687),(1712,1727),
                 (1752,1767),(1792,1810),(1915,1929),(1953,1967),
                 (1990,2005),(2028,2042),(2066,2080),(1831,1844),(1869,1880)]


def north_wall_geometry(points, pairs=None, measured_notches=None, base=0, notch_depth=13):
    """One connected ribbon with explicit vertical sides at each crenel step."""
    vertices, faces, index = [], [], {}
    def vertex(p):
        key = tuple(round(float(v), 6) for v in p)
        if key not in index:
            index[key] = len(vertices)
            vertices.append(key)
        return index[key]
    def face(coords):
        ids = [vertex(c) for c in coords]
        ids = [v for i,v in enumerate(ids) if v != ids[i-1]]
        if len(set(ids)) >= 3:
            faces.append(ids)
    def lerp(a,b,t,z):
        if isinstance(z,tuple): z=z[0]+(z[1]-z[0])*t
        return (a['x']+(b['x']-a['x'])*t,a['y']+(b['y']-a['y'])*t,z)
    pairs = pairs or [(6,7),(5,8),(4,9),(3,10),(2,11),(1,12),(0,13)]
    def prism(a,b,c,d,lo,hi,z0,z1):
        al,bl=lerp(a,c,lo,z0),lerp(b,d,lo,z0)
        ar,br=lerp(a,c,hi,z0),lerp(b,d,hi,z0)
        atl,btl=lerp(a,c,lo,z1),lerp(b,d,lo,z1)
        atr,btr=lerp(a,c,hi,z1),lerp(b,d,hi,z1)
        face([al,ar,atr,atl]);face([br,bl,btl,btr])
        face([atl,atr,btr,btl]);face([bl,br,ar,al])
        face([bl,al,atl,btl]);face([ar,br,btr,atr])
    for segment, ((ai,bi),(ci,di)) in enumerate(zip(pairs,pairs[1:])):
        a,b,c,d = points[ai],points[bi],points[ci],points[di]
        cuts = [0.0,1.0]
        # Each visible run and the projecting turret have separate measurements.
        notches = measured_notches if measured_notches is not None else NORTH_NOTCHES
        for lo,hi in notches:
            for x in (lo,hi):
                t=(x-a['x'])/(c['x']-a['x'])
                if 0 < t < 1: cuts.append(t)
        cuts=sorted(set(cuts))
        for lo,hi in zip(cuts,cuts[1:]):
            x=a['x']+(c['x']-a['x'])*(lo+hi)/2
            low=(a['z_top']-notch_depth,c['z_top']-notch_depth)
            prism(a,b,c,d,lo,hi,base,low)
            if not any(l < x < r for l,r in notches):
                prism(a,b,c,d,lo,hi,low,(a['z_top'],c['z_top']))
    # Neighboring cells share exact vertices; cancel their internal faces.
    shells={}
    for face_ids in faces:
        key=tuple(sorted(face_ids))
        if key in shells: del shells[key]
        else: shells[key]=face_ids
    faces=list(shells.values())
    return vertices,faces


def stair_geometry(points, count=14):
    """Closed stair with fourteen source-counted risers and horizontal treads."""
    # Native polygon walks top-right, bottom-right, bottom-left, top-left.
    a,c,d,b=points
    height=a['z_top']
    profile=[(0,0),(0,height)]
    for i in range(count):
        t=(i+1)/count
        profile.append((t,height*(1-i/count)))
        profile.append((t,height*(1-(i+1)/count)))
    vertices=[]
    for start,end in ((a,c),(b,d)):
        vertices.extend((start['x']+(end['x']-start['x'])*t,
                         start['y']+(end['y']-start['y'])*t,z)
                        for t,z in profile)
    n=len(profile)
    faces=[list(reversed(range(n))),list(range(n,2*n))]
    faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
    return vertices,faces


def gate_arch_geometry(points, anchors):
    """Extrude the source-measured pointed opening edge through native wall depth."""
    xlo=min(p['x'] for p in points);xhi=max(p['x'] for p in points)
    ymin=min(p['y'] for p in points);ymax=max(p['y'] for p in points)
    top=points[0]['z_top']
    anchors=[(xlo,anchors[0][1])]+[(x,y) for x,y in anchors if xlo<x<xhi]+[(xhi,anchors[-1][1])]
    profile=[(xlo,top),(xhi,top)]+[(x,ymax-y) for x,y in reversed(anchors)]
    verts=[(x,y,z) for y in (ymin,ymax) for x,z in profile]
    n=len(profile);faces=[list(reversed(range(n))),list(range(n,2*n))]
    faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
    return verts,faces


def tower_geometry(spec):
    """Close roof sectors while retaining each existing visible-sector owner."""
    native=spec['native_points'];body=native[str(spec['body'])]
    apex_points=[max(native[str(n)],key=lambda p:p['z_top']) for n in spec['roof']]
    apex=tuple(sum(p[k] for p in apex_points)/len(apex_points) for k in ('x','y','z_top'))
    height=sum(p['z_top'] for p in body)/len(body)
    ring=[(p['x'],p['y'],height) for p in body];center=(apex[0],apex[1],height)
    output={};owned_edges=set()
    for node in spec['roof']:
        corners=sorted(native[str(node)],key=lambda p:p['z_top'])[:2]
        indices=[min(range(len(ring)),key=lambda i:(ring[i][0]-p['x'])**2+(ring[i][1]-p['y'])**2) for p in corners]
        owned_edges.add(tuple(sorted(indices)))
        output[node]=([center,ring[indices[0]],ring[indices[1]],apex],[[0,2,1],[0,1,3],[1,2,3],[2,0,3]])
    n=len(ring);verts=[(x,y,0) for x,y,z in ring]+ring+[center,apex]
    faces=[list(reversed(range(n)))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    for i in range(n):
        j=(i+1)%n
        if tuple(sorted((i,j))) in owned_edges:
            faces.append([2*n,n+i,n+j])
        else:
            # These roof sectors were absent; closing them is explicit hidden inference.
            faces.extend([[n+i,n+j,2*n+1],[2*n,n+i,2*n+1],[n+j,2*n,2*n+1]])
    # Cancel internal radial faces between adjacent inferred sectors.
    unique={}
    for f in faces:
        key=tuple(sorted(f))
        if key in unique: del unique[key]
        else: unique[key]=f
    output[spec['body']]=(verts,list(unique.values()))
    return output


def refine_tower(asset,report_path):
    import bpy,bmesh
    from mathutils import Vector
    evidence=json.loads((AUDIT/'measurements.json').read_text())
    generated=tower_geometry(evidence['towers'][asset]);collection=bpy.data.collections['nottingham Working']
    changes=[];neutral=bpy.data.materials.get('Nottingham Unknown Neutral') or bpy.data.materials.new('Nottingham Unknown Neutral')
    neutral.diffuse_color=(0.45,0.45,0.45,1)
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    for number,(verts,faces) in generated.items():
        node=f'building-{number:03}'
        objects=[o for o in collection.all_objects if o.type=='MESH' and o.get('source_node')==node]
        if len(objects)!=1: raise ValueError('Expected one working '+node)
        obj=objects[0];matrix=[list(row) for row in obj.matrix_world];inverse=obj.matrix_world.inverted()
        mesh=bpy.data.meshes.new(obj.name+' Closed Roof');mesh.from_pydata([inverse@Vector((x,-y/sine,z/cosine)) for x,y,z in verts],[],faces)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        if any(not e.is_manifold for e in bm.edges):raise ValueError('Nonmanifold tower '+node)
        bm.to_mesh(mesh);bm.free();mesh.materials.append(neutral);mesh.uv_layers.new(name='UVMap');old=obj.data;obj.data=mesh
        if old.users==0:bpy.data.meshes.remove(old)
        assert matrix==[list(row) for row in obj.matrix_world]
        obj['source_projection_current']=False
        changes.append({'source_node':node,'object':obj.name,'vertices':len(mesh.vertices),'faces':len(mesh.polygons)})
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    report={'asset_id':asset,'changed_objects':changes,'world_transform_drift':0,'nonmanifold_edges':0,
            'recipe':str(Path(__file__).resolve()),'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_nodes':[f'building-{n:03}' for n in generated],
            'changes':['Rebuilt visible roof wedges as closed sectors above the eaves, removing overlapping full-height wedge volumes.','Closed absent rear roof sectors using native eaves and averaged source-supported apex.'],
            'limitations':['Hidden roof sectors infer continuation between the established eaves and apex.','Round shafts retain the source obstacle facets; curved masonry detail remains an approximation.','Decorative corbels and windows remain projected surface detail.'],
            'projection_current':False,'status':'refinement-in-progress'}
    report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(report,indent=2)+'\n')


def prism_geometry(points, bottom=None, top=None):
    n=len(points)
    vertices=[(p['x'],p['y'],p['z_bottom'] if bottom is None else bottom) for p in points]
    vertices += [(p['x'],p['y'],p['z_top'] if top is None else top) for p in points]
    return vertices,[list(reversed(range(n))),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]


def arch_crenels(points, anchors, notches, front_y):
    """Extruded closed outline combining the aperture and counted parapet gaps."""
    xlo=min(p['x'] for p in points);xhi=max(p['x'] for p in points)
    ys=[min(p['y'] for p in points),max(p['y'] for p in points)]
    height=points[0]['z_top'];top=[(xlo,height)]
    for lo,hi in sorted(notches):
        if xlo<lo<hi<xhi:top.extend([(lo,height),(lo,height-13),(hi,height-13),(hi,height)])
    top.append((xhi,height))
    bottom=[(xlo,front_y-anchors[0][1])]+[(x,front_y-y) for x,y in anchors if xlo<x<xhi]+[(xhi,front_y-anchors[-1][1])]
    profile=top+list(reversed(bottom));n=len(profile)
    return [(x,y,z) for y in ys for x,z in profile],[list(reversed(range(n))),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]


def supplemental_geometry(asset,evidence):
    native=evidence['native_fortifications'];p=lambda n:native[str(n)]
    generated={};notes=[];limits=[]
    if asset=='nottingham-north-gate-gallery':
        points=p(185);left,right=points[2],points[1]
        anchors=[(left['x'],450),(1335,435),(1350,410),(1365,398),(1380,389),(1390,390),(1405,400),(1420,420),(right['x'],432)]
        top=[(0,189.501),(1,189.501)]
        lower=[]
        for x,y in anchors:
            t=(x-left['x'])/(right['x']-left['x'])
            lower.append((t,left['y']+(right['y']-left['y'])*t-y))
        profile=top+list(reversed(lower));n=len(profile);verts=[]
        for a,b in [(points[2],points[1]),(points[3],points[0])]:
            verts.extend((a['x']+(b['x']-a['x'])*t,a['y']+(b['y']-a['y'])*t,z) for t,z in profile)
        faces=[list(reversed(range(n))),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
        generated[185]=(verts,faces)
        rear=p(186);back_profile=[(0,176.667),(1,176.667)]+list(reversed(lower));back=[]
        for a,b in [(rear[2],rear[1]),(rear[3],rear[0])]:
            back.extend((a['x']+(b['x']-a['x'])*t,a['y']+(b['y']-a['y'])*t,z) for t,z in back_profile)
        generated[186]=(back,faces)
        notes=['Extended gallery front timber wall to the roof underside, closing the detached roof gap.','Shaped the passage front soffit to nine source-opening anchors from gallery-arch-grid.png.']
        limits=['Painted window frames and braces remain surface detail.','Gallery passage piers retain their native outline; rear soffit depth is inferred.']
    elif asset=='nottingham-north-gate-tower':
        footprint=p(179)
        generated[181]=prism_geometry(footprint,bottom=209.001,top=280.001)
        # Retain the two visible owners; complete the unseen hip within owner183.
        ring=[(1452.36,498.95,280.001),(1573.3247,462.67432,280.001),
              (1499.46,381.34,280.001),(1378.4985,417.6892,280.001)]
        apex=(1461.5403,414.5855,374.866);center=(apex[0],apex[1],280.001)
        generated[182]=([center,ring[0],ring[1],apex],[[0,2,1],[0,1,3],[1,2,3],[2,0,3]])
        verts=[center]+ring+[apex]
        generated[183]=(verts,[[0,3,2],[2,3,5],[0,4,3],[3,4,5],[0,1,4],[4,1,5],[0,2,5],[1,0,5]])
        notes=['Joined upper timber storey to supporting masonry and roof eaves.','Rebuilt two visible roof owners as closed sectors and completed the hidden rear hip.']
        limits=['Rear roof hip and upper wall continuation are inferred from the visible eaves and supporting shaft.','Timber braces and windows remain projected surface detail.']
    elif asset=='nottingham-north-curtain-wall':
        generated[177]=north_wall_geometry(p(177),[(3,2),(0,1)],evidence['supplement']['north_east_notches'])
        notes=['Added three source-measured crenel gaps east of the round tower; central turret gaps use separately measured source intervals.']
        limits=['End continuation is cropped by the source image; obscured wall beneath round tower remains native.']
    elif asset=='nottingham-southwest-curtain-wall':
        generated[219]=north_wall_geometry(p(219),[(3,4),(2,5),(1,6),(0,7)],evidence['supplement']['southwest_notches'])
        notes=['Carved eight counted gaps in the steep wall run and eight in the diagonal run, preserving their independent phases.']
        limits=['Final horizontal return is hidden behind the roofed gate tower and retains its native solid parapet.','Gap depth follows visible masonry; hidden wall thickness retains the native footprint.']
    elif asset=='nottingham-south-curtain-wall':
        fit=json.loads((AUDIT/'south-crenels-fit.json').read_text());notches=[]
        for segment in fit['segments']:notches.extend(segment['notches'])
        # Use the shared fitted height shift to keep structural joins watertight.
        pts=[{**q,'z_top':q['z_top']+1.5} for q in p(200)]
        notches += [(1398,1410),(1435,1446),(1467,1478),(1503,1514)]
        generated[200]=north_wall_geometry(pts,[(7,8),(6,9),(5,10),(4,11),(3,12),(2,13),(1,14),(0,15)],notches)
        generated[205]=north_wall_geometry(p(205),[(3,2),(0,1)],[(1255+34*i,1268+34*i) for i in range(6)],base=113.75101)
        notes=['Carved parapet gaps with separately fitted phase and pitch on the three long visible wall runs.','Matched curved gate return and rear cross-wall battlements to the source crop.']
        limits=['Stair203 is fully obscured in covered artwork; its ramp remains unchanged until a revealed source state supports individual treads.','Native-mask fit error on the three long runs is 0.81–1.61 source pixels; hidden depth is inferred.']
    elif asset=='nottingham-south-gate-arch':
        anchors=evidence['south_arch']['inner_arch_anchors_source'];front_y=max(q['y'] for q in p(213))
        generated[213]=arch_crenels(p(213),anchors,evidence['supplement']['south_arch_notches'],front_y)
        generated[214]=arch_crenels(p(214),anchors,[],front_y)
        notes=['Added three counted crenel gaps to front parapet.','Extended the measured arch opening through the rear walkway so its rectangular underside no longer occludes the passage.']
        limits=['Arch depth and hidden soffit continue the measured front curve through the native walkway thickness.']
    elif asset=='nottingham-south-gate-east-tower':
        spec={'body':206,'roof':[207,208,209,210],
              'native_points':{str(n):p(n) for n in [206,207,208,209,210]}}
        spec['native_points']['206']=p(206)[:7]
        generated.update(tower_geometry(spec))
        generated[204]=north_wall_geometry(p(204),[(3,2),(0,1)],[(1480+34*i,1491+34*i) for i in range(3)])
        generated[212]=north_wall_geometry(p(212),[(3,2),(0,1)],[(1259,1271)])
        notes=['Removed full-height roof wedges from the rear stair turret and completed its closed roof at the eaves.','Carved source-visible battlement gaps into the rear return and short western parapet.']
        limits=['Hidden rear roof sectors infer continuation to the established apex.','The broad front turret parapet is canonically owned by the adjoining southern curtain group.']
    return generated,notes,limits


def refine_supplement(asset,report_path):
    import bpy,bmesh
    from mathutils import Vector
    evidence=json.loads((AUDIT/'measurements.json').read_text())
    generated,notes,limits=supplemental_geometry(asset,evidence)
    if not generated:return
    collection=bpy.data.collections['nottingham Working'];changes=[]
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    neutral=bpy.data.materials.get('Nottingham Unknown Neutral') or bpy.data.materials.new('Nottingham Unknown Neutral');neutral.diffuse_color=(.45,.45,.45,1)
    for number,(verts,faces) in generated.items():
        node=f'building-{number:03}';objs=[o for o in collection.all_objects if o.type=='MESH' and o.get('source_node')==node]
        if len(objs)!=1:raise ValueError('Expected one working '+node)
        obj=objs[0];matrix=[list(r) for r in obj.matrix_world];inverse=obj.matrix_world.inverted()
        mesh=bpy.data.meshes.new(obj.name+' Refined Contact');mesh.from_pydata([inverse@Vector((x,-y/sine,z/cosine)) for x,y,z in verts],[],faces)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges)
        if bad:raise ValueError(f'{node}: {bad} nonmanifold edges')
        bm.to_mesh(mesh);bm.free();mesh.materials.append(neutral);mesh.uv_layers.new(name='UVMap');old=obj.data;obj.data=mesh
        if old.users==0:bpy.data.meshes.remove(old)
        assert matrix==[list(r) for r in obj.matrix_world]
        obj['source_projection_current']=False;changes.append({'source_node':node,'object':obj.name,'vertices':len(mesh.vertices),'faces':len(mesh.polygons)})
    report=json.loads(report_path.read_text()) if report_path.exists() else {'asset_id':asset}
    report.update({'supplemental_changes':changes,'changes':notes,'limitations':limits,'world_transform_drift':0,'nonmanifold_edges':0,'projection_current':False,'status':'refinement-in-progress','recipe':str(Path(__file__).resolve()),'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(report,indent=2)+'\n')


def main():
    import bpy
    import bmesh
    from mathutils import Vector
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser();parser.add_argument('--asset',required=True)
    parser.add_argument('--report',type=Path,required=True);opts=parser.parse_args(args)
    blend=Path(bpy.data.filepath).resolve()
    if 'baseline' in blend.parts or blend.name == 'baseline.blend':
        raise ValueError('Recipe refuses to change a frozen baseline')
    if opts.asset in json.loads((AUDIT/'measurements.json').read_text()).get('towers',{}):
        return refine_tower(opts.asset,opts.report)
    if opts.asset in ('nottingham-north-gate-tower','nottingham-north-gate-gallery','nottingham-south-curtain-wall','nottingham-southwest-curtain-wall','nottingham-south-gate-east-tower'):
        return refine_supplement(opts.asset,opts.report)
    collection=bpy.data.collections.get('nottingham Working')
    node={'nottingham-north-curtain-wall':'building-178','nottingham-north-wall-stair':'building-170','nottingham-south-gate-arch':'building-213','nottingham-northwest-curtain-wall':'building-192','nottingham-southwest-wall-stair':'building-221'}[opts.asset]
    candidates=[o for o in bpy.context.scene.objects if o.type=='MESH' and
                o.get('source_node',o.get('source_obstacle'))==node and
                (collection is None or o.name in collection.all_objects)]
    if len(candidates)!=1: raise ValueError('Expected exactly one working '+node)
    obj=candidates[0];before=[list(r) for r in obj.matrix_world]
    evidence=json.loads((AUDIT/'measurements.json').read_text())
    is_wall=node=='building-178'
    if is_wall:
        verts,faces=north_wall_geometry(evidence['north_wall']['native_points'])
    elif node=='building-170':
        verts,faces=stair_geometry(evidence['stairs']['170']['native_points'])
    elif node=='building-221':
        verts,faces=stair_geometry(evidence['stairs']['221']['native_points'],18)
    elif node=='building-192':
        measured=json.loads((AUDIT/'northwest-crenels-fit.json').read_text())
        verts,faces=north_wall_geometry(measured['native_points'],[(1,2),(0,3)],measured['notches'])
    else:
        verts,faces=gate_arch_geometry(evidence['south_arch']['native_points'],evidence['south_arch']['inner_arch_anchors_source'])
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    inverse=obj.matrix_world.inverted()
    local=[inverse@Vector((x,-y/sine,z/cosine)) for x,y,z in verts]
    old=obj.data;mesh=bpy.data.meshes.new(obj.name+' Measured Crenellation')
    mesh.from_pydata(local,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    if nonmanifold: raise ValueError(f'Generated wall has {nonmanifold} nonmanifold edges')
    bm.to_mesh(mesh);bm.free()
    neutral=bpy.data.materials.get('Nottingham Unknown Neutral') or bpy.data.materials.new('Nottingham Unknown Neutral')
    neutral.diffuse_color=(0.45,0.45,0.45,1);mesh.materials.append(neutral)
    mesh.uv_layers.new(name="UVMap")
    obj.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    obj['refinement_recipe']='nottingham/refine_fortifications.py'
    obj['source_projection_current']=False
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report={'asset_id':opts.asset,'recipe':str(Path(__file__).resolve()),
            'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'changed_objects':[obj.name],'source_nodes':[node],
            'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':nonmanifold,
            'world_transform_drift':0 if before==[list(r) for r in obj.matrix_world] else None,
            'repeated_elements':({'west_visible_merlons':6,'east_visible_merlons':5,'notches':13,'east_continuation_notches':3} if is_wall else {'risers':14} if node=='building-170' else {'modeled_risers':18,'hidden_total_inferred':True} if node=='building-221' else {'visible_notches':7} if node=='building-192' else {'opening_anchors':11}),
            'projection_current':False,'status':'refinement-in-progress',
            'limitations':(['Central projecting turret crenels still need count/phase refinement.',
             'Occluded continuation under northeast tower retains a solid parapet.',
             'Hidden depth follows the native obstacle; not visible artwork evidence.',
             'Regenerate full modified packet before review.'] if is_wall else ['Fourteen risers counted on the native source crop; fixed-camera projection requires visual verification.','Hidden stair sides/underside are inferred from obstacle footprint.','Regenerate full modified packet before review.'] if node=='building-170' else ['Visible upper tread pitch supports18-modeled-riser continuation; obscured lower count is inferred.','Hidden underside/side walls follow native footprint.'] if node=='building-221' else ['Seven visible notch intervals fitted to native mask123; mean silhouette error0.61source pixels.','Hidden continuation extrapolates measured period; actual buried repeats remain unknown.'] if node=='building-192' else ['Only front component213 underside is shaped; thickness receiver214 requires inspection for aperture occlusion.','Parapet merlon geometry remains pending.','Arch underside depth is inferred from native wall thickness.','Regenerate full modified packet before review.'])}
    opts.report.parent.mkdir(parents=True,exist_ok=True);opts.report.write_text(json.dumps(report,indent=2)+'\n')
    refine_supplement(opts.asset,opts.report)

if __name__=='__main__':main()
