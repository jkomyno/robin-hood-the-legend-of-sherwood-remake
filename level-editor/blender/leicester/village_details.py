"""Source-silhouette joinery details with explicitly inferred hidden thickness."""
import json
import math
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector


def silhouette_prism(workspace, index, pixel_to_world, thickness, pixel_filter=None):
    c=json.loads((workspace/'workspace.json').read_text());manifest=Path(c['source_mask_manifest']);contract=json.loads(manifest.read_text());inventory=(manifest.parent/contract['mask_inventory']).resolve();m=next(m for m in json.loads(inventory.read_text())['masks'] if m['index']==index)
    image=bpy.data.images.load(str((inventory.parent/m['png']).resolve()),check_existing=False);width,height=image.size;pixels=np.empty(width*height*4,dtype=np.float32);image.pixels.foreach_get(pixels);bpy.data.images.remove(image);bitmap=pixels.reshape(height,width,4)[::-1,:,0]>0.5
    occupied={(int(x),int(y)) for y,x in np.argwhere(bitmap) if pixel_filter is None or pixel_filter(int(x)+m['box_top_left'][0],int(y)+m['box_top_left'][1])};boundary=[]
    if not occupied:raise ValueError('Empty reviewed detail silhouette')
    for x,y in occupied:
        for neighbor,edge in [((x,y-1),((x,y),(x+1,y))),((x+1,y),((x+1,y),(x+1,y+1))),((x,y+1),((x+1,y+1),(x,y+1))),((x-1,y),((x,y+1),(x,y)))]:
            if neighbor not in occupied:boundary.append((edge,(x,y)))
    corners={p for x,y in occupied for p in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]};indices={};grid=[];split_corners=0
    # Raster diagonals touch at one corner only. Keep their incident faces in
    # separate vertex fans so no vertical edge acquires four side faces.
    for px,py in sorted(corners):
        pending={(x,y) for x,y in [(px-1,py-1),(px,py-1),(px-1,py),(px,py)] if (x,y) in occupied};fans=0
        while pending:
            seed=min(pending);pending.remove(seed);fan={seed};queue=[seed]
            while queue:
                x,y=queue.pop();neighbors={(x-1,y),(x+1,y),(x,y-1),(x,y+1)}&pending;pending-=neighbors;fan|=neighbors;queue.extend(neighbors)
            vertex_index=len(grid);grid.append((px,py));fans+=1
            for cell in fan:indices[((px,py),cell)]=vertex_index
        split_corners+=fans-1
    front=[Vector(pixel_to_world(x+m['box_top_left'][0],y+m['box_top_left'][1])) for x,y in grid];n=len(front)
    normal=(Vector(pixel_to_world(1,0))-Vector(pixel_to_world(0,0))).cross(Vector(pixel_to_world(0,1))-Vector(pixel_to_world(0,0))).normalized();vertices=front+[v+normal*thickness for v in front]
    quads=[tuple(indices[(p,(x,y))] for p in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]) for x,y in sorted(occupied)];faces=quads+[tuple(n+i for i in reversed(f)) for f in quads]+[(indices[(a,cell)],indices[(b,cell)],n+indices[(b,cell)],n+indices[(a,cell)]) for (a,b),cell in boundary]
    mesh=bpy.data.meshes.new(f'Leicester Native{index} Detail');mesh.from_pydata(vertices,[],faces);mesh.uv_layers.new(name='UVMap');bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);bm.to_mesh(mesh);bm.free()
    if bad:raise ValueError(f'Native{index} prism has {bad} nonmanifold edges')
    material=bpy.data.materials.get('Leicester Detail Unknown') or bpy.data.materials.new('Leicester Detail Unknown');material.diffuse_color=(.5,.5,.5,1);mesh.materials.append(material)
    return mesh,{'native_mask':index,'source_pixels':len(occupied),'thickness':thickness,'nonmanifold_edges':bad,'diagonal_pixel_fans_split':split_corners}


