"""Source-measured bucket rim and stone cross with stepped square plinth.

Visible outlines are measured in map pixels. Concealed thickness, circular
vessel section and the rear of the stonework remain explicit hypotheses.
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

VERSION = 'leicester-special-props-v1'
SUPPORTED = {49, 104}
SINE = math.sin(math.radians(35))
COSINE = math.cos(math.radians(35))


def signature(obj):
    return hashlib.sha256(json.dumps({'v': [list(v.co) for v in obj.data.vertices],
        'f': [list(f.vertices) for f in obj.data.polygons]}, sort_keys=True).encode()).hexdigest()


def geometry(node):
    vertices, faces = [], []
    def rings(rows):
        start = len(vertices); count = len(rows[0])
        vertices.extend(v for row in rows for v in row)
        faces.append(tuple(start+i for i in reversed(range(count))))
        for row in range(len(rows)-1):
            a=start+row*count; b=a+count
            for i in range(count):
                j=(i+1)%count; faces.append((a+i,a+j,b+j,b+i))
        faces.append(tuple(start+(len(rows)-1)*count+i for i in range(count)))
    def silhouette(points, ground, depth):
        # Front coordinates reproduce measured artwork anchors exactly. Back
        # thickness follows the camera ray so its projection cannot widen them.
        front=[(x,-ground/SINE,(ground-y)/COSINE) for x,y in points]
        ray=Vector((0,-COSINE,SINE))*depth
        rings([front,[tuple(Vector(v)+ray) for v in front]])
    if node == 49:
        center_x, ground, rx, ry = 2963.5, 1174., 7.6, 6.0
        rim_height = 18.5/COSINE
        profiles=[(0,.79),(rim_height-1.2,1),(rim_height,1),
                  (rim_height,.83),(3.,.66)]
        rings([[(center_x+rx*r*math.cos(i*math.tau/24),
                 -ground/SINE+ry*r*math.sin(i*math.tau/24),z)
                for i in range(24)] for z,r in profiles])
        # Raised gray implement/handle is visually distinct from the wooden lip.
        silhouette([(2955.,1149.),(2958.,1147.),(2965.,1148.),
                    (2973.,1151.),(2970.,1152.),(2966.,1152.),
                    (2966.,1156.),(2962.,1157.),(2957.,1153.)],ground,1.6)
        silhouette([(2953.8,1144.8),(2955.4,1145.1),(2956.2,1147.5),
                    (2957.4,1144.8),(2959.,1145.),(2957.,1150.),
                    (2955.6,1149.)],ground,1.0)
        silhouette([(2958.,1146.3),(2963.,1146.5),(2969.,1147.4),
                    (2969.,1148.3),(2963.,1147.6),(2958.,1147.4)],ground,1.0)
        details=dict(native_mask_index=164, rim_center_source=[center_x,1155.5],
                     contact_source_y=ground, raised_handle_apex_source_y=1144.8,
                     radial_segments=24, inferred_vessel_wall_thickness=1.3,
                     inferred_cavity_floor_world_z=3., inferred_handle_depth=1.6)
        limitations=['The raised gray part may be a tool resting in the vessel; its visible outline is retained separately from the wooden rim.',
                     'Circular vessel section, cavity depth and 1–1.6 world-unit handle/tool thickness are inferred.',
                     'Handle joins and cavity are separate closed components; source projection must be rebuilt.']
    elif node == 104:
        # Square plan axes from the cap's two diagonal source edges. Four tiers
        # share vertices at their seams rather than overlap separate boxes.
        cx,ground=2249.,1556.
        ux,uy=8.2,5.0/SINE
        vx,vy=-7.2,4.0/SINE
        profiles=[(0.,.84),(15.,.84),(15.,1.10),(20.,1.10),
                  (20.,.72),(25.,.72),(35.,.36)]
        rings([[(cx+scale*(sx*ux+sy*vx),-ground/SINE+scale*(sx*uy+sy*vy),z)
                for sx,sy in [(-1,-1),(1,-1),(1,1),(-1,1)]]
               for z,scale in profiles])
        # Native silhouette shows a slender shaft and two oblique cross arms.
        # Trace the visible upper stone independently of the stepped pedestal.
        silhouette([(2247.,1527.),(2247.,1511.),(2246.,1508.),
                    (2242.,1504.),(2242.,1500.),(2250.,1496.),
                    (2252.,1497.),(2252.,1504.),(2257.,1508.),
                    (2258.,1512.),(2254.,1514.),(2252.,1513.),
                    (2252.,1527.)],1556.,3.)
        details=dict(native_mask_index=91, contact_source_y=1556.,
                     cross_apex_source=[2250.,1496.], shaft_source_x=[2247.,2252.],
                     square_tier_profile_world=profiles,
                     inferred_cross_depth_world=3.)
        limitations=['The stone cross is supported by the full native silhouette; the earlier short receiver covered only its pedestal.',
                     'Squared tier rear faces and cross thickness are inferred from the visible cap directions.',
                     'Worn stone bevels and chips remain texture detail; outline measurements have approximately 1–2 source-pixel uncertainty.']
    else:
        raise ValueError('Special prop recipe supports only049 and104')
    return vertices,faces,details,limitations


def refine(obj):
    node=int(obj['source_node'].split('-')[-1]); matrix=obj.matrix_world.copy(); before=signature(obj)
    vertices,faces,details,limitations=geometry(node)
    mesh=bpy.data.meshes.new(obj.name+' source-measured special profile')
    inverse=matrix.inverted(); mesh.from_pydata([inverse@Vector(v) for v in vertices],[],faces)
    for mat in obj.data.materials: mesh.materials.append(mat)
    mesh.uv_layers.new(name='Source fallback')
    for loop in mesh.loops:
        x,y,z=vertices[loop.vertex_index]
        mesh.uv_layers.active.data[loop.index].uv=(x/3136,1-(-y*SINE-z*COSINE)/1984)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    topology=dict(vertices=len(bm.verts),faces=len(bm.faces),
                  nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
                  degenerate_faces=sum(f.calc_area()<1e-7 for f in bm.faces))
    if topology['nonmanifold_edges'] or topology['degenerate_faces']:
        raise ValueError('Special prop topology failed: '+str(topology))
    bm.to_mesh(mesh);bm.free();mesh.update();previous=obj.data;obj.data=mesh
    if previous.users==0:bpy.data.meshes.remove(previous)
    obj['leicester_geometry_recipe']=VERSION
    if obj.matrix_world != matrix: raise ValueError('Transform changed')
    return dict(source_node=obj['source_node'],before_geometry_sha256=before,
                after_geometry_sha256=signature(obj),world_transform_drift=0,
                topology=topology,measurements=details,limitations=limitations)


def run(workspace):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open isolated worker model.blend')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import validate
    validate(workspace)
    targets=[o for o in bpy.data.collections[config['collection_name']].all_objects
             if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    if not targets or any(int(o['source_node'].split('-')[-1]) not in SUPPORTED for o in targets):
        raise ValueError('Workspace contains unsupported special props')
    records=[refine(o) for o in targets];hashes=[signature(o) for o in targets]
    for o in targets:refine(o)
    if hashes!=[signature(o) for o in targets]:raise ValueError('Recipe is not idempotent')
    report=dict(recipe=VERSION,asset_id=config['asset_id'],objects=records,idempotence='PASS',
                projection_status='STALE; regenerate modified packet',approval_status='refinement-in-progress',
                texture_generation='not-started',limitations=[n for r in records for n in r['limitations']])
    validate(workspace);(workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection/special-props-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
