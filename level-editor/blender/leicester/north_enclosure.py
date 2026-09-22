"""Restore the church enclosure contact datum while preserving upper profiles."""
import argparse,json,sys,math
from pathlib import Path
import bpy,bmesh
from mathutils import Vector

NODES=tuple(f'building-{i}' for i in range(365,374))
DATUM=61.04

def arch_lintel(obj):
    original=[obj.matrix_world@v.co for v in obj.data.vertices]
    # Frozen cap anchors are a sloped four-corner coping above the gate.
    corners=[original[i] for i in (14,15,12,13)]
    span=(corners[1]-corners[0]).length;apex=min(p.z for p in original)
    spring=apex-span/2;steps=16;vertices=[]
    for side in range(2):
        left,right=(corners[0],corners[1]) if side==0 else (corners[3],corners[2])
        for upper in (False,True):
            for i in range(steps+1):
                t=i/steps;p=left.lerp(right,t)
                if not upper:p.z=spring+span*.5*math.sqrt(max(0,1-(2*t-1)**2))
                vertices.append(obj.matrix_world.inverted()@p)
    n=steps+1;faces=[]
    for i in range(steps):
        faces.extend(((i,i+1,n+i+1,n+i),(2*n+i,3*n+i,3*n+i+1,2*n+i+1),
                      (i,2*n+i,2*n+i+1,i+1),(n+i,n+i+1,3*n+i+1,3*n+i)))
    faces.extend(((0,n,3*n,2*n),(steps,2*n+steps,3*n+steps,n+steps)))
    mesh=bpy.data.meshes.new(obj.name+' / round gate soffit');mesh.from_pydata(vertices,[],faces)
    for m in obj.data.materials:mesh.materials.append(m)
    mesh.uv_layers.new(name='UVMap');obj.data=mesh
    obj['todo']='Round soffit follows native stone arch; hidden wall thickness and symmetric arc are inferred between measured span/apex anchors.'

def barrel(obj):
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from north_keep_furniture import top_ring
    corners,_=top_ring(obj)
    center=sum(corners,Vector())/4
    u=(corners[1]-corners[0]);v=(corners[2]-corners[1])
    height=center.z-DATUM;length=u.length;width=v.length
    u.normalize();v.normalize();z=Vector((0,0,1));vertices=[]
    horizontal=obj['source_node']=='building-372'
    for t,scale in ((0,.88),(.5,1),(1,.88)):
        for i in range(16):
            angle=2*math.pi*i/16
            if horizontal:
                p=Vector((center.x,center.y,DATUM+height/2))+u*((t-.5)*length)+v*(math.cos(angle)*width*.5*scale)+z*(math.sin(angle)*height*.5*scale)
            else:
                p=Vector((center.x,center.y,DATUM+t*height))+u*(math.cos(angle)*length*.5*scale)+v*(math.sin(angle)*width*.5*scale)
            vertices.append(obj.matrix_world.inverted()@p)
    faces=[tuple(reversed(range(16))),tuple(range(32,48))]
    faces.extend((j*16+i,j*16+(i+1)%16,(j+1)*16+(i+1)%16,(j+1)*16+i) for j in range(2) for i in range(16))
    mesh=bpy.data.meshes.new(obj.name+' / bowed barrel');mesh.from_pydata(vertices,[],faces)
    for m in obj.data.materials:mesh.materials.append(m)
    mesh.uv_layers.new(name='UVMap');obj.data=mesh
    obj['todo']='Barrel taper and unobserved circular back profile are inferred from native upright/lying barrel silhouettes.'

def refine(collection='Leicester Working'):
    rows=[]
    objects=[o for o in bpy.data.collections[collection].all_objects if o.type=='MESH' and o.get('source_node') in NODES]
    if len(objects)!=len(NODES):raise RuntimeError('Enclosure ownership incomplete')
    for obj in objects:
        if obj.get('north_enclosure_recipe'):continue
        if obj['source_node'] in ('building-371','building-372'):barrel(obj)
        if obj['source_node']=='building-368':arch_lintel(obj)
        world=obj.matrix_world.copy();inverse=world.inverted()
        before=[world@v.co for v in obj.data.vertices]
        mesh=obj.data.copy();obj.data=mesh
        raised=0
        for vertex,p in zip(mesh.vertices,before):
            if p.z<1:
                vertex.co=inverse@Vector((p.x,p.y,DATUM));raised+=1
        bm=bmesh.new();bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.5)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6)
        edges=[e for e in bm.edges if e.is_boundary]
        if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-7 for f in bm.faces)
        if bad or deg:raise RuntimeError(f'{obj.name}: topology {bad}/{deg}')
        bm.to_mesh(mesh);bm.free()
        obj['north_enclosure_recipe']='courtyard-enclosure-datum-v1'
        rows.append(dict(source_node=obj['source_node'],raised_vertices=raised,datum=DATUM,nonmanifold_edges=bad,degenerate_faces=deg))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);p.add_argument('--diagnostic',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);rows=refine()
    print(json.dumps(rows,indent=2))
    if not a.diagnostic:
        if Path(bpy.data.filepath).resolve()!=a.workspace.resolve()/'model.blend':raise RuntimeError('Open owned workspace model')
        (a.workspace/'geometry-report.json').write_text(json.dumps(rows,indent=2)+'\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(a.workspace.resolve()/'model.blend'))