def longhouse_wheel(workspace,config):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));dy_dx=-0.2125;dy_dpy=-8/34
    def plane(px,py):
        y=-716/sine+(px-2771.5)*dy_dx+(py-716)*dy_dpy
        return px,y,(-py-y*sine)/cosine
    mesh,report=silhouette_prism(workspace,132,plane,2.5)
    name='Leicester Longhouse Spare Wheel';obj=bpy.data.objects.get(name)
    if obj is None:
        obj=bpy.data.objects.new(name,mesh);bpy.data.collections[config['collection_name']].objects.link(obj)
    else:obj.data=mesh
    obj['source_node']='building-003';obj['asset_group']=config['asset_id'];obj['projection_component']='spare-wheel';obj['part_name']='Eight-spoke spare wheel'
    manifest=Path(config['source_mask_manifest']);contract=json.loads(manifest.read_text());rows=contract['projections']['exterior']['assignments'];rows[:]=[r for r in rows if not(r.get('source_node')=='building-003' and r.get('projection_component')=='spare-wheel')];rows.append({'source_node':'building-003','projection_component':'spare-wheel','mask_indices':[132],'reviewed':True,'evidence':'Native132 silhouette and wheel132-mask.png: single rim, hub, eight radial spokes. Location2771.5,699 source pixels; hidden lean8world units and thickness2.5 inferred.'});manifest.write_text(json.dumps(contract,indent=2)+'\n')
    report.update(spokes=8,inference='Plane follows the front wall orientation and leans eight world units toward it; hidden thickness2.5. Exact native rim, hub and spoke apertures retained.')
    return report


def stilt_ladder(workspace,obj):
    a=Vector((2019.43,-3240.61,72.03));b=Vector((2040.65,-3231.74,72.03));c=Vector((2038.85,-3287.07,0.02));normal=(b-a).cross(c-a);distance=normal.dot(a);sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    inverse=np.linalg.inv(np.array([[normal.y,normal.z],[-sine,-cosine]]))
    def plane(px,py):
        y,z=inverse@np.array([distance-normal.x*px,py]);return px,float(y),float(z)
    mesh,report=silhouette_prism(workspace,180,plane,2.5)
    transform=obj.matrix_world.inverted()
    for vertex in mesh.vertices:vertex.co=transform@vertex.co
    obj.data=mesh
    report.update(rails=2,rungs=9,enclosed_source_apertures=8,inference='Original sloped receiver plane retained; two-unit-and-a-half hidden board depth inferred. Native180 defines the two rails and nine crossboards.')
    return report


