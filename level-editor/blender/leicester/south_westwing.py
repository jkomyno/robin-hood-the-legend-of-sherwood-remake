"""Native western corridor cutaway with a separately attributed floor receiver."""
import argparse
import json
import math
from pathlib import Path
import sys
import uuid

import bpy
import bmesh
from mathutils import Vector

DIRECTORY=Path(__file__).resolve().parent
sys.path.insert(0,str(DIRECTORY));sys.path.insert(0,str(DIRECTORY.parent))
from south_structures import cap_prism, neutral_mesh, topology
from south_cutaway import boundary
from refinement_workspace import initialize_working_projection, modified

TAG='leicester-west-corridor-v1'
PATCH='patch-000'
FLOOR_PIXELS=[(568,961),(592,938),(600,941),(614,916),(624,921),(635,912),
              (667,921),(647,958),(661,967),(679,1006),(672,1015),(593,1004),(583,993)]


def close(obj):
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.5)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-5)
    seen=set();duplicates=[];bm.verts.index_update()
    for face in bm.faces:
        key=tuple(sorted(v.index for v in face.verts))
        if key in seen:duplicates.append(face)
        seen.add(key)
    if duplicates:bmesh.ops.delete(bm,geom=duplicates,context='FACES_ONLY')
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    return topology(obj)


def tag(obj,component):
    obj['projection_component']=component
    obj['reveal_component_role']=component
    obj['reveal_component_patch_id']=PATCH
    obj['south_westwing']=TAG
    return {'source_node':obj['source_node'],'projection_component':component,'patch_id':PATCH}


def receivers_and_chandelier(workspace):
    collection=bpy.data.collections['Leicester Working']
    objects=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')=='leicester-west-wing' and not o.hide_render]
    if any(o.get('projection_component')=='corridor-chandelier' for o in objects):
        raise RuntimeError('Corridor receivers already installed; inspect saved candidate')
    path=Path(initialize_working_projection(workspace));manifest=json.loads(path.read_text());review=manifest['projection_reviews'][PATCH]
    masks_path=Path(workspace)/'source-masks.json';masks=json.loads(masks_path.read_text());assignments=masks['projections']['interior-patch-000']['assignments']
    for node,indices in ((223,[342,343]),(233,[336]),(235,[338,340,350]),(237,[342]),(241,[342,343])):
        obj=next(o for o in objects if o['source_node']==f'building-{node:03}')
        tag(obj,'retained-interior')
        review['receiver_nodes'].append(obj['source_node'])
        review['receiver_components']['interior-'+PATCH].append({'source_node':obj['source_node'],'projection_components':['retained-interior'],'patch_id':PATCH})
        assignments.append({'source_node':obj['source_node'],'mask_indices':indices,'exclude_mask_indices':[337],
                            'reviewed':True,'exclusions_reviewed':True,'exclusion_reason':'Independent chandelier receiver337.',
                            'evidence':'Native revealed left gable/return and retained roof silhouettes; existing physical occluders partition actual receiver faces.'})
    source=next(o for o in objects if o['source_node']=='building-228')
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    def point(x,y,z):return Vector((x,(-y-z*cosine)/sine,z))
    center=point(686.5,946,180);parts=[]
    bpy.ops.mesh.primitive_torus_add(major_segments=48,minor_segments=8,location=center,major_radius=23,minor_radius=1.4)
    parts.append(bpy.context.object)
    def cylinder(a,b,radius):
        axis=b-a;bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=radius,depth=axis.length,location=(a+b)/2)
        obj=bpy.context.object;obj.rotation_euler=axis.to_track_quat('Z','Y').to_euler();parts.append(obj)
    top=center+Vector((0,0,57))
    for angle in (0,2*math.pi/3,4*math.pi/3):
        endpoint=center+Vector((23*math.cos(angle),23*math.sin(angle),0));cylinder(endpoint,top,.65)
    measurements=json.loads((DIRECTORY.parents[1]/'work/leicester-refinement/south-inspection/chandelier-candles-review.json').read_text())
    for candle in measurements['measurements']:
        if candle['confidence']!='high':continue
        x,y=candle['source_visible_wax_base'];a=point(x,y,181.5)
        height=(y-candle['source_top'][1])/cosine;cylinder(a,a+Vector((0,0,height)),.85)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();fixture=parts[0]
    world=fixture.matrix_world.copy();inverse=source.matrix_world.inverted()
    for vertex in fixture.data.vertices:vertex.co=inverse@(world@vertex.co)
    fixture.matrix_world=source.matrix_world.copy();fixture.name='West Wing / corridor chandelier'
    for key in source.keys():fixture[key]=source[key]
    for owner in list(fixture.users_collection):owner.objects.unlink(fixture)
    collection.objects.link(fixture);fixture.hide_render=False;fixture.hide_set(False)
    if not fixture.data.uv_layers:fixture.data.uv_layers.new(name='UVMap')
    fixture.data.materials.clear();fixture.data.materials.append(bpy.data.materials['Leicester source-unknown masonry'])
    selector=tag(fixture,'corridor-chandelier');topology(fixture)
    floor_receiver=next(r for r in review['receiver_components']['interior-'+PATCH] if r['source_node']=='building-228')
    floor_receiver['projection_components'].append('corridor-chandelier')
    # One canonical source node can own floor and fixture, while geometry depth
    # and separate native masks partition the two disjoint pixel silhouettes.
    floor_assignment=next(a for a in assignments if a['source_node']=='building-228')
    floor_assignment['mask_indices']=[327,328,336,337];floor_assignment['exclude_mask_indices']=[]
    floor_assignment['exclusion_reason']='Floor and fixture are separate geometry components of canonical source228; actual depth partitions native337.'
    review['render_visibility']['covered']['hidden_components'].append(selector)
    review['receiver_nodes']=sorted(set(review['receiver_nodes']))
    review['limitations']='Eleven individually measured candle stems modeled; five dim or overlapping candidates remain unmodeled. Fixture depth and three suspension chains are inferred.'
    path.write_text(json.dumps(manifest,indent=2)+'\n');masks_path.write_text(json.dumps(masks,indent=2)+'\n')
    return {'candles':11,'ambiguous_candidates':5,'ring_radius':23,'ring_world_z':180,'chain_count_inferred':3}


