"""Close stone-wall and field-bank receivers and soften their exposed shoulders.

Existing plan corners and elevations anchor these modest profile repairs. The
rounded stone coping and bank shoulder width are inferred from the artwork,
not measurements of concealed back surfaces.
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

VERSION='leicester-boundary-profiles-v4'
WALLS={34,35,36,37,38,39,50,51,53,62,63,70,71,73,381}
BANKS={378,379,380,382,383}
TIMBER={53,73}
HAY={70,71}
# Authored plan/elevation anchors in map-pixel units; convert with the fixed35degree projection.
ANCHORS={34: [[2477.0, 385.92834, 0.0, 31.929], [2467.0, 379.882, 0.0, 31.882002], [2593.0, 321.12503, 0.0, 29.126001], [2614.0, 319.8773, 0.0, 28.878002], [2739.0, 204.73462, 0.0, 24.735], [2819.0, 143.38904, 0.0, 22.389002], [2832.0, 146.3273, 0.0, 22.328001], [2845.0, 128.75803, 0.0, 21.759], [2929.0, 59.167023, 0.0, 19.167002], [2939.0, 70.3403, 0.0, 19.341002], [2616.0, 326.0083, 0.0, 29.009]], 35: [[2939.0, 70.99998, 0.0, 20.243], [2928.0, 61.99997, 0.0, 20.059], [2978.0, 60.998833, 0.0, 20.999], [3057.5679, 51.933144, 0.0, 22.514002], [3137.2104, 55.28704, 0.0, 24.001001], [3130.0, 62.000023, 0.0, 23.849], [3060.0, 60.53859, 0.0, 22.539001], [2988.7234, 70.84609, 0.0, 21.177002]], 36: [[1939.9818, 1216.0387, 0.0, 17.001001], [1948.9679, 1219.1708, 0.0, 17.001001], [1837.0297, 1324.8239, 0.0, 17.001001], [1828.0436, 1321.6918, 0.0, 17.001001]], 37: [[2190.0054, 1142.0931, 0.0, 17.001001], [2195.6965, 1148.4336, 0.0, 17.001001], [1944.8828, 1222.4989, 0.0, 17.001001], [1939.1915, 1216.1584, 0.0, 17.001001]], 38: [[2297.4233, 1064.9788, 0.0, 19.001001], [2306.0952, 1069.0701, 0.0, 19.001001], [2189.5132, 1150.3657, 0.0, 19.001001], [2180.8413, 1146.2744, 0.0, 19.001001]], 39: [[2455.4805, 1045.7693, 0.0, 20.001001], [2458.5034, 1053.631, 0.0, 20.001001], [2298.3452, 1073.8899, 0.0, 20.001001], [2295.3223, 1066.0282, 0.0, 20.001001]], 50: [[3063.187, 1146.8677, 0.0, 22.001001], [2997.8584, 1219.3174, 0.0, 22.001001], [2987.082, 1216.1206, 0.0, 22.001001], [3052.4106, 1143.6709, 0.0, 22.001001]], 51: [[3028.4692, 1232.5085, 0.0, 8.001], [3021.7817, 1238.1814, 0.0, 8.001], [2976.0967, 1220.4636, 0.0, 22.001001], [2982.7842, 1214.7908, 0.0, 22.001001]], 53: [[3136.6726, 1161.0889, 0.0, 32.001003], [3135.4958, 1163.0541, 0.0, 32.001003], [3060.5515, 1148.2917, 0.0, 32.001003], [3061.7283, 1146.3265, 0.0, 32.001003]], 62: [[2631.9116, 918.9032, 0.0, 49.001003], [2685.373, 988.44745, 0.0, 36.001003], [2673.688, 991.4027, 0.0, 36.001003], [2620.2266, 921.85846, 0.0, 49.001003]], 63: [[2698.2397, 873.0791, 0.0, 24.001001], [2759.074, 968.8022, 0.0, 25.001001], [2751.9468, 970.29236, 0.0, 25.001001], [2691.1125, 874.5693, 0.0, 24.001001]], 70: [[3088.548, 1078.5376, 0.0, 23.001001], [3062.0, 1070.0028, 0.0, 8.003], [3054.4956, 1043.4954, 0.0, 0.001], [3076.0, 1026.3977, 0.0, 8.398001], [3089.243, 1025.9312, 0.0, 15.141001], [3102.4524, 1032.7189, 0.0, 23.001001]], 71: [[3088.356, 1079.9868, 0.0, 22.001001], [3102.8582, 1032.3447, 0.0, 22.001001], [3115.142, 1029.6884, 0.0, 14.7300005], [3137.704, 1031.9478, 0.0, 0.001], [3119.6094, 1061.9587, 0.0, 5.677], [3102.4292, 1074.9335, 0.0, 14.059001]], 73: [[3125.5593, 1062.68, 0.0, 17.0], [3160.703, 1073.4912, 0.0, 17.0], [3128.8118, 1107.5968, 0.0, 26.000002], [3093.6682, 1096.7856, 0.0, 26.000002]], 378: [[249.50464, 1926.2213, 0.0, 27.061], [236.61008, 1923.3267, 0.0, 27.061], [286.34692, 1882.8003, 0.0, 27.061], [303.4522, 1885.4318, 0.0, 27.061], [338.71527, 1851.2214, 0.0, 27.061], [405.03104, 1800.6951, 0.0, 27.061], [486.87335, 1759.6423, 0.0, 27.061], [525.1894, 1731.8645, 0.0, 27.061], [575.8208, 1687.2739, 0.0, 27.061], [695.03107, 1719.1162, 0.0, 27.061], [769.24164, 1751.7476, 0.0, 27.061], [933.1425, 1804.6132, 0.0, 27.061], [925.6659, 1809.288, 0.0, 27.061], [758.45215, 1758.0636, 0.0, 27.061], [661.08374, 1717.0109, 0.0, 27.061], [579.2417, 1706.2214, 0.0, 27.061], [495.29413, 1767.2742, 0.0, 27.061], [407.66278, 1814.6426, 0.0, 27.061], [312.9258, 1890.4319, 0.0, 27.061]], 379: [[210.66302, 1940.6678, 0.0, 40.001003], [218.72574, 1948.3363, 0.0, 40.001003], [11.465736, 2020.0287, 0.0, 40.001003], [3.4030304, 2012.3602, 0.0, 40.001003]], 380: [[1190.7501, 1899.4895, 0.0, 27.001001], [1183.2264, 1905.7964, 0.0, 27.001001], [992.90784, 1831.1038, 0.0, 27.001001], [1000.43146, 1824.7969, 0.0, 27.001001]], 382: [[0.9763471, 1546.2107, 0.0, 50.001003], [272.13327, 1820.9987, 0.0, 50.001003], [-0.7527151, 1909.5891, 0.0, 50.001003], [-271.90964, 1634.8011, 0.0, 50.001003]], 383: [[406.0559, 1678.294, 0.0, 0.001], [272.4488, 1820.8966, 0.0, 50.001003], [1.1492462, 1545.9641, 0.0, 50.001003], [0.7473297, 1267.5579, 0.0, 0.001]]}

# Source crest rises toward the wall junction at the right; the inherited
# receiver's elevation gradient was reversed. Pixel crest samples at x960,
# 968,975,982,989 have y1816,1811,1805,1802,1801 respectively.
ANCHORS[381]=[[1000.4681, 1824.7965, 0.0, 24.0], [992.94446, 1831.1034, 0.0, 30.0], [960.74896, 1818.4679, 0.0, 2.5], [968.2726, 1812.161, 0.0, 1.2]]

# Two halves share one observed hay ridge. Reconcile subpixel imported plan
# offsets and one-pixel height disagreement before rounding the slopes.
for a,b in [(0,0),(5,1)]:
    left,right=ANCHORS[70][a],ANCHORS[71][b]
    shared=[(left[i]+right[i])/2 for i in range(4)]
    ANCHORS[70][a]=list(shared);ANCHORS[71][b]=list(shared)

# Native223 cliff alpha supplies the exposed crest, sampled every16pixels.
# The ground contact stays on the authored front edge; hidden plateau remains
# a declared interpolation rather than a recovered terrain heightfield.
CLIFF_382_CREST=[(0,1844),(16,1841),(32,1838),(48,1837),(64,1834),(80,1837),
                 (96,1845),(112,1827),(128,1821),(144,1821),(160,1815),(176,1804),
                 (192,1797),(208,1796),(224,1793),(240,1788),(256,1782),(272,1768)]
ANCHORS[382]=[ANCHORS[382][0]]+[[x,1909.35-.3247*x,0,1909.35-.3247*x-y] for x,y in reversed(CLIFF_382_CREST)]+[ANCHORS[382][3]]


def signature(obj):
    return hashlib.sha256(json.dumps({'v':[list(v.co) for v in obj.data.vertices],
        'f':[list(p.vertices) for p in obj.data.polygons]},sort_keys=True).encode()).hexdigest()


def repair(obj):
    if obj['source_node']=='building-053':
        from props_timber import refine
        return refine(obj)
    before=signature(obj);matrix=[list(row) for row in obj.matrix_world]
    bm=bmesh.new();bm.from_mesh(obj.data)
    initial={'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges)}
    node=int(obj['source_node'].rsplit('-',1)[1]);bank=node in BANKS
    width=None;edge_count=0
    if obj.get('leicester_boundary_recipe')!=VERSION:
        # Shared corners remove the independently fitted top/side seams before
        # coping refinement. Concealed bases close the same authored footprint.
        bm.clear()
        points=ANCHORS[node];count=len(points)
        sin=math.sin(math.radians(35));cos=math.cos(math.radians(35))
        inverse=obj.matrix_world.inverted()
        vertices=[bm.verts.new(inverse@Vector((x,-y/sin,z/cos)))
                  for which in (2,3) for point in points
                  for x,y,z in [(point[0],point[1],point[which])]]
        for i in range(count):
            j=(i+1)%count
            bm.faces.new([vertices[i],vertices[j],vertices[count+j],vertices[count+i]])
        bm.faces.new(list(reversed(vertices[:count])))
        if node in HAY:
            # Rounded cross-section inside the measured boundary. The rise is
            # inferred from the soft hay slope; perimeter anchors stay fixed.
            top_points=[Vector((x,-y/sin,z/cos)) for x,y,_,z in points]
            center=sum(top_points,Vector())/count
            previous=vertices[count:]
            for t in (.25,.5,.75):
                ring=[bm.verts.new(inverse@(p.lerp(center,t)+Vector((0,0,3*math.sin(math.pi*t/2)/cos)))) for p in top_points]
                for i in range(count):
                    j=(i+1)%count;bm.faces.new([previous[i],previous[j],ring[j],ring[i]])
                previous=ring
            peak=bm.verts.new(inverse@(center+Vector((0,0,3/cos))))
            for i in range(count):bm.faces.new([previous[i],previous[(i+1)%count],peak])
        elif node==382:
            center=sum((v.co for v in vertices[count:]),Vector())/count
            peak=bm.verts.new(center)
            for i in range(count):bm.faces.new([vertices[count+i],vertices[count+(i+1)%count],peak])
        else:
            bm.faces.new(vertices[count:])
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.75)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.0001)
        zs=[(obj.matrix_world@v.co).z for v in bm.verts];bottom,top=min(zs),max(zs)
        ground=[e for e in bm.edges if e.is_boundary and all(abs((obj.matrix_world@v.co).z-bottom)<.15 for v in e.verts)]
        if ground:bmesh.ops.holes_fill(bm,edges=ground,sides=0)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        rotation=obj.matrix_world.to_3x3()
        edges=[e for e in bm.edges if e.is_manifold
               and all((obj.matrix_world@v.co).z>bottom+(top-bottom)*.70 for v in e.verts)
               and any((rotation@f.normal).z>.7 for f in e.link_faces)
               and any(abs((rotation@f.normal).z)<.4 for f in e.link_faces)]
        width=0 if node in TIMBER|HAY or node==382 else min(6 if bank else 2,(top-bottom)*(.17 if bank else .07))
        edge_count=len(edges)
        if edges and width:
            bmesh.ops.bevel(bm,geom=edges,offset=width,segments=1 if bank else 2,
                            affect='EDGES',clamp_overlap=True)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(obj.data);obj.data.update();obj['leicester_boundary_recipe']=VERSION
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name='UVMap')
    final={'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),
           'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    bm.free()
    if matrix!=[list(row) for row in obj.matrix_world]:raise ValueError('Transform drift')
    return {'object':obj.name,'source_node':obj['source_node'],'kind':'hay mound slope' if node in HAY else 'timber receiver' if node in TIMBER else 'field bank' if bank else 'stone boundary',
        'before':initial,'after':final,'before_geometry_sha256':before,'after_geometry_sha256':signature(obj),
        'shoulder_edges':edge_count,'inferred_shoulder_width':width,'world_transform_drift':0}


def run(workspace):
    w=Path(workspace).resolve();c=json.loads((w/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=w/'model.blend':raise ValueError('Open worker model.blend')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import validate
    validate(w)
    targets=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==c['asset_id']]
    if not targets or any(int(o['source_node'].rsplit('-',1)[1]) not in WALLS|BANKS for o in targets):
        raise ValueError('Only owned stone boundary and field-bank nodes are supported')
    records=[repair(o) for o in targets];first=[signature(o) for o in targets]
    for o in targets:repair(o)
    if first!=[signature(o) for o in targets]:raise ValueError('Recipe not idempotent')
    report={'recipe':VERSION,'asset_id':c['asset_id'],'objects':records,'idempotence':'PASS',
        'source_supported':'Stone coping is rounded and field-bank shoulders slope in the map artwork; existing plan corners and elevations anchor this profile pass.',
        'limitations':['Shoulder radius and hidden ground closures are inferred; rock-by-rock masonry is retained as source texture detail.',
                      'Field banks remain discrete receivers; adjoining terrain elevation is not reconstructed by this prop recipe.',
                      *(['Native053 is a measured13-picket palisade; timber depth is inferred and no stone bevel is applied.'] if any(o['source_node']=='building-053' for o in targets) else []),
                      *(['Native070/071 are the two adjoining hay-mound slopes. Foreground timber exclusion and native073 gate/retainer decomposition remain separate review requirements.'] if any(int(o['source_node'].rsplit('-',1)[1]) in HAY|{73} for o in targets) else []),
                      'Native silhouette, occlusion and fixed-view projection require inspection after the edit.'],
        'projection_status':'STALE; run modified packet','approval_status':'refinement-in-progress','texture_generation':'not-started'}
    validate(w);(w/'inspection').mkdir(exist_ok=True)
    (w/'inspection'/'boundary-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    print(json.dumps(run(a.workspace)))