def gabled_accessories(workspace,config,update_masks=True):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));wall_slope=-34.67/52.38
    # Both receivers follow the existing gable wall direction. Native artwork
    # fixes their screen silhouette; the ladder's top height and lean remain
    # explicit depth hypotheses anchored to that wall.
    top=(2925.,487.,94.);bottom=(2907.,583.,0.)
    top_y=(-top[1]-top[2]*cosine)/sine;bottom_y=-bottom[1]/sine
    ladder_dy=(bottom_y-top_y-wall_slope*(bottom[0]-top[0]))/(bottom[1]-top[1])
    def ladder_plane(px,py):
        y=top_y+wall_slope*(px-top[0])+ladder_dy*(py-top[1]);return px,y,(-py-y*sine)/cosine
    def wheel_plane(px,py):
        y=-580/sine+wall_slope*(px-2952.)-(py-580.)*5/28
        return px,y,(-py-y*sine)/cosine
    reports=[];assignments=[]
    for index,component,plane,details in [(123,'spare-wheel',wheel_plane,{'spokes':8,'inferred_lean':5.}),(124,'access-ladder',ladder_plane,{'rails':2,'rungs':7,'enclosed_source_apertures':6,'source_top':list(top),'source_foot':list(bottom),'inferred_depth_lean':bottom_y-top_y})]:
        mesh,report=silhouette_prism(workspace,index,plane,2.5)
        name=f'Leicester Northeast Gabled {component.title()}';obj=bpy.data.objects.get(name)
        if obj is None:obj=bpy.data.objects.new(name,mesh);bpy.data.collections[config['collection_name']].objects.link(obj)
        else:obj.data=mesh
        obj['source_node']='building-009';obj['asset_group']=config['asset_id'];obj['projection_component']=component;obj['part_name']=component.replace('-',' ').title()
        reports.append({'component':component,**report,**details})
        assignments.append({'source_node':'building-009','projection_component':component,'mask_indices':[index],'reviewed':True,'evidence':'gabled-ladder-wheel-close.png: native123 separate wheel and native124 two rails, seven rungs, six enclosed apertures. Exact mask silhouette; concealed thickness2.5 and gable-aligned receiver lean are inferred.'})
    if update_masks:
        path=Path(config['source_mask_manifest']);contract=json.loads(path.read_text());rows=contract['projections']['exterior']['assignments'];components={r['projection_component'] for r in assignments};rows[:]=[r for r in rows if not(r.get('source_node')=='building-009' and r.get('projection_component') in components)];rows.extend(assignments);path.write_text(json.dumps(contract,indent=2)+'\n')
    return {'components':reports,'inference':'Native masks determine visible apertures and silhouette. Wheel follows gable plane with five-unit lean; ladder top94 follows gable contact, footground0, and depth2.5 are hypotheses requiring eight-view review.'}


def gabled_lean_to(workspace,roof_obj,fence_obj):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    anchors=[Vector((2889.99,-1013.09,59.91)),Vector((2917.20,-978.29,84.34)),Vector((2853.03,-928.11,78.23))]
    normal=(anchors[1]-anchors[0]).cross(anchors[2]-anchors[0]);distance=normal.dot(anchors[0]);inverse=np.linalg.inv(np.array([[normal.y,normal.z],[-sine,-cosine]]))
    def roof_plane(px,py):
        y,z=inverse@np.array([distance-normal.x*px,py]);return px,float(y),float(z)
    def eave(px):return 508.3+(px-2825.8)*(532.0-508.3)/(2889.99-2825.8) if px<=2889.99 else 532.0+(px-2889.99)*(492.0-532.0)/(2917.2-2889.99)
    roof,roof_report=silhouette_prism(workspace,120,roof_plane,2.5,lambda x,y:y<=eave(x)+1.)
    for vertex in roof.vertices:vertex.co=roof_obj.matrix_world.inverted()@vertex.co
    roof_obj.data=roof
    reports=[];merged=bmesh.new()
    for label,origin,slope,pixel_filter in [
        ('front',(2825.8,-962.9),(-1013.1+962.9)/(2889.99-2825.8),lambda x,y:x<=2890 and y>eave(x)+1.),
        ('return',(2890.,-1013.1),(-972.7+1013.1)/(2915.2-2890.),lambda x,y:x>2890 and y>eave(x)+1.)]:
        def plane(px,py):
            y=origin[1]+(px-origin[0])*slope;return px,y,(-py-y*sine)/cosine
        mesh,report=silhouette_prism(workspace,120,plane,2.,pixel_filter);merged.from_mesh(mesh);reports.append({'panel':label,**report});bpy.data.meshes.remove(mesh)
    mesh=bpy.data.meshes.new('Leicester Northeast Lean-to Open Fence');merged.to_mesh(mesh);merged.free();mesh.uv_layers.new(name='UVMap');mesh.materials.append(bpy.data.materials['Leicester Detail Unknown'])
    for vertex in mesh.vertices:vertex.co=fence_obj.matrix_world.inverted()@vertex.co
    fence_obj.data=mesh
    return {'roof':roof_report,'fence_panels':reports,'horizontal_rails_per_run':3,'inference':'Native120 retains plank eave, upright supports, three fence rails and gate boards/apertures. Roof receiver follows inherited sloped plane; front/return fence planes follow inherited ground edges extended to source silhouette. Concealed depths2/2.5 are inferred; panel junction and roof contact require rendered review.'}