def refine(workspace):
    collection=bpy.data.collections['Leicester Working']
    objects=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')=='leicester-west-wing' and not o.hide_render]
    if any(o.get('south_westwing')==TAG for o in objects):
        raise RuntimeError('West corridor candidate already exists; inspect or restore its preserved model explicitly')
    by_node={int(o['source_node'].split('-')[-1]):o for o in objects}
    projection_path=Path(initialize_working_projection(workspace))
    manifest=json.loads(projection_path.read_text())
    patch=next(p for p in manifest['patches'] if p['id']==PATCH)
    contour=boundary(Path(patch['graphic']['alpha']),patch['graphic']['bbox'][:2])
    # Avoid exact pixel-grid corner coincidences with imported wall vertices.
    # The one-hundredth pixel offset is far below the 0.8px contour tolerance.
    contour=[(x+.01,y+.01) for x,y in contour]
    report={'tag':TAG,'floor_world_z':50/math.cos(math.radians(35)),
            'cut_contour_offset_pixels':[.01,.01],
            'floor_source_pixels':FLOOR_PIXELS,'changes':[],
            'limitations':['Floor elevation50 in game units is supported by courtyard and wall-foot anchors, but is not uniquely recovered.',
                           'Native motion polygon defines visible corridor footprint; hidden continuation is not invented.',
                           'Cutaway depth follows the source camera rays. Roof undersides are inferred three-unit shells.']}
    for node,count in ((222,2),(231,2),(232,2),(234,2),(235,3)):
        report['changes'].append({'source_node':f'building-{node:03}','kind':'roof-shell',**cap_prism(by_node[node],thickness=3,face_count=count)})
    report['changes'].append({'source_node':'building-228','kind':'closed-concave-shell',**cap_prism(by_node[228])})
    report['changes'].append({'source_node':'building-230','kind':'closed-interior-wall',**cap_prism(by_node[230])})
    report['limitations'].append('Source230 uses its measured concave upper-wall footprint with inferred vertical foundation closure below the corridor floor.')
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    vertices=[(x,-y/sine-depth*cosine,depth*sine) for depth in (-3000,3000) for x,y in contour]
    n=len(contour);faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    mesh=bpy.data.meshes.new('West corridor camera cutter');mesh.from_pydata(vertices,[],faces)
    cutter=bpy.data.objects.new('West corridor camera cutter',mesh);collection.objects.link(cutter);cutter.hide_render=True
    close(cutter)
    exterior=[];interior=[];covers=[]
    for node in (228,234,230):
        source=by_node[node]
        roles=('retained-shell','interior-wall' if node==230 else 'removable-cover')
        for operation,role in zip(('DIFFERENCE','INTERSECT'),roles):
            obj=source.copy();obj.data=source.data.copy();obj.name=source.name+' / '+role;collection.objects.link(obj)
            modifier=obj.modifiers.new('Native corridor opening','BOOLEAN');modifier.operation=operation;modifier.solver='EXACT';modifier.object=cutter
            bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=modifier.name)
            if not obj.data.polygons:raise RuntimeError(f'Empty {node}/{role} cutaway')
            bm=bmesh.new();bm.from_mesh(obj.data)
            loose=[e for e in bm.edges if not e.link_faces]
            if loose:
                bmesh.ops.delete(bm,geom=loose,context='EDGES')
                unused=[v for v in bm.verts if not v.link_edges]
                if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
                bm.to_mesh(obj.data)
            if any(f.calc_area()<1e-8 for f in bm.faces):
                bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-3)
                bm.to_mesh(obj.data)
            if any(len(e.link_faces)>2 for e in bm.edges):
                # Native stepped wall cells may touch along one zero-volume
                # edge after clipping. Preserve each closed face fan separately.
                remaining=set(bm.faces);components=[]
                while remaining:
                    todo=[remaining.pop()];group=[]
                    while todo:
                        face=todo.pop();group.append(face)
                        for edge in face.edges:
                            if len(edge.link_faces)!=2:continue
                            for neighbor in edge.link_faces:
                                if neighbor in remaining:remaining.remove(neighbor);todo.append(neighbor)
                    components.append(group)
                rebuilt=bmesh.new()
                for group in components:
                    mapping={v:rebuilt.verts.new(v.co) for v in {v for face in group for v in face.verts}}
                    for face in group:rebuilt.faces.new([mapping[v] for v in face.verts])
                rebuilt.to_mesh(obj.data);rebuilt.free()
            bm.free()
            check=bmesh.new();check.from_mesh(obj.data)
            for edge in check.edges:
                if not edge.is_manifold:
                    print('WEST BOOLEAN EDGE',node,role,len(edge.link_faces),[list(v.co) for v in edge.verts],flush=True)
            check.free()
            result=topology(obj);selector=tag(obj,role)
            (interior if role=='interior-wall' else exterior).append(selector)
            if role=='removable-cover':covers.append(selector)
            report['changes'].append({'source_node':source['source_node'],'component':role,**result})
        source.hide_render=True;source.hide_set(True)
    source=by_node[228]
    floor=source.copy();floor.data=source.data.copy();floor.name=source.name+' / corridor-floor';collection.objects.link(floor)
    floor.hide_render=False;floor.hide_set(False)
    z=report['floor_world_z'];n=len(FLOOR_PIXELS);inverse=floor.matrix_world.inverted()
    points=[inverse@Vector((x,(-y-height*cosine)/sine,height)) for height in (z-3,z) for x,y in FLOOR_PIXELS]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    neutral_mesh(floor,points,faces,'West corridor floor')
    close(floor);floor_selector=tag(floor,'corridor-floor');interior.append(floor_selector)
    report['changes'].append({'source_node':'building-228','component':'corridor-floor',**topology(floor)})
    bpy.data.objects.remove(cutter,do_unlink=True)
    review=manifest['projection_reviews'][PATCH]
    def receivers(selectors):
        return [{'source_node':node,'projection_components':[s['projection_component'] for s in selectors if s['source_node']==node],'patch_id':PATCH}
                for node in sorted({s['source_node'] for s in selectors})]
    evidence='Native patch000 alpha; south-inspection/west-floor-review.json motion polygon and wall-foot anchors; dedicated low corridor floor and source230 interior wall.'
    review.update(role='interior',reviewed=True,reviewer='refine_south',evidence=evidence,
                  receiver_nodes=sorted({s['source_node'] for s in interior}),
                  receiver_components={'exterior':receivers(exterior),'interior-'+PATCH:receivers(interior)},
                  partial_cover_nodes=sorted({s['source_node'] for s in covers}),exclude_occluder_components=covers,
                  covered_hidden_nodes=[],geometry_ready=False,
                  render_visibility={'version':1,'reviewed':True,'reviewer':'refine_south','evidence':evidence,
                    'covered':{'hidden_nodes':[],'hidden_components':[floor_selector]},
                    'revealed':{'hidden_nodes':[],'hidden_components':covers}},
                  limitations='Candidate requires eight-view paired-state review; chandelier receiver still pending.')
    projection_path.write_text(json.dumps(manifest,indent=2)+'\n')
    masks_path=Path(workspace)/'source-masks.json';masks=json.loads(masks_path.read_text())
    masks['projections']['interior-patch-000']['assignments']=[
        {'source_node':'building-228','mask_indices':[327,328,336], 'exclude_mask_indices':[337],
         'reviewed':True,'exclusions_reviewed':True,'exclusion_reason':'Independent chandelier337 must not project onto floor.',
         'evidence':'Actual dedicated corridor-floor receiver, native motion footprint and source camera occluders partition the logical west-wing silhouette.'},
        {'source_node':'building-230','mask_indices':[334,339,341], 'exclude_mask_indices':[337],
         'reviewed':True,'exclusions_reviewed':True,'exclusion_reason':'Independent chandelier337 remains separate.',
         'evidence':'Native right wall334/339 and inner back-wall341, clipped to source230 interior component.'}]
    masks_path.write_text(json.dumps(masks,indent=2)+'\n')
    report['cover_selectors']=covers;report['interior_selectors']=interior
    return report


