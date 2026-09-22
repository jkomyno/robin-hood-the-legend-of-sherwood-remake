"""Source-anchor-preserving curvature revisions requested in review."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector, Matrix

DIRECTORY=Path(__file__).resolve().parent
sys.path.insert(0,str(DIRECTORY));sys.path.insert(0,str(DIRECTORY.parent))
from south_structures import neutral_mesh,topology,crenels,CUTS
from refinement_workspace import modified
ROOT=DIRECTORY.parents[1]/'work/leicester-refinement'
SINE=math.sin(math.radians(35))


def curve(knots,index,t):
    a,b=knots[index:index+2]
    before=knots[index-1] if index else a-(b-a)
    after=knots[index+2] if index+2<len(knots) else b+(b-a)
    return .5*((2*a)+(-before+b)*t+(2*before-5*a+4*b-after)*t*t+(-before+3*a-3*b+after)*t*t*t)


def native_top(node):
    inventory=json.loads((ROOT/'round-1/inventory/complete-scene.json').read_text())
    obj=next(o for o in inventory['objects'] if o['properties'].get('source_node')==f'building-{node:03}')
    points=[Matrix(obj['matrix_world'])@Vector(v) for v in obj['geometry']['vertices']]
    faces=[p for p in obj['geometry']['polygons'] if max(points[i].z for i in p)-min(points[i].z for i in p)<.001 and min(points[i].z for i in p)>100]
    counts={}
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):
            edge=tuple(sorted((a,b)));counts[edge]=counts.get(edge,0)+1
    edges=[edge for edge,count in counts.items() if count==1];adj={}
    for a,b in edges:adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
    if any(len(v)!=2 for v in adj.values()):raise RuntimeError('Native top outline is not a simple loop')
    start=min(adj);order=[start];previous=None;current=start
    while True:
        nxt=next(n for n in adj[current] if n!=previous)
        if nxt==start:break
        order.append(nxt);previous,current=current,nxt
    return [points[i] for i in order]


def sampled_outline(outline,curves):
    result=[];rounded=0
    for a,b in zip(outline,outline[1:]+outline[:1]):
        selected=None
        for knots in curves:
            for i in range(len(knots)-1):
                if (a.xy-knots[i]).length<.6 and (b.xy-knots[i+1]).length<.6:selected=(knots,i,False)
                if (b.xy-knots[i]).length<.6 and (a.xy-knots[i+1]).length<.6:selected=(knots,i,True)
        if selected:
            knots,i,reverse=selected
            for step in range(6):
                t=step/6;t=1-t if reverse else t;p=curve(knots,i,t);result.append(Vector((p.x,p.y,a.z)))
            rounded+=1
        else:result.append(a.copy())
    return result,rounded


def prism(obj,outline,bottom):
    inverse=obj.matrix_world.inverted();n=len(outline)
    points=[inverse@Vector((p.x,p.y,h)) for h in (bottom,outline[0].z) for p in outline]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=neutral_mesh(obj,points,faces,obj.name+' / rounded outline')
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    return topology(obj)


def turret(workspace):
    evidence=json.loads((ROOT/'south-inspection/southeast-rounding-review.json').read_text())['turret']
    curves=[[Vector((p['native_game'][0],-p['native_game'][1]/SINE)) for p in evidence[key]] for key in ['outer_arc','inner_arc']]
    report={'source_evidence':'south-inspection/southeast-rounding-review.json','samples_per_native_span':6,'changes':[]}
    for node in [111,119]:
        obj=next(o for o in bpy.data.collections['Leicester Working'].all_objects if o.type=='MESH' and o.get('source_node')==f'building-{node:03}' and not o.hide_render)
        outline,count=sampled_outline(native_top(node),curves)
        expected=10 if node==111 else 5
        if count!=expected:raise RuntimeError(f'Expected {expected} curved spans for{node}, got{count}')
        result=prism(obj,outline,0)
        if node==111:result=crenels(obj,CUTS[111])
        report['changes'].append({'source_node':obj['source_node'],'rounded_native_spans':count,**result})
    return report


def manor(workspace):
    evidence=json.loads((ROOT/'south-inspection/southeast-rounding-review.json').read_text())['manor']
    knots=[Vector((p[0],-p[1]/SINE)) for p in evidence['eave_arc_native_game']]
    z=evidence['eave_game_height']/math.cos(math.radians(35))
    inventory=json.loads((ROOT/'round-1/inventory/complete-scene.json').read_text())
    collection=bpy.data.collections['Leicester Working'];native={};peaks=[]
    for node in range(153,157):
        record=next(o for o in inventory['objects'] if o['properties'].get('source_node')==f'building-{node:03}')
        points=[Matrix(record['matrix_world'])@Vector(record['geometry']['vertices'][i]) for i in record['geometry']['polygons'][-1]]
        peak=max(points,key=lambda p:p.z);peaks.append(peak);native[node]=points
    peak=sum(peaks,Vector())/len(peaks)
    report={'source_evidence':'south-inspection/southeast-rounding-review.json','samples_per_native_span':6,
            'shared_ridge_endpoint':list(peak),'max_ridge_reconciliation_world':max((p-peak).length for p in peaks),'changes':[]}
    for node in range(153,157):
        obj=next(o for o in collection.all_objects if o.type=='MESH' and o.get('source_node')==f'building-{node:03}' and not o.hide_render)
        span=node-153;rim=[curve(knots,span,i/6) for i in range(7)]
        points=[peak.copy()]+[Vector((p.x,p.y,z)) for p in rim];n=len(points);inverse=obj.matrix_world.inverted()
        vertices=[inverse@(p+Vector((0,0,offset))) for offset in [0,-3] for p in points]
        faces=[]
        for i in range(1,n-1):faces.extend([(0,i,i+1),(n,n+i+1,n+i)])
        boundary=[0]+list(range(1,n))
        faces.extend((a,b,b+n,a+n) for a,b in zip(boundary,boundary[1:]+boundary[:1]))
        mesh=neutral_mesh(obj,vertices,faces,obj.name+' / rounded hip')
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        report['changes'].append({'source_node':obj['source_node'],'hip_segments':6,**topology(obj)})
    # Reconcile only existing shared hip/ridge and eave seam vertices on the two
    # adjoining slate planes. The separate orange gables retain their geometry.
    for node in [151,152]:
        obj=next(o for o in collection.all_objects if o.type=='MESH' and o.get('source_node')==f'building-{node:03}' and not o.hide_render)
        inverse=obj.matrix_world.inverted();count=0
        for vertex in obj.data.vertices:
            p=obj.matrix_world@vertex.co
            for offset in [0,-3]:
                if min((p-(q+Vector((0,0,offset)))).length for q in peaks)<2:
                    vertex.co=inverse@(peak+Vector((0,0,offset)));count+=1;break
                endpoint=knots[0 if node==151 else -1];target=Vector((endpoint.x,endpoint.y,z+offset))
                if (p-target).length<2:
                    vertex.co=inverse@target;count+=1;break
        report['changes'].append({'source_node':obj['source_node'],'seam_vertices_reconciled':count,**topology(obj)})
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace',type=Path)
    workspace=parser.parse_args(sys.argv[sys.argv.index('--')+1:]).workspace.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    if (workspace/'rounding-report.json').exists():raise RuntimeError('Rounding revision already exists; preserve it')
    asset=json.loads((workspace/'workspace.json').read_text())['asset_id']
    report=manor(workspace) if asset=='leicester-southeast-manor' else turret(workspace)
    (workspace/'rounding-report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    modified(workspace)


if __name__=='__main__':main()