def gabled_barrel(obj):
    sine=math.sin(math.radians(35));center=Vector((2935.5,-579.0/sine,0));segments=24;vertices=[];faces=[]
    def rings(profile,cap_start,cap_end):
        start=len(vertices)
        for z,radius in profile:
            for i in range(segments):
                angle=2*math.pi*i/segments;vertices.append(center+Vector((radius*math.cos(angle),radius*math.sin(angle),z)))
        for j in range(len(profile)-1):
            for i in range(segments):a=start+j*segments+i;b=start+j*segments+(i+1)%segments;faces.append((a,b,b+segments,a+segments))
        if cap_start:faces.append(tuple(reversed(range(start,start+segments))))
        if cap_end:faces.append(tuple(range(start+(len(profile)-1)*segments,start+len(profile)*segments)))
    rings([(0.,9.),(2.,9.8),(12.,11.),(23.,10.),(25.,9.5)],True,True)
    # The smaller vessel is visibly open. Its inner wall and floor close the
    # mesh without substituting a disk across the source-visible opening.
    rings([(25.,6.),(28.,6.4),(38.,7.),(42.,7.5),(42.,6.),(34.,5.5)],True,True)
    mesh=bpy.data.meshes.new('Leicester Northeast Barrel and Bucket');mesh.from_pydata([obj.matrix_world.inverted()@v for v in vertices],[],faces);mesh.uv_layers.new(name='UVMap');bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not edge.is_manifold for edge in bm.edges);deg=sum(face.calc_area()<1e-8 for face in bm.faces);bm.to_mesh(mesh);bm.free()
    if bad or deg:raise ValueError(f'Barrel/bucket topology invalid: {bad}/{deg}')
    material=bpy.data.materials.get('Leicester Detail Unknown') or bpy.data.materials.new('Leicester Detail Unknown');material.diffuse_color=(.5,.5,.5,1);mesh.materials.append(material);obj.data=mesh
    return {'native_mask':122,'parts':['bulged barrel','smaller open bucket'],'radial_segments':segments,'source_center_x':2935.5,'ground_center_source_y':579.,'heights':[25.,42.],'maximum_radii':[11.,7.5],'inference':'gabled-barrel-close.png shows a large barrel supporting a smaller open bucket. Rotational symmetry, concealed radial depth and eight-unit bucket interior are inferred; source widths and overall silhouette constrain placement.'}


