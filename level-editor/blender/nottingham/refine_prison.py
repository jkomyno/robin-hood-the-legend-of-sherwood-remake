"""Refine the southwest prison from measured architectural and state evidence.

Run in the isolated asset workspace; the frozen scene is never edited. The
recipe retains canonical source identities on named projection components.
Source-only projection must be regenerated after running this recipe.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ASSET = 'nottingham-southwest-prison'
TAG = 'nottingham-prison-v1'
ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / 'level-editor/work/nottingham-refinement/prison-audit/obstacles.json'
SINE = math.sin(math.radians(35))
COSINE = math.cos(math.radians(35))
# Visible cap centers measured in the source crop (origin 160,1530).
CAPS = [(233,121),(193,138),(157,155),(124,173),(103,204),(93,238),
        (104,272),(131,300),(162,325),(192,346),(224,359),(261,370),
        (299,378),(337,380),(376,362),(410,349),(443,337),(479,321),
        (500,299),(458,285),(429,258),(400,231),(373,207),(398,192),
        (405,166),(380,145)]


def world(p):
    return Vector((p['x'], -p['y']/SINE, p['z']/COSINE))


def snapshot(obj):
    data = {'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'matrix': [list(r) for r in obj.matrix_world]}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def volume(points, bottom=None, top=None):
    """Native footprint with a closed bottom and piecewise planar top."""
    n = len(points)
    verts = [world(dict(p, z=(p['z_bottom'] if bottom is None else bottom))) for p in points]
    verts += [world(dict(p, z=(p['z_top'] if top is None else top))) for p in points]
    faces = [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    for off in (0,n):
        vs = verts[off:off+n]
        for tri in tessellate_polygon([vs]):
            faces.append(tuple((v if isinstance(v,int) else
                                min(range(n), key=lambda i:(vs[i]-v).length_squared))+off for v in tri))
    return verts, faces


def roof_triangle(points, footprint, apex):
    """Share measured eave and apex anchors across separate roof owners."""
    result=[]
    highest=max(range(len(points)),key=lambda i:points[i]['z_top'])
    for index,point in enumerate(points):
        if index==highest:
            result.append(dict(apex))
        else:
            anchor=min(footprint,key=lambda p:(p['x']-point['x'])**2+(p['y']-point['y'])**2)
            result.append(dict(anchor,z_bottom=anchor['z_top']-3))
    return result


def stair_volume(points, steps=6):
    """Extrude a continuous six-riser side profile across the authored stair."""
    profile=[(0,0),(0,35/steps)]
    for step in range(1,steps+1):
        profile.append((step/steps,35*step/steps))
        if step<steps:profile.append((step/steps,35*(step+1)/steps))
    profile.append((1,0))
    verts=[]
    for start,end in [(points[3],points[0]),(points[2],points[1])]:
        for t,z in profile:
            verts.append(world({'x':start['x']+(end['x']-start['x'])*t,
                                'y':start['y']+(end['y']-start['y'])*t,'z':z}))
    n=len(profile)
    faces=[tuple(range(n)),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    return verts,faces


def mesh_for(obj, geometries, label):
    verts, faces = [], []
    for vs, fs in geometries:
        offset = len(verts)
        verts.extend(obj.matrix_world.inverted() @ p for p in vs)
        faces.extend(tuple(i+offset for i in f) for f in fs)
    mesh = bpy.data.meshes.new(obj.name + ' ' + label)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    defects = {'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
               'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(defects.values()):
        bm.free()
        raise ValueError(f'{obj.name}: invalid closed component {defects}')
    bm.to_mesh(mesh)
    bm.free()
    material = bpy.data.materials.get('Nottingham prison pending source projection')
    if material is None:
        material = bpy.data.materials.new('Nottingham prison pending source projection')
        material.diffuse_color = (.45,.45,.45,1)
    mesh.materials.append(material)
    mesh.uv_layers.new(name='UVMap')
    obj.data = mesh
    obj['prison_refinement'] = TAG
    return defects


def component(primary, name, geometries):
    # Recipe-created components are replaced instead of accumulated on reruns.
    objname = primary['source_node'] + '__' + name
    obj = bpy.data.objects.get(objname)
    if obj is None:
        obj = bpy.data.objects.new(objname, bpy.data.meshes.new(objname + ' staging'))
        for collection in primary.users_collection:
            collection.objects.link(obj)
        obj.parent = primary.parent
        obj.matrix_parent_inverse = primary.matrix_parent_inverse.copy()
        obj.matrix_world = primary.matrix_world.copy()
        for key in primary.keys():
            obj[key] = primary[key]
    obj['projection_component'] = name
    obj['canonical_source_node'] = primary['source_node']
    obj['prison_generated_component'] = True
    obj['reveal_component_role'] = 'removable-cover' if name == 'prison-removable-cover' else 'retained'
    obj['reveal_component_patch_id'] = ('patch-007' if primary.get('asset_group') == ASSET
                                        else 'patch-002')
    mesh_for(obj, geometries, name)
    return obj


def carve_notch(obj, a, b, top, depth=16, width=40):
    """Subtract a physical embrasure, leaving closed receiver geometry."""
    pa, pb = Vector(a), Vector(b)
    tangent = (pb-pa).normalized()
    normal = Vector((-tangent.y, tangent.x)) * width
    quad = [pa+normal, pb+normal, pb-normal, pa-normal]
    points = [{'x':p.x,'y':p.y,'z_bottom':top-depth,'z_top':top+20} for p in quad]
    cutter = bpy.data.objects.new('Prison temporary notch', bpy.data.meshes.new('Prison notch staging'))
    bpy.context.scene.collection.objects.link(cutter)
    mesh_for(cutter, [volume(points)], 'cutter')
    modifier = obj.modifiers.new('Measured parapet embrasure', 'BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.solver = 'EXACT'
    modifier.object = cutter
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.select_set(False)
    mesh = cutter.data
    bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.data.meshes.remove(mesh)


def station(path, point):
    distances = [0.0]
    for a,b in zip(path,path[1:]):
        distances.append(distances[-1]+(b-a).length)
    best = None
    for i,(a,b) in enumerate(zip(path,path[1:])):
        t = min(1,max(0,(point-a).dot(b-a)/(b-a).length_squared))
        projected = a+(b-a)*t
        candidate=((point-projected).length_squared, distances[i]+(b-a).length*t)
        if best is None or candidate[0]<best[0]:best=candidate
    return best[1], distances


def sample(path, distances, s):
    for i in range(len(path)-1):
        if s <= distances[i+1]:
            return path[i].lerp(path[i+1], (s-distances[i])/(distances[i+1]-distances[i]))
    return path[-1].copy()


def battlements(obj, points, indices, cap_indices):
    # Convert measured screen crown centers to the native top plane before
    # measuring stations. Depth remains constrained by the authored footprint.
    path = [Vector((points[i]['x'], points[i]['y'])) for i in indices]
    top = sum(points[i]['z_top'] for i in indices)/len(indices)
    locations=[]
    for i in cap_indices:
        x,y=CAPS[i-1]
        s, distances=station(path,Vector((x+160,y+1530+top)))
        locations.append(s)
    locations=sorted(locations)
    for s0,s1 in zip(locations, locations[1:]):
        # Crown width follows the measured local repeat spacing; the source
        # mortar and beveled cap textures remain source pixels after projection.
        gap0=s0+(s1-s0)*.32
        gap1=s1-(s1-s0)*.32
        carve_notch(obj,sample(path,distances,gap0),sample(path,distances,gap1),top)
    return {'visible_caps':len(locations),'embrasures':max(0,len(locations)-1),
            'measured_cap_ids':cap_indices,'native_stations':locations,
            'inference':'Embrasure depth16; crown width64% of neighboring measured repeat.'}


def refine(workspace=None):
    if bpy.context.scene.get('frozen_baseline'):
        raise ValueError('Refuse to edit a frozen baseline')
    working=bpy.data.collections['nottingham Working']
    all_meshes=[o for o in working.all_objects if o.type=='MESH']
    selected=[o for o in all_meshes if o.get('asset_group')==ASSET and not o.get('prison_generated_component')]
    by_node={o.get('source_node'):o for o in selected}
    expected={f'building-{i:03}' for i in range(456,478)}
    if set(by_node)!=expected or len(selected)!=len(expected):
        raise ValueError(f'Expected exactly prison nodes456..477; found {sorted(by_node)}')
    outside={o.name:snapshot(o) for o in all_meshes if o.get('asset_group')!=ASSET}
    transforms={o.name:[list(r) for r in o.matrix_world] for o in selected}
    native={o['id']:o['points'] for o in json.loads(NATIVE.read_text())}
    def main(i,geometries,part='prison-retained'):
        obj=by_node[f'building-{i:03}']
        obj['projection_component']=part
        obj['reveal_component_patch_id']='patch-007'
        mesh_for(obj,geometries,part)
        return obj
    # Correct five visible roof wedges: the imported vertical prisms are
    # replaced by three-unit thick roof planes, preserving the measured eaves.
    apex={'x':475.37,'y':1997.84,'z_bottom':457.65,'z_top':460.65}
    for i in range(461,466):
        main(i,[volume(roof_triangle(native[i],native[459],apex))],'prison-roof')
    # A roof pavilion stands on the terrace, not on the ground-floor cell.
    main(459,[volume(native[459],bottom=335.001)],'prison-pavilion')
    # The rear support continues below the pavilion. Replacing its old solid
    # prism with a thin rear arc keeps the cell open without floating masonry.
    outline=[native[457][5]]+[native[459][i] for i in [3,4,5,6,0]]+[native[458][4]]
    center=Vector((480,2000))
    inner=[]
    for point in reversed(outline):
        xy=Vector((point['x'],point['y']))
        inset=xy+(center-xy).normalized()*12
        inner.append(dict(point,x=inset.x,y=inset.y))
    component(by_node['building-459'],'prison-inferred-rear-support',
              [volume(outline+inner,bottom=0,top=335.001)])
    # Seven-sided pavilion has two unseen roof facets. Their depth is inferred
    # from the existing eaves and apex, and they are neutral in known views.
    back=[native[459][4],native[459][5],native[459][6]]
    for j in range(2):
        pts=[dict(back[j],z_bottom=back[j]['z_top']-3),
             dict(back[j+1],z_bottom=back[j+1]['z_top']-3),apex]
        component(by_node['building-461'],f'prison-inferred-roof-back-{j+1}',[volume(pts)])
    # Removable shell is below the shared rooftop, preserving its parapet in
    # both states. Low retained sections reproduce the visible cutaway walls.
    main(456,[volume(native[456],top=45),volume(native[456],bottom=320.626)])
    component(by_node['building-456'],'prison-removable-cover',[volume(native[456],bottom=45,top=320.626)])
    p=native[457]
    front=[p[i] for i in [0,1,2,9,10,11]]
    rear=[p[i] for i in [2,3,4,5,6,7,8,9]]
    main(457,[volume(front,top=40),volume(front,bottom=320.626)])
    component(by_node['building-457'],'prison-retained-rear-wall',[volume(rear)])
    component(by_node['building-457'],'prison-removable-cover',[volume(front,bottom=40,top=320.626)])
    # The thin front railing belongs to the reveal cutaway, while the right
    # buttress remains full height. Keeping the middle band masks the cell door.
    p = native[466]
    front = [p[i] for i in [3,4,5,6]]
    rear = [p[i] for i in [0,1,2,3,6,7]]
    main(466,[volume(front,top=25),volume(front,bottom=320.626)])
    component(by_node['building-466'],'prison-retained-right-buttress',[volume(rear)])
    component(by_node['building-466'],'prison-removable-cover',
              [volume(front,bottom=25,top=320.626)])
    main(470,[volume(native[470],bottom=320.626)])
    component(by_node['building-470'],'prison-removable-cover',[volume(native[470],top=320.626)])
    # Interior masking volumes do not describe the rendered low cell wall.
    partition_heights=[55,35,30,25,25,40,65,65,40,25,25,30,35,55]
    main(472,[volume([dict(p,z_top=h) for p,h in zip(native[472],partition_heights)])],
         'prison-interior-wall')
    main(473,[volume(native[473],top=95)],'prison-interior-post')
    main(474,[volume(native[474],top=95)],'prison-interior-lintel')
    floor=[native[472][i] for i in [7,8,9,10,11,12,13]]
    component(by_node['building-472'],'prison-interior-floor',[volume(floor,bottom=-2,top=0)])
    main(468,[stair_volume(native[468])],'prison-interior-stair')
    # Rebuild the remaining parapet before subtraction so reruns are identical.
    main(458,[volume(native[458])])
    main(467,[volume(native[467])])
    caps={}
    caps['building-456']=battlements(by_node['building-456'],native[456],[3,2,1,0],[11,12,13,14])
    caps['building-457-front']=battlements(by_node['building-457'],native[457],[0,1,2],[6,7,8,9])
    caps['building-457-rear']=battlements(bpy.data.objects['building-457__prison-retained-rear-wall'],native[457],[2,3,4,5],[1,2,3,4,5,6])
    caps['building-458']=battlements(by_node['building-458'],native[458],[0,1,2,3],[20,21,22,23,24,25,26])
    caps['building-467']=battlements(by_node['building-467'],native[467],[2,1,0],[15,16,17,18])
    # Finish repeats across canonical source boundaries. Without these cuts,
    # adjacent end caps incorrectly join into one long crown in solid views.
    seams=[]
    for first,last,nodes,top in [(9,10,[457,470],375),
                                 (10,11,[470,456],372),
                                 (14,15,[456,467],369),
                                 (18,19,[467],365),
                                 (19,20,[467,458],370)]:
        a=Vector((CAPS[first-1][0]+160,CAPS[first-1][1]+1530+top))
        b=Vector((CAPS[last-1][0]+160,CAPS[last-1][1]+1530+top))
        for node in nodes:
            carve_notch(by_node[f'building-{node}'],a.lerp(b,.32),a.lerp(b,.68),top)
        seams.append({'cap_ids':[first,last],'source_nodes':nodes})
    report=[]
    for obj in working.all_objects:
        if obj.type!='MESH' or obj.get('asset_group')!=ASSET:continue
        bm=bmesh.new();bm.from_mesh(obj.data)
        changed=obj.get('prison_refinement')==TAG
        defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
                 'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
        bm.free()
        if changed and any(defects.values()):raise ValueError(f'{obj.name}: {defects}')
        report.append({'object':obj.name,'source_node':obj['source_node'],
                       'projection_component':obj.get('projection_component'),
                       'changed':changed,'vertices':len(obj.data.vertices),
                       'faces':len(obj.data.polygons),'geometry_sha256':snapshot(obj),**defects})
    drift=[o.name for o in selected if transforms[o.name]!=[list(r) for r in o.matrix_world]]
    outside_changed=[o.name for o in working.all_objects if o.name in outside and snapshot(o)!=outside[o.name]]
    if drift or outside_changed:raise ValueError('Transform or outside-object drift')
    result={'version':1,'asset_id':ASSET,'recipe':TAG,'status':'geometry-candidate',
            'parts':report,'source_nodes':sorted(expected),'cap_measurements':caps,
            'cross_node_embrasures':seams,
            'visible_cap_count':26,'cap_count_evidence':'prison-audit/cap-count.png',
            'interior_stair_risers':6,
            'transform_drift':drift,'outside_objects_changed':outside_changed,
            'approval_state':'pending','texture_generation':'not-started',
            'limitations':['Roof thickness3 and two rear roof facets are inferred.',
             'Cutaway lower shell heights45/40 and partition heights25..65 are measured visual hypotheses.',
             'Doorway lintel95 is conservative; fine arch curvature remains approximate.',
             'Curved stone wall is piecewise planar between native footprint anchors.',
             'Fine arch relief and the thin roof finial are not fully modeled.',
             'The rear support wall has inferred12-unit thickness and remains neutral.',
             'Shared component joins have coincident internal faces by design; each receiver is closed.',
             'Unchanged imported meshes can retain pre-existing topology defects.',
             'Covered/revealed projection and door476/477 state exclusion require the reviewed layer manifest.']}
    if workspace:
        path=Path(workspace)
        (path/'geometry-refinement.json').write_text(json.dumps(result,indent=2)+'\n')
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(path/'model.blend'))
    return result


def refine_upper(workspace):
    """Upper prison preserves the elevated cell floor and removable facade."""
    asset = 'nottingham-upper-prison'
    if bpy.context.scene.get('frozen_baseline'):
        raise ValueError('Refuse to edit a frozen baseline')
    working = bpy.data.collections['nottingham Working']
    selected = [o for o in working.all_objects if o.type == 'MESH'
                and o.get('asset_group') == asset and not o.get('prison_generated_component')]
    by_node = {o.get('source_node'): o for o in selected}
    expected = {f'building-{i:03}' for i in range(435,456)}
    if set(by_node) != expected or len(selected) != len(expected):
        raise ValueError(f'Expected upper prison nodes435..455, found {sorted(by_node)}')
    outside = {o.name:snapshot(o) for o in working.all_objects
               if o.type == 'MESH' and o.get('asset_group') != asset}
    transforms = {o.name:[list(r) for r in o.matrix_world] for o in selected}
    source = NATIVE.with_name('upper-obstacles.json')
    native = {o['id']:o['points'] for o in json.loads(source.read_text())}
    def main(i, geometries, part='prison-retained'):
        obj = by_node[f'building-{i:03}']
        obj['projection_component'] = part
        obj['reveal_component_patch_id'] = 'patch-002'
        mesh_for(obj, geometries, part)
        return obj
    apex = {'x':980.27,'y':979.05,'z_bottom':586.1,'z_top':589.1}
    for i in range(445,451):
        main(i,[volume(roof_triangle(native[i],native[444],apex))], 'prison-roof')
    back = [native[444][6],native[444][7],native[444][0]]
    for j in range(2):
        points = [dict(back[j],z_bottom=back[j]['z_top']-3),
                  dict(back[j+1],z_bottom=back[j+1]['z_top']-3),apex]
        component(by_node['building-445'],f'prison-inferred-roof-back-{j+1}',[volume(points)])
    for i in (441,442):
        main(i,[volume(native[i],top=270),volume(native[i],bottom=361.687)])
        component(by_node[f'building-{i}'],'prison-removable-cover',
                  [volume(native[i],bottom=270,top=361.687)])
    main(443,[volume(native[443],bottom=361.687)])
    component(by_node['building-443'],'prison-removable-cover',
              [volume(native[443],top=361.687)])
    main(454,[volume(native[454],top=250)])
    component(by_node['building-454'],'prison-removable-cover',
              [volume(native[454],bottom=250)])
    partition_heights=[250,310,308,301,300,255]
    main(438,[volume([dict(p,z_top=h) for p,h in zip(native[438],partition_heights)])],
         'prison-interior-partition')
    for i in (453,455):
        main(i,[volume(native[i],bottom=250)],'prison-door')
    report = []
    for obj in working.all_objects:
        if obj.type != 'MESH' or obj.get('asset_group') != asset:continue
        bm=bmesh.new();bm.from_mesh(obj.data)
        defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
                 'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
        bm.free()
        changed = obj.get('prison_refinement') == TAG
        if changed and any(defects.values()):raise ValueError(f'{obj.name}: {defects}')
        report.append({'object':obj.name,'source_node':obj['source_node'],
                       'projection_component':obj.get('projection_component'),
                       'changed':changed,'vertices':len(obj.data.vertices),
                       'faces':len(obj.data.polygons),'geometry_sha256':snapshot(obj),**defects})
    drift = [o.name for o in selected if transforms[o.name] != [list(r) for r in o.matrix_world]]
    outside_changed = [o.name for o in working.all_objects
                       if o.name in outside and snapshot(o) != outside[o.name]]
    if drift or outside_changed:raise ValueError('Transform or outside-object drift')
    result = {'version':1,'asset_id':asset,'recipe':TAG,'status':'geometry-candidate',
              'parts':report,'source_nodes':sorted(expected),
              'transform_drift':drift,'outside_objects_changed':outside_changed,
              'approval_state':'pending','texture_generation':'not-started',
              'limitations':['Roof thickness3 and two unseen roof facets inferred.',
               'Retained front masonry rim rises20 above the native cell floor250.',
               'Partition crown slopes250..310 above floor250; source control estimates have about5 units uncertainty.',
               'Fine arch relief and the thin roof finial are not fully modeled.',
               'Shared component joins retain coincident internal faces for state separation.',
               'Door453/455 state exclusion requires the reviewed state manifest.',
               'Unchanged imported meshes can retain pre-existing topology defects.']}
    path = Path(workspace)
    (path/'geometry-refinement.json').write_text(json.dumps(result,indent=2)+'\n')
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path/'model.blend'))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--upper',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    print(json.dumps(refine_upper(args.workspace) if args.upper else refine(args.workspace)))
