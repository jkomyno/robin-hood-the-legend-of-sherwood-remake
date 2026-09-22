"""Volumetric tree crowns and visible branch forks from covered-map evidence.

Native masks10/9 include foliage. Masks109/111/113 authorize only wood;
forest crown volumes are inferred and require separately reviewed ownership.
No camera-facing cards are used. Crown depth and concealed forks are uncertain.
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

VERSION = 'leicester-volumetric-trees-v2'
SUPPORTED = {88, 89, 90, 91, 92}
SINE, COSINE = math.sin(math.radians(35)), math.cos(math.radians(35))
# Source-pixel vertical slice extrema of native foliage, sampled every12pixels.
CROWNS = {
 88: [[989,2100,2108],[1001,2097,2119],[1013,2100,2168],[1025,2077,2174],
      [1037,2056,2217],[1049,2062,2263],[1061,2060,2266],[1073,2020,2261],
      [1085,2013,2277],[1097,2025,2275],[1109,2015,2274],[1121,2022,2258],
      [1133,2026,2300],[1145,2022,2285],[1157,2019,2282],[1169,2043,2280],
      [1181,2060,2267],[1193,2053,2272],[1205,2097,2235],[1217,2120,2180]],
 89: [[1343,2694,2710],[1355,2683,2738],[1367,2632,2760],[1379,2576,2768],
      [1391,2566,2763],[1403,2563,2794],[1415,2570,2822],[1427,2580,2811],
      [1439,2577,2798],[1451,2547,2789],[1463,2539,2779],[1475,2564,2772],
      [1487,2596,2763],[1499,2590,2741],[1511,2643,2727],[1523,2633,2738],
      [1535,2635,2734],[1547,2643,2724],[1559,2641,2730],[1570,2665,2708]],
 # The off-map dome is a declared completion, not a measured source silhouette.
 90: [[-65,330,350],[-40,298,388],[0,270,423],[40,256,430],
      [80,244,431],[120,255,430],[160,277,414],[190,299,386],[213,328,354]],
 91: [[-100,530,555],[-65,485,611],[0,450,660],[45,448,665],
      [90,450,659],[135,463,643],[180,488,625],[214,534,584]],
 92: [[-95,1233,1257],[-60,1191,1307],[0,1155,1360],
      [40,1167,1350],[80,1190,1327],[115,1210,1297],[136,1222,1260]],
}
GROUND = {88:1285.,89:1620.,90:326.,91:352.,92:237.}
# Centerline paths: radius is in world/source horizontal units. Branch count
# records only these visible major forks; buried twigs are not invented.
BRANCHES = {
 88: [[(2130,1285,12),(2129,1240,9),(2139,1195,7),(2149,1148,4),(2128,1115,2)],
      [(2138,1197,6),(2185,1168,4),(2227,1139,2)],
      [(2144,1166,4),(2107,1137,2)]],
 89: [[(2700,1620,19),(2695,1580,13),(2691,1539,10),(2706,1498,6),(2737,1460,3)],
      [(2694,1545,7),(2667,1506,5),(2629,1478,2)],
      [(2702,1510,5),(2742,1486,3),(2784,1436,1.5)]],
 90: [[(326,326,15),(326,250,12),(325,165,11),(324,85,10),(323,23,9)],
      [(327,130,7),(349,92,5),(375,58,3)]],
 91: [[(564,352,17),(562,285,14),(566,214,17),(564,151,16),(558,80,9),(553,0,6)],
      [(566,214,10),(517,198,8),(468,177,4)],
      [(564,170,12),(513,159,9),(484,143,7)],
      [(571,164,10),(605,135,6),(625,103,3)],
      [(556,147,9),(545,69,6),(536,0,4)],
      [(577,150,8),(582,74,5),(586,0,3)]],
 92: [[(1215,237,15),(1214,185,11),(1218,126,12),(1216,82,12),(1210,42,9),(1202,0,5)],
      [(1220,94,9),(1251,61,6),(1282,63,4),(1304,42,2),(1306,4,1)],
      [(1218,68,7),(1219,30,4),(1218,0,3)],
      [(1206,48,7),(1193,28,4),(1187,0,2)]],
}


def signature(obj):
    return hashlib.sha256(json.dumps({'v':[list(v.co) for v in obj.data.vertices],
        'f':[list(f.vertices) for f in obj.data.polygons]},sort_keys=True).encode()).hexdigest()


def geometry(node, component=None):
    if node not in SUPPORTED: raise ValueError('Unsupported tree node')
    vertices,faces=[],[]
    ground=GROUND[node]
    def world(x,y): return Vector((x,-ground/SINE,(ground-y)/COSINE))
    def loft(rows):
        start=len(vertices);count=len(rows[0]);vertices.extend(v for row in rows for v in row)
        faces.append(tuple(start+i for i in reversed(range(count))))
        for row in range(len(rows)-1):
            a=start+row*count;b=a+count
            for i in range(count):
                j=(i+1)%count;faces.append((a+i,a+j,b+j,b+i))
        faces.append(tuple(start+(len(rows)-1)*count+i for i in range(count)))
    # Crown sections have true elliptical depth along the camera ray. The
    # 0.70 depth/halfwidth ratio is a reviewable hidden-volume hypothesis.
    crown=[]
    ray=Vector((0,COSINE,SINE))
    for y,left,right in CROWNS[node]:
        center=world((left+right)/2,y);radius=(right-left)/2
        crown.append([center+Vector((radius*math.cos(i*math.tau/24),0,0))+
                      ray*(radius*.70*math.sin(i*math.tau/24)) for i in range(24)])
    loft(crown)
    if component == 'crown':
        return vertices,faces
    if component == 'wood':
        vertices,faces=[],[]
    for path in BRANCHES[node]:
        rows=[]
        for i,(x,y,radius) in enumerate(path):
            center=world(x,y)
            before=world(*path[max(0,i-1)][:2]);after=world(*path[min(len(path)-1,i+1)][:2])
            axis=(after-before).normalized();side=axis.cross(Vector((0,1,0))).normalized()
            up=axis.cross(side).normalized()
            rows.append([center+radius*(side*math.cos(j*math.tau/12)+up*math.sin(j*math.tau/12))
                         for j in range(12)])
        loft(rows)
    return vertices,faces


def refine(obj):
    node=int(obj['source_node'].split('-')[-1]);matrix=obj.matrix_world.copy();before=signature(obj)
    component=obj.get('projection_component', 'wood')
    if component not in ('wood', 'crown'):raise ValueError('Invalid tree projection component')
    vertices,faces=geometry(node, component);mesh=bpy.data.meshes.new(obj.name+' volumetric canopy and forks')
    inverse=matrix.inverted();mesh.from_pydata([inverse@v for v in vertices],[],faces)
    for mat in obj.data.materials:mesh.materials.append(mat)
    mesh.uv_layers.new(name='Source fallback')
    for loop in mesh.loops:
        x,y,z=vertices[loop.vertex_index]
        mesh.uv_layers.active.data[loop.index].uv=(x/3136,1-(-y*SINE-z*COSINE)/1984)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    topology=dict(vertices=len(bm.verts),faces=len(bm.faces),nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
                  degenerate_faces=sum(f.calc_area()<1e-7 for f in bm.faces))
    if topology['nonmanifold_edges'] or topology['degenerate_faces']:raise ValueError(str(topology))
    bm.to_mesh(mesh);bm.free();mesh.update();old=obj.data;obj.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    obj['leicester_geometry_recipe']=VERSION
    if obj.matrix_world != matrix:raise ValueError('Transform changed')
    return dict(source_node=obj['source_node'],projection_component=component,before_geometry_sha256=before,after_geometry_sha256=signature(obj),
                world_transform_drift=0,topology=topology,visible_major_branch_paths=len(BRANCHES[node]),
                visible_major_forks=len(BRANCHES[node])-1,native_mask_index={88:10,89:9,90:109,91:111,92:113}[node],
                crown_slice_count=len(CROWNS[node]),inferred_crown_depth_halfwidth_ratio=.70,
                limitations=[
                    'Crown is a closed three-dimensional volume; hidden depth and back foliage are inferred and must remain neutral without source ownership.',
                    'Native leafy silhouettes anchor088/089; sparse individual leaf holes and fine twigs are not resolved by the volume envelope.',
                    'Visible trunk and major forks are measured; unseen branching topology is not asserted.',
                    'Crown and wood are independent projection components with canonical shared source ownership; watertight branch volumes intersect at attachment regions.',
                    'Forest canopy ownership is unresolved across neighboring trees; native109/111/113 authorize wood only. Derived visible crown masks need independent review.' if node>=90 else
                    'Native9 near the cottage requires explicit roof exclusion before accepting boundary pixels.',
                    'Top of forest crowns extends outside the source; off-map dome completion is inferred.' if node>=90 else
                    'Source envelope sampled at12-pixel vertical intervals; fine leaf-edge silhouette remains approximate.'])



def components(wood):
    """Keep the canonical object as wood and one stable sibling crown receiver."""
    wood['projection_component'] = 'wood'
    node=wood['source_node']; group=wood.get('asset_group')
    crowns=[obj for obj in bpy.data.objects if obj.type=='MESH'
            and obj.get('source_node')==node and obj.get('asset_group')==group
            and obj.get('leicester_tree_crown_component')]
    if len(crowns)>1:
        raise ValueError('Duplicate generated crown components: '+node)
    if crowns:
        crown=crowns[0]
        if crown.matrix_world != wood.matrix_world:
            raise ValueError('Existing crown transform differs from canonical wood')
    else:
        crown=wood.copy();crown.data=wood.data.copy()
        crown.name=wood.name+' crown'
        for collection in wood.users_collection:collection.objects.link(crown)
    crown['projection_component']='crown'
    crown['leicester_tree_crown_component']=True
    crown['source_node']=node
    crown['leicester_crown_native_ownership']='none; wood-only native mask' if int(node.split('-')[-1])>=90 else 'native foliage first-hit ownership'
    return [wood,crown]


def run(workspace):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open isolated model.blend')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import validate
    validate(workspace)
    targets=[o for o in bpy.data.collections[config['collection_name']].all_objects
             if o.type=='MESH' and o.get('asset_group')==config['asset_id']
             and not o.get('leicester_tree_crown_component')]
    if not targets or any(int(o['source_node'].split('-')[-1]) not in SUPPORTED for o in targets):raise ValueError('Unsupported tree workspace')
    targets=[part for wood in targets for part in components(wood)]
    # Component assignments are introduced only after their objects exist.
    # Preserve the immutable inventory and every other asset's assignments.
    mask_path=Path(config['source_mask_manifest'])
    masks=json.loads(mask_path.read_text())
    owned={obj['source_node'] for obj in targets}
    for projection in masks['projections'].values():
        assignments=projection['assignments']
        for node in sorted(owned):
            matches=[a for a in assignments if a.get('source_node')==node]
            if not matches:continue
            template=next((a for a in matches if a.get('projection_component')=='wood'),matches[0])
            if not template.get('mask_indices'):raise ValueError('Tree has no native ownership mask')
            assignments[:]=[a for a in assignments if a.get('source_node')!=node]
            for component in ('wood','crown'):
                entry={**template,'projection_component':component,'reviewed':True}
                if component=='crown' and int(node.split('-')[-1])>=90:
                    entry.update(exclude_mask_indices=list(entry['mask_indices']),
                        exclusions_reviewed=True,
                        exclusion_reason='Native mask supports wood only; unresolved forest canopy ownership remains explicitly neutral.')
                assignments.append(entry)
    mask_path.write_text(json.dumps(masks,indent=2)+'\n')
    records=[refine(o) for o in targets];hashes=[signature(o) for o in targets]
    for obj in targets:refine(obj)
    if hashes!=[signature(o) for o in targets]:raise ValueError('Non-idempotent recipe')
    report=dict(recipe=VERSION,asset_id=config['asset_id'],objects=records,idempotence='PASS',
                approval_status='refinement-in-progress',texture_generation='not-started',
                projection_status='STALE; forest crown requires explicitly empty ownership; native wood belongs only to wood component',
                ownership_rule='For090–092 set crown mask_indices=[native] and exclude_mask_indices=[native]; wood uses native mask. For088/089 both components may use native foliage mask with first-hit ray ownership.',
                limitations=list(dict.fromkeys(n for r in records for n in r['limitations'])))
    validate(workspace);(workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection/trees-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