def longhouse_shed(workspace,obj):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    anchors=[Vector((2800.65,-1199.61,65.92)),Vector((2813.84,-1139.54,90.34)),Vector((2886.39,-1218.70,65.92))]
    normal=(anchors[1]-anchors[0]).cross(anchors[2]-anchors[0]);distance=normal.dot(anchors[0]);inverse=np.linalg.inv(np.array([[normal.y,normal.z],[-sine,-cosine]]))
    def roof_plane(px,py):
        y,z=inverse@np.array([distance-normal.x*px,py]);return px,float(y),float(z)
    roof_pixels=[(2801.,637.),(2813.,579.),(2899.,588.),(2888.,648.)]
    def inside(px,py):
        signs=[(b[0]-a[0])*(py-a[1])-(b[1]-a[1])*(px-a[0]) for a,b in zip(roof_pixels,roof_pixels[1:]+roof_pixels[:1])]
        return min(signs)>=0 or max(signs)<=0
    def component(px,py):
        if inside(px+.5,py+.5):return 'roof'
        if py>=637+(px-2801)*11/87 and px<=2888:return 'front'
        if px>=2888:return 'right'
        return 'left'
    def wall(origin,slope):
        def point(px,py):
            y=origin[1]+(px-origin[0])*slope;return px,y,(-py-y*sine)/cosine
        return point
    planes={'roof':roof_plane,'front':wall((2800.65,-1199.61),(-1218.70+1199.61)/(2886.39-2800.65)),'left':wall((2800.65,-1199.61),(60.07)/(13.19)),'right':wall((2886.39,-1218.70),60.14/13.24)}
    merged=bmesh.new();reports=[]
    for label,plane in planes.items():
        mesh,report=silhouette_prism(workspace,131,plane,2.5 if label=='roof' else 2.,lambda x,y:component(x,y)==label);merged.from_mesh(mesh);reports.append({'surface':label,**report});bpy.data.meshes.remove(mesh)
    mesh=bpy.data.meshes.new('Leicester Longhouse Open Picket Shed');merged.to_mesh(mesh);merged.free();mesh.uv_layers.new(name='UVMap');mesh.materials.append(bpy.data.materials['Leicester Detail Unknown'])
    for vertex in mesh.vertices:vertex.co=obj.matrix_world.inverted()@vertex.co
    obj.data=mesh
    return {'components':reports,'roof_source_corners':roof_pixels,'front_lower_pickets':4,'picket_source_centers_x':[2855,2862,2869,2876],'inference':'Native131 front upper opening, four lower pickets, left braced gate and dark side boards replace the solid collision volume. Source roof outline clips four distinct receiver planes derived from inherited footprint; concealed depth2/2.5 and panel joints remain inferred. No invented opaque back wall fills native openings.'}