def extend_walkway(workspace):
    collection=bpy.data.collections['Leicester Working']
    if any(o.get('projection_component')=='corridor-walkway' for o in collection.all_objects):
        raise RuntimeError('Walkway extension already exists')
    source=next(o for o in collection.all_objects if o.get('projection_component')=='corridor-floor')
    # Native navigable contour continues beyond the back chamber, sharing its
    # exact front edge. Retained roof and wall geometry determines visibility.
    pixels=[(593,1004),(672,1015),(794,1054),(796,1067),(806,1068),
            (814,1061),(832,1066),(819,1079),(834,1082),(810,1098),
            (601,1032),(537,1033),(522,1009),(572,1000),(577,1007)]
    obj=source.copy();obj.data=source.data.copy();obj.name='West Wing / foreground corridor walkway';collection.objects.link(obj)
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35));z=50/cosine;n=len(pixels);inverse=obj.matrix_world.inverted()
    points=[inverse@Vector((x,(-y-h*cosine)/sine,h)) for h in (z-3,z) for x,y in pixels]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    neutral_mesh(obj,points,faces,'Foreground corridor walkway');close(obj);selector=tag(obj,'corridor-walkway')
    path=Path(initialize_working_projection(workspace));manifest=json.loads(path.read_text());review=manifest['projection_reviews'][PATCH]
    receiver=next(r for r in review['receiver_components']['interior-'+PATCH] if r['source_node']=='building-228')
    receiver['projection_components'].append('corridor-walkway');review['render_visibility']['covered']['hidden_components'].append(selector)
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'source_pixels':pixels,'world_z':z,'native_datum_game':50,'depth_hypothesis':True,**topology(obj)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace',type=Path);parser.add_argument('--receivers',action='store_true')
    parser.add_argument('--walkway',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);workspace=args.workspace.resolve()
    if not json.loads((workspace/'inspection/input-review.json').read_text())['all_eight_views_inspected']:
        raise RuntimeError('Inspect frozen input before modifying')
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    if args.walkway:
        report=json.loads((workspace/'geometry-report.json').read_text());report['foreground_walkway']=extend_walkway(workspace)
    elif args.receivers:
        report=json.loads((workspace/'geometry-report.json').read_text());report['chandelier']=receivers_and_chandelier(workspace)
    else:report=refine(workspace)
    (workspace/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    modified(workspace)
    from asset_reference_views import render_states
    target=workspace/'inspection/states'
    if target.exists():
        history=workspace/'inspection/state-history';history.mkdir(exist_ok=True);target.rename(history/uuid.uuid4().hex[:12])
    render_states(workspace,target)


if __name__=='__main__':main()
