"""Split the approved market into seven buildings without changing its exterior."""
from pathlib import Path
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
APPROVED_SHA = '302a6445b3398e7fb18caed5dbb46b3d7298ba9a500904953fc4402138e695a7'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def area(points):
    total=0.0
    for i in range(1,len(points)-1):
        a=[x-y for x,y in zip(points[i],points[0])];b=[x-y for x,y in zip(points[i+1],points[0])]
        cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
        total+=math.sqrt(sum(v*v for v in cross))/2
    return total


def clip(vertices, normal, offset, sign):
    result=[]
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        da=sign*(sum(x*y for x,y in zip(a[:3],normal))-offset)
        db=sign*(sum(x*y for x,y in zip(b[:3],normal))-offset)
        if da>=-1e-7:result.append(a)
        if (da>1e-7 and db < -1e-7) or (da < -1e-7 and db>1e-7):
            t=da/(da-db);result.append(tuple(x+(y-x)*t for x,y in zip(a,b)))
    return result


def geometry_signature(obj):
    data={'vertices':[list(v.co)for v in obj.data.vertices],'faces':[list(p.vertices)for p in obj.data.polygons],
          'matrix':[list(row)for row in obj.matrix_world],
          'uv':{layer.name:[list(v.uv)for v in layer.data]for layer in obj.data.uv_layers}}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def main():
    import bpy,bmesh
    from mathutils import Vector
    sys.path.insert(0,str(Path(__file__).parent))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    tooling=select_tooling(WORK/'tooling/94116d984f92dbae')
    source=WORK/'round-1/assets/nottingham-market-terrace/model.blend'
    if digest(source)!=APPROVED_SHA:raise ValueError('Approved parent geometry changed')
    proposal=json.loads((WORK/'town-audit/market-seven-building-grouping-proposal.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.view_layer.update()
    collection=bpy.data.collections['nottingham Working']
    objects=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')=='nottingham-market-terrace']
    assert len(objects)==23
    base=next(o for o in objects if o['source_node']=='building-012');matrix=base.matrix_world.copy();inv=matrix.inverted()
    base.data.calc_loop_triangles();uv_names=[u.name for u in base.data.uv_layers]
    triangles=[]
    for i,tri in enumerate(base.data.loop_triangles):
        vertices=[]
        for vertex,loop in zip(tri.vertices,tri.loops):
            payload=list(matrix@base.data.vertices[vertex].co)
            for layer in base.data.uv_layers:payload.extend(layer.data[loop].uv)
            vertices.append(tuple(payload))
        triangles.append({'index':i,'polygon':tri.polygon_index,'material':base.data.polygons[tri.polygon_index].material_index,'vertices':vertices})
    planes=[]
    world_vertices=[tuple(matrix@v.co)for v in base.data.vertices]
    def anchor_world(native):
        expected=(native[0],-native[1]/math.sin(math.radians(35)))
        closest=min(world_vertices,key=lambda v:math.dist(v[:2],expected))
        return closest[:2] if math.dist(closest[:2],expected)<0.01 else expected
    for entry in proposal['shared_source_partition']['vertical_split_planes']:
        a,b=map(anchor_world,entry['anchors_native_xy'])
        nx=-(b[1]-a[1]);ny=b[0]-a[0]
        if nx<0:nx,ny=-nx,-ny
        planes.append(((nx,ny,0),nx*a[0]+ny*a[1]))
    report={'version':1,'approved_parent':str(source),'approved_parent_sha256':APPROVED_SHA,'tooling':tooling,'unchanged_meshes':[],'components':[],'source_triangles':[],'inference':'Only internal party-wall cut caps are new; approved exterior triangles and all their UV layers are clipped without displacement.'}
    for obj in objects:
        if obj==base:continue
        building=next(g for g in proposal['buildings']if obj['source_node']in g['exclusive_source_nodes'])
        before=geometry_signature(obj);obj['asset_group']=building['proposed_id'];obj['asset_name']=building['proposed_id'].replace('nottingham-','').replace('-',' ').title()
        obj['market_parent_approved_sha256']=APPROVED_SHA
        if geometry_signature(obj)!=before:raise ValueError('Regrouping changed geometry')
        report['unchanged_meshes'].append({'source_node':obj['source_node'],'object':obj.name,'asset_id':obj['asset_group'],'geometry_uv_matrix_sha256':before})
    sums=[0.0]*len(triangles)
    for index,building in enumerate(proposal['buildings'][:4]):
        cuts=[]
        if index>0:cuts.append((*planes[index-1],1))
        if index<3:cuts.append((*planes[index],-1))
        points=[];faces=[];payloads=[];origins=[];lookup={}
        for tri in triangles:
            polygon=tri['vertices']
            for normal,offset,sign in cuts:polygon=clip(polygon,normal,offset,sign)
            fragment_area=area([p[:3]for p in polygon]) if len(polygon)>2 else 0
            if fragment_area<1e-8:continue
            face=[];data=[]
            for p in polygon:
                key=tuple(round(v,6)for v in p[:3])
                if key not in lookup:lookup[key]=len(points);points.append(inv@Vector(p[:3]))
                vi=lookup[key]
                if not face or vi!=face[-1]:face.append(vi);data.append(p)
            if len(face)>1 and face[0]==face[-1]:face.pop();data.pop()
            if len(set(face))<3:raise ValueError('Clipped nonzero triangle collapsed')
            faces.append(face);payloads.append(data);origins.append({'source_triangle':tri['index'],'source_polygon':tri['polygon'],'area_world':fragment_area,'material':tri['material']});sums[tri['index']]+=fragment_area
        component=f'market-base-012-front-{index+1}'
        mesh=bpy.data.meshes.new(component);mesh.from_pydata(points,[],faces);mesh.update()
        for material in base.data.materials:mesh.materials.append(material)
        for k,name in enumerate(uv_names):
            layer=mesh.uv_layers.new(name=name)
            for polygon,payload in zip(mesh.polygons,payloads):
                for loop,p in zip(polygon.loop_indices,payload):layer.data[loop].uv=p[3+2*k:5+2*k]
        bm=bmesh.new();bm.from_mesh(mesh);layer=bm.faces.layers.int.new('source_triangle_plus_one')
        for face,origin in zip(bm.faces,origins):face[layer]=origin['source_triangle']+1;face.material_index=origin['material']
        boundary=[e for e in bm.edges if e.is_boundary]
        caps=bmesh.ops.holes_fill(bm,edges=boundary,sides=0)['faces']
        for face in caps:face[layer]=-1;face.material_index=0
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)}
        if any(defects.values()):raise ValueError((component,defects,[(tuple(e.verts[0].co),tuple(e.verts[1].co),len(e.link_faces))for e in bm.edges if not e.is_manifold]))
        cap_area=sum(f.calc_area()for f in caps)
        cap_plane_error=max((min(max(abs(sum(n[j]*(matrix@v.co)[j]for j in range(3))-offset)/math.sqrt(sum(x*x for x in n))for v in face.verts)for n,offset,_ in cuts)for face in caps),default=0)
        if cap_plane_error>0.001:raise ValueError(('Cap extends off partition plane',component,cap_plane_error))
        bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new(component,mesh);collection.objects.link(obj);obj.matrix_world=matrix
        for key,value in base.items():
            if not key.startswith('reprojection_'):obj[key]=value
        obj['asset_group']=building['proposed_id'];obj['asset_name']=building['proposed_id'].replace('nottingham-','').replace('-',' ').title();obj['part_name']=f'Masonry base section {index+1}'
        obj['projection_component']=component;obj['market_partition_version']=1;obj['market_parent_approved_sha256']=APPROVED_SHA
        report['components'].append({'id':component,'object':obj.name,'asset_id':obj['asset_group'],'source_node':'building-012','geometry_uv_matrix_sha256':geometry_signature(obj),'clipped_faces':origins,'new_internal_cap_area_local':cap_area,'maximum_cap_plane_error_world':cap_plane_error,'vertex_weld_key_precision_world':0.000001,'validation':defects})
    for tri,total in zip(triangles,sums):
        original=area([v[:3]for v in tri['vertices']]);residual=original-total
        if abs(residual)>max(0.002,original*2e-6):raise ValueError(('Source area loss or duplication',tri['index'],original,total,residual))
        report['source_triangles'].append({'source_triangle':tri['index'],'source_polygon':tri['polygon'],'area_world':original,'sum_clipped_area_world':total,'residual':residual})
    base.hide_render=True;base.hide_viewport=True;base['asset_group']=proposal['buildings'][0]['proposed_id'];base['market_canonical_hidden']=True
    report['canonical_object']=base.name;report['canonical_source_retained_once']=True;report['approved_parent_unchanged']=digest(source)==APPROVED_SHA
    report['source_area_conservation']='PASS';report['maximum_triangle_area_residual']=max(abs(x['residual'])for x in report['source_triangles'])
    output=WORK/'market-partitions-v9';output.mkdir(exist_ok=True)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(output/'components.blend'))
    (output/'partition-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print('MARKET_PARTITION_PASS',report['maximum_triangle_area_residual'],flush=True)


if __name__=='__main__':main()
