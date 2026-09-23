"""Add the two source-visible manor ridge finials, preserving every existing mesh."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

DIRECTORY=Path(__file__).resolve().parent
sys.path.insert(0,str(DIRECTORY.parent))
sys.path.insert(0,str(DIRECTORY))
import bpy
from mathutils import Vector
from bridges import object_mesh
from south_structures import topology
from refinement_workspace import modified
from refinement_review import _tree

ASSET='leicester-southeast-manor'
SINE,COSINE=math.sin(math.radians(35)),math.cos(math.radians(35))
SPECIFICATIONS=[
    {'id':'left','source_node':'building-151','anchor':[1337.5,1048.5],
     'crop':[1318,1004,1355,1082],
     'profile':[[1050,3.5],[1048.5,3.5],[1043,3.2],[1034,1.8],[1027,1.5],
                [1024,2.7],[1021,3.4],[1017,3.0],[1013.5,.6]]},
    {'id':'right','source_node':'building-153','anchor':[1518.5,1111.5],
     'crop':[1495,1004,1542,1132],
     'profile':[[1114,2.0],[1111.5,2.0],[1090,1.7],[1086,3.0],[1083,6.0],
                [1080,7.0],[1077,6.0],[1074,3.0],[1072,1.5],[1028,1.5],
                [1025,2.5],[1023,1.2],[1018.5,.35]]},
]


def geometry(obj):
    return hashlib.sha256(json.dumps({'vertices':[list(v.co) for v in obj.data.vertices],
        'faces':[list(p.vertices) for p in obj.data.polygons],
        'matrix':[list(row) for row in obj.matrix_world]},sort_keys=True).encode()).hexdigest()


def refine(workspace):
    config=json.loads((workspace/'workspace.json').read_text())
    if config['asset_id']!=ASSET:raise ValueError('Wrong finial workspace')
    collection=bpy.data.collections[config['collection_name']]
    existing=[o for o in collection.all_objects if o.type=='MESH']
    if any(o.get('manor_finial') for o in existing):raise ValueError('Finials already authored; preserve reviewed revision')
    before={o.name:geometry(o) for o in existing}
    roof=[o for o in existing if o.get('asset_group')==ASSET and o.get('source_node') in
          [f'building-{i}' for i in range(151,157)] and not o.hide_render]
    tree,owners,points=_tree(roof);toward=Vector((0,-COSINE,SINE));down=Vector((0,-SINE,-COSINE))
    depth=max(p.dot(toward) for p in points)+100
    changes=[]
    for spec in SPECIFICATIONS:
        x,y=spec['anchor'];origin=Vector((x,0,0))+down*y+toward*depth
        hit,normal,index,_=tree.ray_cast(origin,-toward)
        if hit is None:raise ValueError('Finial anchor misses rounded roof')
        template=next(o for o in roof if o.get('source_node')==spec['source_node'])
        vertices=[];segments=16
        for pixel_y,radius in spec['profile']:
            center=hit+Vector((0,0,(y-pixel_y)/COSINE))
            if spec['id']=='left':center.x-=max(0.,(1048.5-pixel_y)/35.)*.8
            vertices.extend(center+Vector((radius*math.cos(i*2*math.pi/segments),
                                           radius*math.sin(i*2*math.pi/segments),0)) for i in range(segments))
        rings=len(spec['profile']);faces=[tuple(reversed(range(segments))),tuple((rings-1)*segments+i for i in range(segments))]
        faces.extend((row*segments+i,row*segments+(i+1)%segments,
                      (row+1)*segments+(i+1)%segments,(row+1)*segments+i)
                     for row in range(rings-1) for i in range(segments))
        obj=object_mesh('Southeast Manor / '+spec['id']+' ridge finial',vertices,faces,template,collection)
        obj['projection_component']='roof-finial-'+spec['id'];obj['manor_finial']=spec['id']
        obj.hide_render=False;obj.hide_viewport=False
        changes.append({**spec,'anchor_world':list(hit),'anchor_roof_object':owners[index].name,
                        'segments':segments,**topology(obj)})
    if any(geometry(o)!=before[o.name] for o in existing):raise RuntimeError('Existing geometry changed')
    return {'asset_id':ASSET,'user_feedback':'leicester-southeast-manor needs refinement — two antenna-like things on roof missing [review834c7d14c8b8eccf]',
        'existing_geometry_unchanged':True,'existing_meshes_checked':len(existing),'finials':changes,
        'source_sha256':hashlib.sha256(Path(config['source_path']).read_bytes()).hexdigest(),
        'limitations':['Hidden round cross-sections and roof penetration are inferred from the visible front profiles.',
                       'Existing roof roundness, all original meshes, transforms and source mask assignments retained.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);workspace=args.workspace.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    report=refine(workspace);(workspace/'finial-report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    modified(workspace)


if __name__=='__main__':main()