def longhouse_fence(workspace,obj):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));merged=bmesh.new();reports=[]
    def plane(origin,slope):
        def point(px,py):
            y=origin[1]+(px-origin[0])*slope;return px,y,(-py-y*sine)/cosine
        return point
    front=plane((2580.,-1161.),-16/36);back=plane((2574.,-600/sine),6/72)
    for index,label,receiver,pixel_filter in [(129,'front',front,lambda x,y:2580<=x<=2618 and 0<=front(x,y)[2]<=40),(130,'back',back,None)]:
        mesh,report=silhouette_prism(workspace,index,receiver,2.,pixel_filter);merged.from_mesh(mesh);reports.append({'panel':label,**report});bpy.data.meshes.remove(mesh)
    # The long return is almost edge-on in the source. Its depth is resolved
    # from the front/back fences; three rails follow their visible rail phase.
    vertices=[];faces=[]
    def beam(a,b,width):
        a=Vector(a);b=Vector(b);direction=(b-a).normalized();u=Vector((1,0,0))*width/2;v=direction.cross(u).normalized()*width/2;start=len(vertices)
        vertices.extend([p+du*u+dv*v for p in (a,b) for du,dv in [(-1,-1),(1,-1),(1,1),(-1,1)]])
        faces.extend(tuple(start+i for i in face) for face in [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    far=(2578.,back(2578,580)[1]);near=(2580.,-1161.)
    for high,low in [(10.,5.),(22.,13.),(34.,21.)]:beam((*far,high),(*near,low),2.5)
    beam((*far,0.),(*far,42.),3.);beam((*near,0.),(*near,30.),3.)
    timber=bpy.data.meshes.new('Leicester Longhouse Fence Return');timber.from_pydata(vertices,[],faces);merged.from_mesh(timber);bpy.data.meshes.remove(timber);bmesh.ops.recalc_face_normals(merged,faces=list(merged.faces));mesh=bpy.data.meshes.new('Leicester Longhouse Open Fence');merged.to_mesh(mesh);merged.free();mesh.uv_layers.new(name='UVMap');mesh.materials.append(bpy.data.materials['Leicester Detail Unknown'])
    for vertex in mesh.vertices:vertex.co=obj.matrix_world.inverted()@vertex.co
    obj.data=mesh
    return {'source_panels':reports,'return_rails':3,'return_endpoint_posts':2,'inference':'Front native129 and back native130 openings are explicit. Almost edge-on long return uses three connecting rails and endpoint posts; concealed thickness2.5/3, changing rail heights and back-ground source ordinate600 are inferred from adjoining source silhouettes. Foreground hay pixels outside the front fence ground/height envelope are not geometry.'}


def gabled_canopy(workspace,config,roof_obj,update_masks=True):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    pixels=[(2983.,490.),(3033.,443.),(3078.,474.),(3023.,518.)]
    heights=[86.68,86.66,64.70,75.0]
    world=[Vector((x,(-y-z*cosine)/sine,z)) for (x,y),z in zip(pixels,heights)]
    def bary(px,py,tri):
        matrix=np.array([[pixels[i][0] for i in tri],[pixels[i][1] for i in tri],[1.,1.,1.]])
        return np.linalg.solve(matrix,np.array([px,py,1.]))
    def roof_plane(px,py):
        tri=(0,1,2);weights=bary(px,py,tri)
        if min(weights)<-1e-5:tri=(0,2,3);weights=bary(px,py,tri)
        return sum((world[i]*float(weight) for i,weight in zip(tri,weights)),Vector())
    def roof_pixel(px,py):return any(min(bary(px+.5,py+.5,tri))>=0 for tri in [(0,1,2),(0,2,3)])
    mesh,roof_report=silhouette_prism(workspace,121,roof_plane,3.,roof_pixel)
    for vertex in mesh.vertices:vertex.co=roof_obj.matrix_world.inverted()@vertex.co
    roof_obj.data=mesh;reports=[{'component':'roof',**roof_report}]
    assignments=[]
    for label,x0,y0,z0,x1,y1,span in [('left',3023.,518.,75.,3020.,596.,(3015,3027)),('right',3072.,477.,64.7,3067.,557.,(3063,3075))]:
        top_y=(-y0-z0*cosine)/sine;bottom_y=-y1/sine;dy=(bottom_y-top_y)/(y1-y0)
        def plane(px,py):
            y=top_y+(py-y0)*dy;return px,y,(-py-y*sine)/cosine
        mesh,report=silhouette_prism(workspace,121,plane,3.,lambda x,y:span[0]<=x<=span[1] and y>=y0)
        name=f'Leicester Northeast Canopy {label.title()} Post';obj=bpy.data.objects.get(name)
        if obj is None:obj=bpy.data.objects.new(name,mesh);bpy.data.collections[config['collection_name']].objects.link(obj)
        else:obj.data=mesh
        component=f'canopy-{label}-post';obj['source_node']='building-010';obj['asset_group']=config['asset_id'];obj['projection_component']=component;obj['part_name']=f'Canopy {label} support post'
        reports.append({'component':component,**report,'source_top':[x0,y0],'source_foot':[x1,y1],'inferred_top_height':z0,'inferred_depth_lean':bottom_y-top_y})
        assignments.append({'source_node':'building-010','projection_component':component,'mask_indices':[121],'reviewed':True,'evidence':'canopy121-post-grid.png identifies two continuous post silhouettes. Geometry clips to the corresponding narrow pixel strip; depth lean follows inherited roof height and hypothesized ground0.'})
    if update_masks:
        path=Path(config['source_mask_manifest']);contract=json.loads(path.read_text());rows=contract['projections']['exterior']['assignments'];components={r['projection_component'] for r in assignments};rows[:]=[r for r in rows if not(r.get('source_node')=='building-010' and r.get('projection_component') in components)];rows.extend(assignments);path.write_text(json.dumps(contract,indent=2)+'\n')
    return {'components':reports,'source_roof_corners':pixels,'inference':'Roof corner heights anchored to inherited back86.7/right64.7; left eave75 chosen to meet native silhouette. Post bases assume ground0, requiring substantial concealed depth lean; this is a reviewable hypothesis. Exact native plank apertures preserved by silhouette mesh.'}
