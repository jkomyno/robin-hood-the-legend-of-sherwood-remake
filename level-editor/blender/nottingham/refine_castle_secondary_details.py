"""Reproducible, source-counted secondary castle crown and monument refinements.

The fixed packet and its original source ownership stay frozen. Run in Blender
with an asset short name; use --finalize only after inspecting all eight views.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from refine_castle_secondary import WORK, sha, write, replace_mesh
TAG = 'nottingham-secondary-details-v1'
ASSETS = ['castle-west-courtyard-wall', 'churchyard-graves', 'castle-gate-west-tower', 'castle-upper-wall', 'castle-east-courtyard-wall', 'castle-watchtower', 'churchyard-wall', 'castle-courtyard-shelter']
LIMITS = {
    'castle-courtyard-shelter': 'Three closed arched door bays now have shallow recessed panels. Main roof retains its source-facing fascia thickness while the concealed rear underside follows the roof slope. Supports meet the source-measured courtyard datum100. Door recess depth and closed-bay backing are inferred; the separately owned lower lean-to371 and chimney372 retain native geometry.',
    'churchyard-wall': 'The visible boundary now has a projecting coping course and beveled top lip following the native wall bends. Individual stone joints remain painted. The matching profile on the roof/foliage-obscured northern run is an explicit continuity inference; its source pixels remain unassigned and gray.',
    'castle-watchtower': 'Ten major crown capstones are individually anchored to visible artwork. Upper doorway turret has lowered central parapet openings; corner cap continuity on the foliage-obscured rear is inferred. Narrow arrow loops and small coping bevels remain painted. Lower body and hidden tower contacts retain native depths.',
    'castle-east-courtyard-wall': 'Twenty measured crenels replace the continuous crown across the five visible runs. Source-hidden northern section of the eastern return remains continuous rather than inventing a repeat behind the roofed tower. Coping bevels and arrow loops remain painted; narrow return crenel phase needs further close-up review.',
    'castle-upper-wall': 'Upper parapets now have four measured rear-wall crenels, three front-wall crenels, three turret crenels and two lower-landing crenels. Native footprints and floor datum remain unchanged. Curved turret facets, coping bevels and arrow-loop depth remain coarse; this packet requires further silhouette review before approval.',
    'castle-gate-west-tower': 'Eight capstones are counted in the original crown. The drum and crown use smooth interpolated ring contours through source anchors; intermediate hidden curvature is inferred. Arrow loops and coping bevels remain painted. Adjacent gate supports retain their source footprints.',
    'castle-west-courtyard-wall': 'Nine complete central-run crenels plus the western clipped crenel are source measured. Seven western return crenels are fitted to native mask282. The curved turret and eastern bend still lack individually measured battlements; arrow loops remain painted. Hidden curtain depth remains inherited. This is a partial structural refinement, not approval-ready.',
    'churchyard-graves': 'Two headstones now have curved shoulders/crowns and the monument has a tapered plinth, cornice and pitched cap. Tiny cap ornament and surface carving remain painted. Rear profiles and monument tier depths are inferred from the visible silhouette; native footprints and principal cap heights are retained. Tiny high finials are omitted rather than expanding the whole cap to their elevation.',
}


def native_mesh(obj, vertices, faces):
    from mathutils import Vector
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    inv = obj.matrix_world.inverted()
    vertices = [inv @ Vector((x, -y / sine, z / cosine)) for x, y, z in vertices]
    return replace_mesh(obj, vertices, faces)


def west_crown(points):
    from refine_fortifications import north_wall_geometry
    points = copy.deepcopy(points)
    # Native mask278 visible upper-edge plateaus. The old straight collision
    # crown changes phase/height at x586; the artwork continues a shallow slope.
    for a,b in [(3,14),(2,15),(1,16)]:
        x = points[b]['x']
        target = 1356 + (x - 350) * (27 / 350)
        dz = points[b]['y'] - points[b]['z_top'] - target
        for index in (a,b):
            points[index]['z_top'] += dz
    # Notch starts/ends traced from the mask edge and checked against the RGB
    # coping. Preserve small hand-painted spacing variation rather than impose
    # an arbitrary regular count on the entire curtain.
    notches = [(335.2,348), (375,389), (416,430), (458,471), (499,513),
               (541,554), (583,596), (624,638), (666,680), (708,719)]
    pairs = [(8,9),(7,10),(6,11),(5,12),(4,13),(3,14),(2,15),(1,16),(0,17)]
    # Seven fully measured return crenels. A narrow source-facing parapet
    # foreshortens the openings; this independent fit uses mask282 edge jumps.
    from ribbon_crown import arc_ribbon_geometry
    for i in [8,9,7,10]:
        points[i]['z_top']-=4.95991
    return_notches=[(186.47104+i*9.74787,189.56543+i*9.74787) for i in range(1,8)]
    mids=[((points[a]['x']+points[b]['x'])/2,(points[a]['y']+points[b]['y'])/2) for a,b in pairs]
    cumulative=[0.]
    for a,b in zip(mids,mids[1:]):cumulative.append(cumulative[-1]+math.dist(a,b))
    total=cumulative[-1]
    intervals=[]
    for segment,((ai,bi),(ci,di)) in enumerate(zip(pairs,pairs[1:])):
        accepted=return_notches if segment==0 else notches if segment in [5,6] else []
        a,c=points[ai],points[ci]
        for x0,x1 in accepted:
            lo=max(0.,(x0-a['x'])/(c['x']-a['x']))
            hi=min(1.,(x1-a['x'])/(c['x']-a['x']))
            if lo<hi:
                left=(cumulative[segment]+lo*(cumulative[segment+1]-cumulative[segment]))/total
                right=(cumulative[segment]+hi*(cumulative[segment+1]-cumulative[segment]))/total
                intervals.append((left,right))
    vertices,faces=arc_ribbon_geometry(points,pairs,intervals,base=0,notch_depth=12.34659)
    return vertices, faces, {'complete_central_notches':9,'clipped_central_notches':1,
        'measured_return_notches':7,'return_notch_source_x_intervals':return_notches,
        'return_edge_fit_mean_error_pixels':2.37682,
        'notch_source_x_intervals':notches,'notch_depth_native':12.34659,
        'source_mask_indices':[278,282],'source_plateau_anchors':[[350,1356],[700,1383]],
        'change':'Replace continuous central parapet and west return with measured crenels; correct upper-edge slope'}


def gate_crown(native, node):
    """Eight independently selectable, closed crown sectors across two owners."""
    from ribbon_crown import arc_ribbon_geometry
    source=native[331]['points']
    outer=source[:8]
    inner=[source[i] for i in [15,14,13,12,11,10,9,8]]
    def curve(ring,edge,t):
        values=[]
        for key in ('x','y'):
            a,b,c,d=[ring[i%8][key] for i in (edge-1,edge,edge+1,edge+2)]
            values.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
        return {'x':values[0],'y':values[1],'z_top':357.59802}
    if node==329:
        ring=[curve(inner,edge,j/8) for edge in range(8) for j in range(8)]
        n=len(ring)
        vertices=[(p['x'],p['y'],z) for z in (0,330.001) for p in ring]
        faces=[list(reversed(range(n))),list(range(n,2*n))]
        faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
        return vertices,faces,{'change':'Round the tower core through its source ring anchors and match the crown inner surface',
            'ring_samples':64,'inference':'Smooth intermediate circumference is interpolated between native ring anchors'}
    edges=list(range(7)) if node==331 else [7]
    points=[];pairs=[];positions=[]
    for edge in edges:
        for j in range(8):
            positions.append(edge+j/8)
            pairs.append((len(points),len(points)+1));points.extend([curve(outer,edge,j/8),curve(inner,edge,j/8)])
    positions.append(edges[-1]+1)
    pairs.append((len(points),len(points)+1));points.extend([curve(outer,edges[-1],1),curve(inner,edges[-1],1)])
    # One raised capstone occupies each source-counted eighth of the drum.
    # The front closure is the eighth cap and remains canonical source332.
    mid=[((points[a]['x']+points[b]['x'])/2,(points[a]['y']+points[b]['y'])/2) for a,b in pairs]
    lengths=[0.]
    for a,b in zip(mid,mid[1:]):lengths.append(lengths[-1]+math.dist(a,b))
    total=lengths[-1]
    lengths=[x/total for x in lengths]
    def along(t):
        for i in range(len(positions)-1):
            if positions[i]<=t<=positions[i+1]:
                f=(t-positions[i])/(positions[i+1]-positions[i]);return lengths[i]+f*(lengths[i+1]-lengths[i])
        raise ValueError('Crown interval outside segment')
    notches=[]
    for edge in edges:
        notches.extend([(along(edge),along(edge+.22)),(along(edge+.78),along(edge+1))])
    # Merge adjoining low intervals so the repeat belongs to the cap center.
    merged=[]
    for a,b in notches:
        if merged and abs(a-merged[-1][1])<1e-8:merged[-1]=(merged[-1][0],b)
        else:merged.append((a,b))
    vertices,faces=arc_ribbon_geometry(points,pairs,merged,base=0,notch_depth=14)
    return vertices,faces,{'change':'Replace continuous crown with source-counted raised capstones and fourteen-unit crenels',
        'raised_capstones':len(edges),'source_count_total':8,'notch_depth_native':14,
        'source_evidence':'castle-secondary-audit/west-gate-crown-5x.png',
        'inference':'Smooth hidden/intermediate ring depth is interpolated through the source contour anchors'}


def upper_wall(native,node):
    from ribbon_crown import arc_ribbon_geometry
    pts=copy.deepcopy(native[node]['points'])
    if node==365:
        pairs=[(3,2),(0,1)]
        measured={0:[(763,775),(797,809),(830,842),(863,875)]}
        partial={}
    elif node==360:
        pairs=[(0,15),(1,14),(2,13),(3,12),(4,11),(5,10),(6,9),(7,8)]
        measured={0:[(987,1001),(1028,1040),(1068,1081)],3:[(930,946)]}
        partial={1:[(.25,.72)],5:[(.15,.7)]}
    elif node==367:
        pairs=[(1,2),(0,3),(5,4)]
        measured={0:[(687,700),(729,741)]}
        partial={}
    else:
        raise ValueError('Unsupported upper-wall source node')
    mids=[((pts[a]['x']+pts[b]['x'])/2,(pts[a]['y']+pts[b]['y'])/2) for a,b in pairs]
    lengths=[0.]
    for a,b in zip(mids,mids[1:]):lengths.append(lengths[-1]+math.dist(a,b))
    total=lengths[-1]
    intervals=[]
    for segment,((ai,bi),(ci,di)) in enumerate(zip(pairs,pairs[1:])):
        positions=list(partial.get(segment,[]))
        for x0,x1 in measured.get(segment,[]):
            a,c=pts[ai],pts[ci]
            lo,hi=sorted([(x0-a['x'])/(c['x']-a['x']),(x1-a['x'])/(c['x']-a['x'])])
            positions.append((max(0.,lo),min(1.,hi)))
        for lo,hi in positions:
            if lo<hi:intervals.append(((lengths[segment]+lo*(lengths[segment+1]-lengths[segment]))/total,
                                      (lengths[segment]+hi*(lengths[segment+1]-lengths[segment]))/total))
    v,f=arc_ribbon_geometry(pts,pairs,intervals,base=0,notch_depth=13)
    return v,f,{'change':'Replace continuous upper-courtyard parapet with source-counted crenels',
        'crenels':len(intervals),'source_x_intervals_by_segment':measured,'short_turn_intervals':partial,
        'native_notch_depth':13,'source_evidence':'castle-secondary-audit/upper-back-grid.png and upper-front-grid.png',
        'inference':'Concealed cross-wall depth is retained; short turret-turn openings interpolate the measured contour anchors'}


def east_curtain(native):
    from ribbon_crown import arc_ribbon_geometry
    pts=copy.deepcopy(native[326]['points'])
    pairs=[(6,7),(5,8),(4,9),(3,10),(2,11),(1,0)]
    # Each run is counted independently in the source; roof-hidden intervals
    # on the east return have no fabricated repeat.
    specs={0:('x',[(1139,1149),(1162,1171)]),
           1:('y',[(1046,1052),(1069,1075),(1092,1098),(1115,1121)]),
           2:('x',[(1167,1179),(1205,1217),(1244,1256),(1282,1294)]),
           3:('y',[(1348,1354),(1371,1377),(1394,1400),(1418,1424),(1441,1447),(1465,1471)]),
           4:('x',[(1123,1137),(1163,1177),(1203,1217),(1243,1257)])}
    mids=[((pts[a]['x']+pts[b]['x'])/2,(pts[a]['y']+pts[b]['y'])/2) for a,b in pairs]
    lengths=[0.]
    for a,b in zip(mids,mids[1:]):lengths.append(lengths[-1]+math.dist(a,b))
    total=lengths[-1];intervals=[];counts={}
    for segment,((ai,bi),(ci,di)) in enumerate(zip(pairs,pairs[1:])):
        axis,bands=specs[segment];a,c=pts[ai],pts[ci];count=0
        for low,high in bands:
            lo,hi=sorted([(low-a[axis])/(c[axis]-a[axis]),(high-a[axis])/(c[axis]-a[axis])])
            lo,hi=max(0.,lo),min(1.,hi)
            if lo<hi:
                intervals.append(((lengths[segment]+lo*(lengths[segment+1]-lengths[segment]))/total,
                                  (lengths[segment]+hi*(lengths[segment+1]-lengths[segment]))/total));count+=1
        counts[segment]=count
    v,f=arc_ribbon_geometry(pts,pairs,intervals,base=0,notch_depth=13)
    return v,f,{'change':'Cut individually source-counted crenels across five eastern courtyard wall runs',
        'crenels_by_run':counts,'measured_native_axis_intervals':specs,'native_notch_depth':13,
        'source_evidence':'castle-secondary-audit/east-north-grid.png, east-wall-grid.png, east-return-grid.png and east-front-grid.png',
        'inference':'The native wall depth and corner positions are retained; roof-hidden return crown is deliberately unresolved'}


def watchtower_crown(native,node):
    from ribbon_crown import arc_ribbon_geometry
    if node in (539,540):
        pts=copy.deepcopy(native[node]['points'])
        h=pts[0]['z_top']-(14 if node==539 else 0)
        v=[(p['x'],p['y'],z) for z in (820.00104,h) for p in pts];n=len(pts)
        f=[list(reversed(range(n))),list(range(n,2*n))]
        f.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
        return v,f,{'change':'Seat the upper doorway turret on the main roof platform and lower its side parapet opening' if node==539 else 'Seat the upper doorway turret body on the main roof platform instead of extending it through the entire tower',
            'native_notch_depth':14 if node==539 else 0,'native_bottom':820.00104,'inference':'Side opening follows the visible front parapet depth'}
    if node==538:
        pts=copy.deepcopy(native[node]['points']);pairs=[(0,7),(1,6),(2,5),(3,4)]
        mids=[((pts[a]['x']+pts[b]['x'])/2,(pts[a]['y']+pts[b]['y'])/2) for a,b in pairs]
        lengths=[0.]
        for a,b in zip(mids,mids[1:]):lengths.append(lengths[-1]+math.dist(a,b))
        total=lengths[-1]
        intervals=[((a+(b-a)*.24)/total,(a+(b-a)*.76)/total) for a,b in zip(lengths,lengths[1:])]
        v,f=arc_ribbon_geometry(pts,pairs,intervals,base=820.00104,notch_depth=14)
        return v,f,{'change':'Replace continuous upper doorway-turret parapet with three central openings and retained corner caps',
            'crenels':3,'native_notch_depth':14,'inference':'Rear corner continuation is partly obscured by foliage'}
    pts=copy.deepcopy(native[536]['points']);a,b=pts[5],pts[6]
    for index in [13,12]:
        o=pts[index]
        t=((o['x']-a['x'])*(b['x']-a['x'])+(o['y']-a['y'])*(b['y']-a['y']))/((b['x']-a['x'])**2+(b['y']-a['y'])**2)
        pts.append({'x':a['x']+t*(b['x']-a['x']),'y':a['y']+t*(b['y']-a['y']),'z_top':857.273})
    pairs=[(2,3),(1,4),(0,5),(13,14),(12,15),(11,6),(10,7),(9,8)]
    mids=[((pts[a]['x']+pts[b]['x'])/2,(pts[a]['y']+pts[b]['y'])/2) for a,b in pairs]
    lengths=[0.]
    for a,b in zip(mids,mids[1:]):lengths.append(lengths[-1]+math.dist(a,b))
    total=lengths[-1]
    anchors=[(654,210,15),(619,222,14),(585,242,12),(611,270,16),(641,297,16),
             (671,323,15),(713,311,15),(752,297,17),(774,263,14),(749,223,12)]
    caps=[];evidence=[]
    for x,y,halfwidth in anchors:
        closest=None
        for i,(a,b) in enumerate(zip(mids,mids[1:])):
            t=max(0.,min(1.,((x-a[0])*(b[0]-a[0])+(y+857.273-a[1])*(b[1]-a[1]))/math.dist(a,b)**2))
            q=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))
            distance=math.dist(q,(x,y+857.273));d=lengths[i]+t*(lengths[i+1]-lengths[i])
            value=(distance,d)
            if closest is None or value<closest:closest=value
        distance,d=closest
        caps.append((max(0.,(d-halfwidth)/total),min(1.,(d+halfwidth)/total)))
        evidence.append({'source_cap_center':[x,y],'native_halfwidth':halfwidth,
                         'centerline_offset_pixels':distance,'normalized_center':d/total})
    intervals=[];start=0.
    for lo,hi in sorted(caps):
        if lo>start:intervals.append((start,lo))
        start=max(start,hi)
    if start<1:intervals.append((start,1.))
    v,f=arc_ribbon_geometry(pts,pairs,intervals,base=0,notch_depth=14)
    return v,f,{'change':'Replace continuous watchtower crown with ten individually source-anchored capstones',
        'source_counted_capstones':10,'source_cap_anchors':evidence,'native_notch_depth':14,
        'inference':'Native wall thickness retained; intermediate cap cuts follow paired ring interpolation'}


def coping_wall(points):
    ring=[(p['x'],p['y']) for p in points]
    sign=1 if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1]))>0 else -1
    def inset(distance):
        lines=[]
        for a,b in zip(ring,ring[1:]+ring[:1]):
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
            n=(-dy/length*distance*sign,dx/length*distance*sign)
            lines.append(((a[0]+n[0],a[1]+n[1]),(dx,dy)))
        result=[]
        for i,(b,v) in enumerate(lines):
            a,u=lines[i-1];cross=u[0]*v[1]-u[1]*v[0]
            if abs(cross)<1e-9:raise ValueError('Collinear coping corner requires explicit treatment')
            t=((b[0]-a[0])*v[1]-(b[1]-a[1])*v[0])/cross
            result.append((a[0]+u[0]*t,a[1]+u[1]*t))
        return result
    h=points[0]['z_top'];n=len(points)
    levels=[(0,inset(1.5)),(h-6,inset(1.5)),(h-6,ring),(h-2,ring),(h,inset(1))]
    v=[(x,y,z) for z,outline in levels for x,y in outline]
    f=[list(reversed(range(n))),list(range(n*(len(levels)-1),n*len(levels)))]
    for j in range(len(levels)-1):
        f.extend([j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i] for i in range(n))
    return v,f,{'change':'Add projecting six-unit coping course and two-unit beveled top lip to the churchyard boundary',
        'coping_height_native':6,'body_inset_native':1.5,'bevel_height_native':2,
        'inference':'Hidden run repeats the visible front boundary coping profile; individual stone joints remain texture-only'}


def shelter_part(native,node):
    pts=copy.deepcopy(native[node]['points'])
    if node==369:
        # The original narrow pier omits the source-visible first closed bay.
        # Extend it to the adjoining second-bay divider, preserving that contact.
        pts[0]=copy.deepcopy(native[370]['points'][3])
        pts[1]=copy.deepcopy(native[370]['points'][2])
    n=len(pts)
    top=[(p['x'],p['y'],p['z_top'] if node==368 else p['z_top']-16) for p in pts]
    bottom=[(p['x'],p['y'],p['z_top']-16 if node==368 else 100) for p in pts]
    v=top+bottom;f=[list(range(n)),list(reversed(range(n,2*n)))]
    f.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
    return v,f,{'change':'Keep sixteen-unit visible roof fascia with a parallel hidden underside' if node==368 else 'Build closed source-visible door bays on courtyard datum100 and below the roof fascia',
        'native_floor':100,'native_fascia_thickness':16,'front_points':pts,
        'inference':'Closed bay backing and the hidden parallel roof underside are inferred from visible wall and eave contacts'}


def shelter_recesses(obj,points,node):
    import bpy
    import bmesh
    from mathutils import Vector
    # Arched profiles are measured in the repeated door-bay elevation; the
    # shallow backing depth is intentionally recorded as an inference.
    a,b=points[2],points[1]
    rear=points[3]
    dx,dy=rear['x']-a['x'],rear['y']-a['y']
    spans=[(.42,.94)] if node==369 else [(.16,.43),(.68,.95)]
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    inv=obj.matrix_world.inverted()
    for index,(left,right) in enumerate(spans):
        profile=[(left,95),(left,150)]
        for i in range(1,9):
            theta=math.pi*(1-i/8)
            profile.append(((left+right)/2+(right-left)/2*math.cos(theta),150+16*math.sin(theta)))
        profile.append((right,95))
        native_vertices=[(a['x']+t*(b['x']-a['x'])+depth*dx,
                          a['y']+t*(b['y']-a['y'])+depth*dy,z)
                         for depth in (-.015,.045) for t,z in profile]
        vertices=[inv@Vector((x,-y/sine,z/cosine)) for x,y,z in native_vertices]
        n=len(profile);faces=[list(range(n)),list(reversed(range(n,2*n)))]
        faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
        mesh=bpy.data.meshes.new('temporary closed door recess cutter')
        mesh.from_pydata(vertices,[],faces)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        cutter=bpy.data.objects.new('temporary closed door recess cutter',mesh)
        bpy.context.scene.collection.objects.link(cutter);cutter.matrix_world=obj.matrix_world.copy()
        modifier=obj.modifiers.new('Measured arched closed door recess','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
        bpy.data.meshes.remove(mesh)
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bad=sum(not e.is_manifold for e in bm.edges);flat=sum(f.calc_area()<1e-8 for f in bm.faces)
    bm.to_mesh(obj.data);bm.free()
    if bad or flat:raise ValueError(f'Door recess topology invalid: {bad}/{flat}')
    return {'closed_recessed_doors':len(spans),'door_native_spring_height':150,'door_native_arch_height':166,
            'door_depth_fraction_of_bay':.045,'nonmanifold_edges':bad,'degenerate_faces':flat,
            'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons)}


def headstone(points, node):
    # Long front/back edges are native edges1-2 and0-3. Crown remains at the
    # original height; the outline removes unsupported square top corners.
    high = points[0]['z_top']
    crown = [(0,0), (0,.76), (.12,.76), (.12,.84), (.22,.89),
             (.3,.96), (.43,1), (.57,1), (.7,.96), (.78,.89),
             (.88,.84), (.88,.76), (1,.76), (1,0)] if node == 433 else [
             (0,0),(0,.8),(.04,.88),(.14,.95),(.28,.99),(.5,1),
             (.72,.99),(.86,.95),(.96,.88),(1,.8),(1,0)]
    vertices=[]
    for a,b in [(points[1], points[2]), (points[0],points[3])]:
        vertices.extend((a['x']+(b['x']-a['x'])*u, a['y']+(b['y']-a['y'])*u, high*z) for u,z in crown)
    n=len(crown)
    faces=[list(range(n)),list(reversed(range(n,2*n)))]
    faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
    return vertices,faces,{'change': 'Replace rectangular headstone top with source-visible rounded crown and shoulders',
        'measured_height': high, 'outline_profile': crown,
        'inference': 'Extruded rear silhouette follows the visible face across inherited slab thickness'}


def monument(points):
    cx=sum(p['x'] for p in points)/4
    cy=sum(p['y'] for p in points)/4
    h=points[0]['z_top']
    # Source silhouette has a low flared foot, narrow shaft, double projecting
    # cornice and a pitched cap. All rings are nested inside the native footprint.
    levels=[(0,1),(.1,1),(.19,.78),(.69,.78),(.69,.96),(.75,.96),
            (.75,.82),(.82,.82),(.82,.96),(.86,.96)]
    vertices=[(cx+(p['x']-cx)*scale,cy+(p['y']-cy)*scale,h*z) for z,scale in levels for p in points]
    faces=[list(reversed(range(4)))]
    for j in range(len(levels)-1):
        faces.extend([4*j+i,4*j+(i+1)%4,4*(j+1)+(i+1)%4,4*(j+1)+i] for i in range(4))
    # Two-point roof ridge closes the cap without an invented full-size finial.
    ridge=[]
    for a,b in [(points[0],points[1]),(points[2],points[3])]:
        ridge.append((cx+((a['x']+b['x'])/2-cx)*.85,cy+((a['y']+b['y'])/2-cy)*.85,h))
    k=len(vertices);vertices.extend(ridge);q=4*(len(levels)-1)
    faces.extend([[q,q+1,k],[q+1,q+2,k+1,k],[q+2,q+3,k+1],[q+3,q,k,k+1]])
    return vertices,faces,{'change': 'Replace plain grave prism with tapered foot, narrow shaft, double cornice and pitched cap',
        'levels_height_and_footprint_fraction':levels,
        'inference':'Hidden tier depth follows the symmetric native footprint; tiny cap ornament remains texture-only'}


def candidate(workspace, reviewed):
    config=json.loads((workspace/'workspace.json').read_text())
    short=config['asset_id'].removeprefix('nottingham-')
    report=json.loads((workspace/'geometry-report.json').read_text())
    ready=reviewed and short in ['churchyard-graves','castle-gate-west-tower','castle-watchtower','churchyard-wall','castle-courtyard-shelter']
    write(workspace/'candidate.json',{'version':1,'asset_id':config['asset_id'],
        'geometry_reviewed':reviewed,'geometry_refined':True,
        'status':'ready-for-user' if ready else 'fix-needed' if reviewed else 'refinement-in-progress',
        'inspected_views':list(range(8)) if reviewed else [],'recipe':str(Path(__file__).resolve()),
        'model_sha256':sha(workspace/'model.blend'),'modified_views_sha256':sha(workspace/'modified/views.json'),
        'changes':[item['change'] for item in report['changes']], 'limitations':[LIMITS[short]],'user_approval':'pending'})
    (workspace/'review.md').write_text('# '+config['asset_id']+'\n\n'+LIMITS[short]+'\n\n'+
        ('All eight fixed solid and masked source-textured views inspected.' if reviewed else 'All eight fixed views require visual inspection.')+
        '\n\nNo geometry or texture approval recorded; no texture synthesis or publication.\n')


def apply(workspace):
    import bpy
    from refinement_workspace import _geometry, initialize_working_masks, validate, modified
    initialize_working_masks(workspace)
    validate(workspace)
    config=json.loads((workspace/'workspace.json').read_text())
    short=config['asset_id'].removeprefix('nottingham-')
    mask_path=Path(config['source_mask_manifest'])
    masks=json.loads(mask_path.read_text())
    reviewed=({328:[279,282]} if short=='castle-west-courtyard-wall' else {329:[286],331:[286],332:[286]} if short=='castle-gate-west-tower' else {360:[301,303],365:[305]} if short=='castle-upper-wall' else {326:[291,300]} if short=='castle-east-courtyard-wall' else {536:[468],538:[470],539:[470]} if short=='castle-watchtower' else {430:[347]} if short=='churchyard-wall' else {368:[313],369:[313],370:[313]} if short=='castle-courtyard-shelter' else {432:[349],433:[348],434:[355]})
    for row in masks['projections']['exterior']['assignments']:
        node=int(row['source_node'].split('-')[-1])
        if node not in reviewed:
            continue
        row.clear()
        row.update({'source_node':f'building-{node:03d}', 'reviewed':True,
            'mask_indices':reviewed[node],'constraint_kind':'reviewed-native-silhouette',
            'native_ownership_reviewed':True,'review_evidence':'castle-secondary-audit/mask overlays',
            'review_note': {
                'castle-west-courtyard-wall':'RGB/mask overlays inspected. Upper-wall279 and west return282 accepted. Broad278 rejected because it includes foreground foliage, roof and stairs.',
                'castle-gate-west-tower':'RGB/mask286 overlay inspected: upper front crown and drum only. Broad284/285 rejected because they include the foreground cottage roof. Unverified rear and lower surfaces remain unknown.',
                'churchyard-graves':'RGB/mask overlays inspected. Grave348 also includes its fence; source texel ownership restricts acceptance to the modeled headstone. Masks349 and355 follow the monument and rear headstone silhouettes.',
                'castle-upper-wall':'RGB/mask301 and303 overlays independently reviewed for front curtain and turret. Rear curtain uses305 with source-ray receiver ownership; other stair and landing geometry remains separately owned.',
                'castle-courtyard-shelter':'Native313 source silhouette reviewed against the main lean-to roof and three door bays. Per-surface source rays separate roof and facade recipients. Lower lean-to371/chimney372 retain their existing source authority.',
                'churchyard-wall':'Native347 RGB/mask overlay reviewed for the front churchyard wall and coping. The northern roof/foliage-obscured run431 remains unknown; no union mask is used to assign hidden pixels.',
                'castle-watchtower':'RGB/mask468 reviewed for main upper crown and470 for the doorway turret. Broad467/469 withheld to avoid foreground roof and foliage pixels; unsupported lower/back surfaces stay unknown.',
                'castle-east-courtyard-wall':'RGB/mask291 and300 overlays reviewed for the front curtain and upper return. Broad296/298 withheld because they include walkway and shelter roof pixels. Remaining surfaces stay unknown.'
            }[short]})
    write(mask_path,masks)
    objects=list(bpy.data.collections[config['collection_name']].all_objects)
    before={o.name:_geometry(o) for o in objects}
    targets=[o for o in objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    matrices={o.name:tuple(v for row in o.matrix_world for v in row) for o in targets}
    native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    changes=[]
    for obj in targets:
        n=int(obj['source_node'].split('-')[-1])
        if short=='castle-west-courtyard-wall' and n==328:
            v,f,e=west_crown(native[n]['points'])
        elif short=='castle-gate-west-tower' and n in (329,331,332):
            v,f,e=gate_crown(native,n)
        elif short=='castle-upper-wall' and n in (360,365,367):
            v,f,e=upper_wall(native,n)
        elif short=='castle-east-courtyard-wall' and n==326:
            v,f,e=east_curtain(native)
        elif short=='castle-watchtower' and n in (536,538,539,540):
            v,f,e=watchtower_crown(native,n)
        elif short=='churchyard-wall':
            v,f,e=coping_wall(native[n]['points'])
        elif short=='castle-courtyard-shelter' and n in (368,369,370):
            v,f,e=shelter_part(native,n)
        elif short=='churchyard-graves':
            v,f,e=monument(native[n]['points']) if n==432 else headstone(native[n]['points'],n)
        else:
            continue
        topology=native_mesh(obj,v,f)
        if short=='castle-courtyard-shelter' and n in (369,370):
            topology.update(shelter_recesses(obj,e['front_points'],n))
        obj['secondary_details_recipe']=TAG
        changes.append({'source_node':obj['source_node'],'object':obj.name,**e,**topology,
            'before_sha256':before[obj.name],'after_sha256':_geometry(obj)})
    assert all(before[o.name]==_geometry(o) for o in objects if o not in targets), 'Outside-object geometry changed'
    assert all(matrices[o.name]==tuple(v for row in o.matrix_world for v in row) for o in targets), 'Transform changed'
    write(workspace/'geometry-report.json',{'version':1,'asset_id':config['asset_id'],'recipe':str(Path(__file__).resolve()),
        'recipe_sha256':sha(__file__),'changes':changes,'world_transform_drift':0,'outside_objects_preserved':len(objects)-len(targets),
        'native_source_sha256':sha(WORK/'baseline/nottingham.rhp.json'),'limitations':[LIMITS[short]],
        'idempotence':'Each mesh is reconstructed solely from frozen native coordinates and fixed measurements'})
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    modified(workspace)
    candidate(workspace,False)
    if short=='churchyard-graves':
        from refinement_review import render_review
        for obj in targets:
            directory=workspace/'inspection'/('details-v2-'+obj['source_node'])
            # Supplemental close-ups never replace the immutable review packet.
            if not directory.exists():
                render_review(directory,scene_name=config['scene_name'],collection_name=config['collection_name'],
                    asset_id=config['asset_id'],source_path=config['source_path'],width=256,height=320,
                    lighting=json.loads((workspace/'input/views.json').read_text()).get('lighting'),
                    source_mask_manifest=config['source_mask_manifest'],render_object_names=[obj.name])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assets',nargs='+',choices=ASSETS)
    parser.add_argument('--finalize',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
    from freeze_tooling import select_tooling
    select_tooling()
    if not args.finalize:
        from render_slots import acquire
        acquire()
    for short in args.assets:
        workspace=WORK/'round-1/assets'/('nottingham-'+short)
        if args.finalize:
            candidate(workspace,True)
        else:
            import bpy
            bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
            apply(workspace)
        print('SECONDARY DETAILS COMPLETE '+short,flush=True)


if __name__=='__main__':
    main()
