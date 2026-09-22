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
ASSETS = ['castle-west-courtyard-wall', 'churchyard-graves', 'castle-gate-west-tower']
LIMITS = {
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
    ready=reviewed and short in ['churchyard-graves','castle-gate-west-tower']
    write(workspace/'candidate.json',{'version':1,'asset_id':config['asset_id'],
        'geometry_reviewed':reviewed,'geometry_refined':True,
        'status':'ready-for-approval' if ready else 'fix-needed' if reviewed else 'refinement-in-progress',
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
    reviewed=({328:[279,282]} if short=='castle-west-courtyard-wall' else {329:[286],331:[286],332:[286]} if short=='castle-gate-west-tower' else {432:[349],433:[348],434:[355]})
    for row in masks['projections']['exterior']['assignments']:
        node=int(row['source_node'].split('-')[-1])
        if node not in reviewed:
            continue
        row.clear()
        row.update({'source_node':f'building-{node:03d}', 'reviewed':True,
            'mask_indices':reviewed[node],'constraint_kind':'reviewed-native-silhouette',
            'native_ownership_reviewed':True,'review_evidence':'castle-secondary-audit/mask overlays',
            'review_note':'Native RGB/mask overlay inspected. Curtain uses upper-wall279 plus west return282; broad278 excluded because it contains foreground foliage, tower roof and stairs. Grave348 includes its fence, but first-hit receiver geometry restricts source pixels to the headstone; 349 and355 tightly follow monument and rear headstone.'})
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
        elif short=='churchyard-graves':
            v,f,e=monument(native[n]['points']) if n==432 else headstone(native[n]['points'],n)
        else:
            continue
        topology=native_mesh(obj,v,f)
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
