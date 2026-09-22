"""Measured riverside eaves, kept distinct from their supporting wall volumes."""
import json
import math
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector


def riverside_roofs(workspace,config,bynode,update_masks=True):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));depth=3.0
    def roof_plane(anchors):
        a,b,c=map(Vector,anchors);normal=(b-a).cross(c-a);distance=normal.dot(a)
        inverse=np.linalg.inv(np.array([[normal.y,normal.z],[-sine,-cosine]]))
        def point(px,py):
            y,z=inverse@np.array([distance-normal.x*px,py]);return Vector((px,float(y),float(z)))
        return point
    main_plane=roof_plane([(3011.74,-1635.30,96.50),(3076.67,-1611.32,159.97),(3136.70,-1773.90,159.99)])
    porch_plane=roof_plane([(3060.51,-1765.78,76.84),(3045.42,-1723.59,76.85),(3012.43,-1735.37,51.21)])
    main_pixels=[(3005.,866.),(3076.,793.),(3137.,886.5),(3065.,955.)]
    porch_pixels=[(3008.,956.),(3044.,924.),(3062.,947.),(3020.,979.)]
    main=[main_plane(*p) for p in main_pixels];porch=[porch_plane(*p) for p in porch_pixels]
    # The far eave lies beyond the map edge. Retain the inherited roof slope,
    # with the same small overhang as the measured visible slope.
    back_ridge,front_ridge=main[1],main[2]
    far_back=Vector((3131.98,-1590.59,107.47));far_front=Vector((3193.62,-1752.90,106.26))
    extension=(far_back-back_ridge).normalized()*7.0
    far_back+=extension;far_front+=extension
    roofs=[('building-064','main-roof',main,135,main_pixels),('building-065','opposite-roof',[back_ridge,far_back,far_front,front_ridge],135,None),('building-066','porch-roof',porch,136,porch_pixels)]
    reports=[];assignments=[]
    mask_path=Path(config['source_mask_manifest']);contract=json.loads(mask_path.read_text());rows=contract['projections']['exterior']['assignments']
    for node,component,top,mask,pixels in roofs:
        body=bynode[node]
        if body.get('riverside_overhang_revision')!='source-eaves-v1':
            inverse=body.matrix_world.inverted()
            for vertex in body.data.vertices:
                world=body.matrix_world@vertex.co
                if world.z>1.0:world.z-=depth;vertex.co=inverse@world
            body['riverside_overhang_revision']='source-eaves-v1';body.data.update()
        vertices=top+[v-Vector((0,0,depth)) for v in top]
        faces=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
        mesh=bpy.data.meshes.new(f'Leicester Riverside {component}');mesh.from_pydata(vertices,[],faces);mesh.uv_layers.new(name='UVMap')
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not edge.is_manifold for edge in bm.edges);deg=sum(face.calc_area()<1e-8 for face in bm.faces);bm.to_mesh(mesh);bm.free()
        if bad or deg:raise ValueError(f'Invalid roof slab {component}: {bad}/{deg}')
        material=bpy.data.materials.get('Leicester Roof Unknown') or bpy.data.materials.new('Leicester Roof Unknown');material.diffuse_color=(.5,.5,.5,1);mesh.materials.append(material)
        name=f'Leicester Riverside {component.title()}';obj=bpy.data.objects.get(name)
        if obj is None:obj=bpy.data.objects.new(name,mesh);bpy.data.collections[config['collection_name']].objects.link(obj)
        else:obj.data=mesh
        obj['source_node']=node;obj['asset_group']=config['asset_id'];obj['projection_component']=component;obj['part_name']=component.replace('-',' ').title()
        original=next(row for row in rows if row.get('source_node')==node and not row.get('projection_component'))
        assignment={**original,'projection_component':component,'evidence':'User overhang correction; roof-overhang-user-review/source-corners.json records visible roof corners. Separate roof receiver extends to observed source silhouette; nearest-source visibility prevents roof pixels landing on recessed wall.'};assignments.append(assignment)
        reports.append({'source_node':node,'component':component,'native_mask':mask,'source_corners':pixels,'world_corners':[list(v) for v in top],'vertical_thickness':depth,'nonmanifold_edges':bad,'degenerate_faces':deg})
    if update_masks:
        components={row['projection_component'] for row in assignments};rows[:]=[row for row in rows if row.get('projection_component') not in components];rows.extend(assignments);mask_path.write_text(json.dumps(contract,indent=2)+'\n')
    return {'revision':'source-eaves-v1','roofs':reports,'inference':'Visible main and porch eaves measured with 1–2pixel uncertainty. Hidden main front ridge and opposite eave remain inherited hypotheses, opposite eave extended7world units. Roof slabs have3world-unit vertical thickness; wall top vertices recessed3 to meet undersides. Source-mask inventory unchanged.'}
