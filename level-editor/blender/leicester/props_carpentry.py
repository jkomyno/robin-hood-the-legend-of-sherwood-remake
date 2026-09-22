"""Fence panel and open handcart candidates with explicit concealed geometry.

The cart tray and two shafts follow its retained receiver anchors. The near
wheel is positioned from visible artwork; concealed wheel width, spokes, and
back-facing surfaces are hypotheses requiring the fixed-camera review.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from props import footprint, signature
VERSION = 'leicester-carpentry-v1'


def build(obj, kind):
    matrix = obj.matrix_world.copy()
    before = signature(obj)
    vertices, faces = [], []

    def box(a, b, width, depth):
        a,b=Vector(a),Vector(b);direction=(b-a).normalized()
        ref=Vector((0,0,1)) if abs(direction.z)<.9 else Vector((1,0,0))
        side=direction.cross(ref).normalized()*width/2
        up=direction.cross(side).normalized()*depth/2
        start=len(vertices)
        vertices.extend(p+s*side+t*up for p in (a,b) for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)])
        faces.extend(tuple(start+i for i in face) for face in
                     [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])

    def wheel(center, axis, radial, radius):
        center,axis,radial=Vector(center),Vector(axis),Vector(radial)
        vertical=Vector((0,0,1));n=20;start=len(vertices)
        for offset,r in [(-1.6,radius),(1.6,radius),(-1.6,radius-2),(1.6,radius-2)]:
            for i in range(n):
                angle=2*math.pi*i/n
                vertices.append(center+axis*offset+r*(radial*math.cos(angle)+vertical*math.sin(angle)))
        for i in range(n):
            j=(i+1)%n
            for f in [(i,j,n+j,n+i),(2*n+j,2*n+i,3*n+i,3*n+j),
                      (j,i,2*n+i,2*n+j),(n+i,n+j,3*n+j,3*n+i)]:faces.append(tuple(start+k for k in f))
        # The obscured spoke count is not asserted as source parity.
        for i in range(8):
            angle=2*math.pi*i/8
            end=center+(radius-2)*(radial*math.cos(angle)+vertical*math.sin(angle))
            box(center,end,1.6,1.6)
        box(center-axis*3,center+axis*3,4,4)

    if kind == 'panel':
        if obj.get('leicester_prop_anchor'):
            anchor=json.loads(obj['leicester_prop_anchor'])
        elif obj.get('leicester_carpentry_anchor'):
            anchor=json.loads(obj['leicester_carpentry_anchor'])
        else:anchor=footprint(obj)
        obj['leicester_carpentry_anchor']=json.dumps(anchor,sort_keys=True)
        c,s=math.cos(anchor['angle']),math.sin(anchor['angle']);cx,cy=anchor['center']
        rx,ry=anchor['radii'];long_x=rx>=ry
        length,thickness=(2*rx,2*ry) if long_x else (2*ry,2*rx)
        direction=Vector((c,s,0)) if long_x else Vector((-s,c,0))
        center=Vector((cx*c-cy*s,cx*s+cy*c,0));bottom=anchor['bottom'];height=anchor['top']-bottom
        for offset in [-length/2+2,length/2-2]:
            p=center+direction*offset
            box(p+Vector((0,0,bottom)),p+Vector((0,0,bottom+height)),thickness,4)
        gap=length-8;board_width=gap/4*.84
        for i in range(4):
            p=center+direction*(-gap/2+(i+.5)*gap/4)
            # Panel boards use a shallow section matching the native thickness.
            a=p+Vector((0,0,bottom));b=p+Vector((0,0,bottom+height*.92))
            start=len(vertices);side=direction*board_width/2;across=Vector((-direction.y,direction.x,0))*thickness*.35
            vertices.extend(q+u*side+v*across for q in (a,b) for u,v in [(-1,-1),(1,-1),(1,1),(-1,1)])
            faces.extend(tuple(start+k for k in face) for face in [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        for fraction in [.2,.7]:
            z=bottom+height*fraction
            box(center-direction*length/2+Vector((0,0,z)),center+direction*length/2+Vector((0,0,z)),thickness*.4,3)
        detail={'visible_end_posts':2,'interior_boards_inferred':4,'anchor':anchor}
    elif kind == 'cart':
        rear=Vector((2797.10,-864.22,0));tip=Vector((2878.45,-824.47,0))
        direction=(tip-rear).normalized();across=Vector((-direction.y,direction.x,0))
        front=rear+(tip-rear)*.65;half_width=19.45
        # Main body receiver becomes floor, three walls, shafts and wheels.
        # The fourth (far) side remains the independent native receiver 075.
        floor_back,floor_front=28.08,20.15;rim_back,rim_front=59.70,51.35
        floor_center=(rear+front)/2
        box(rear+Vector((0,0,floor_back)),front+Vector((0,0,floor_front)),half_width*2,2.4)
        near_back=rear-across*half_width;near_front=front-across*half_width
        box(near_back+Vector((0,0,(floor_back+rim_back)/2)),near_front+Vector((0,0,(floor_front+rim_front)/2)),2.4,31.5)
        for p,floor_z,rim_z in [(rear,floor_back,rim_back),(front,floor_front,rim_front)]:
            box(p-across*half_width+Vector((0,0,(floor_z+rim_z)/2)),p+across*half_width+Vector((0,0,(floor_z+rim_z)/2)),2.4,rim_z-floor_z)
        for sign in [-1,1]:
            box(front+across*(half_width-3)*sign+Vector((0,0,floor_front)),tip+across*(half_width-3)*sign+Vector((0,0,17.8)),3,3)
        axle=rear+(tip-rear)*.36+Vector((0,0,15.5))
        box(axle-across*24,axle+across*24,3,3)
        for sign in [-1,1]:wheel(axle+across*22*sign,across,direction,15.5)
        detail={'tray_rear':list(rear),'shaft_tip_center':list(tip),'tray_fraction':.65,
                'near_wheel_source_estimate':[2836,486],'inferred_wheel_radius':15.5,
                'visible_shafts':2,'inferred_spokes_per_wheel':8,'retained_far_wall':'building-075'}
    else:raise ValueError(kind)
    mesh=bpy.data.meshes.new(obj.name+' carpentry');inv=matrix.inverted()
    mesh.from_pydata([inv@v for v in vertices],[],faces);mesh.update()
    mesh.uv_layers.new(name='UVMap')
    for mat in obj.data.materials:mesh.materials.append(mat)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    topology={'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),
              'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(topology[k] for k in ['boundary_edges','nonmanifold_edges','degenerate_faces']):raise ValueError(str(topology))
    bm.to_mesh(mesh);bm.free();old=obj.data;obj.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    obj['leicester_geometry_recipe']=VERSION
    if obj.matrix_world!=matrix:raise ValueError('Transform drift')
    return {'source_node':obj['source_node'],'before_geometry_sha256':before,'after_geometry_sha256':signature(obj),
            'world_transform_drift':0,'topology':topology,'measurements':detail}


def run(workspace):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open isolated worker model')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import validate
    validate(workspace)
    targets=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    nodes={o.get('source_node') for o in targets}
    if nodes=={'building-054'}:kind='panel';obj=targets[0]
    elif nodes=={'building-074','building-075'}:kind='cart';obj=next(o for o in targets if o['source_node']=='building-074')
    else:raise ValueError('Recipe supports only fence panel054 or cart074/075')
    report_object=build(obj,kind);first=signature(obj);build(obj,kind)
    if signature(obj)!=first:raise ValueError('Recipe is not idempotent')
    limitations=['Hidden timber thickness and rear-facing surfaces are inferred; rebuild protected projection before review.']
    if kind=='panel':limitations+=['Two end posts are visible. Four internal boards are an uncertain interpretation of soft source pixels; exact plank count is not approved.']
    else:limitations+=['The near wheel is partly hidden by the house; wheel center has approximately 6 source-pixel uncertainty.','Far wheel, eight-spoke pattern, wheel thickness and unseen tray floor are inferred rather than recovered from artwork.','Tray floor and shaft junction are approximations within the native receivers; handrail irregularities remain unmodeled.','Timber members intentionally contact/intersect at structural joints; receivers remain independently addressable.']
    report={'recipe':VERSION,'asset_id':config['asset_id'],'objects':[report_object],'idempotence':'PASS','limitations':limitations,
            'projection_status':'STALE; rebuild modified packet','approval_status':'refinement in progress','texture_generation':'not-started'}
    validate(workspace);(workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection'/'carpentry-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
