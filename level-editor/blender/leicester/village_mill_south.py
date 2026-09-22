"""Open mill-south cottage roof supports and annex framing from native masks."""
import json
import math
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector


def refine(workspace,config,bynode,update_masks=True):
    try:from village_details import silhouette_prism
    except ImportError:from leicester.village_details import silhouette_prism
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));reports=[];assignments=[]
    top=[Vector(p) for p in [(2852.66,-2169.51,90.34),(2926.89,-2017.31,90.34),(2835.95,-1972.80,142.83),(2761.69,-2125.23,142.83)]]
    mesh=bpy.data.meshes.new('Leicester Mill South Closed Main Roof');mesh.from_pydata(top+[v-Vector((0,0,7.32)) for v in top],[],[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]);bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
    material=bpy.data.materials.get('Leicester Detail Unknown') or bpy.data.materials.new('Leicester Detail Unknown');material.diffuse_color=(.5,.5,.5,1);mesh.materials.append(material)
    for vertex in mesh.vertices:vertex.co=bynode['building-040'].matrix_world.inverted()@vertex.co
    bynode['building-040'].data=mesh;reports.append({'source_node':'building-040','correction':'Original four visible roof corner anchors retained; hidden notch/underside replaced by closed7.32-unit roof slab.'})
    roof_pixels=[(v.x,-v.y*sine-v.z*cosine) for v in top]
    def inside(px,py):
        signs=[(b[0]-a[0])*(py-a[1])-(b[1]-a[1])*(px-a[0]) for a,b in zip(roof_pixels,roof_pixels[1:]+roof_pixels[:1])];return min(signs)>=0 or max(signs)<=0
    def main_support(px,py):
        y=-1244/sine+(px-2849.)*(-44.28/90.97);return px,y,(-py-y*sine)/cosine
    def frame_plane(px,py):
        y=-1173/sine+(px-2978.5)*(37/sine/29);return px,y,(-py-y*sine)/cosine
    mesh,report=silhouette_prism(workspace,166,frame_plane,3.,lambda x,y:0<=frame_plane(x+.5,y+.5)[2]<=110)
    for vertex in mesh.vertices:vertex.co=bynode['building-057'].matrix_world.inverted()@vertex.co
    bynode['building-057'].data=mesh;reports.append({'source_node':'building-057','description':'Native166 open annex side-frame with curved diagonal brace and two posts.',**report})
    for node,anchors,polygon in [
        ('building-046',[(2978.48,-2042.70,73.25),(3006.71,-1984.83,95.22),(2906.17,-1936.03,95.22)],[(2978.5,1111.7),(3006.7,1060.5),(2906.2,1032.5),(2878.1,1083.5)]),
        ('building-047',[(3003.54,-2047.64,58.60),(3032.57,-1985.38,65.92),(3010.84,-1975.20,78.13)],[(3003.5,1126.5),(3032.6,1084.8),(3010.8,1068.9),(2981.8,1110.7)])]:
        a,b,c=map(Vector,anchors);normal=(b-a).cross(c-a);distance=normal.dot(a);inverse=np.linalg.inv(np.array([[normal.y,normal.z],[-sine,-cosine]]))
        def plane(px,py):
            y,z=inverse@np.array([distance-normal.x*px,py]);return px,float(y),float(z)
        def roof_pixel(px,py):
            signs=[(b[0]-a[0])*(py+.5-a[1])-(b[1]-a[1])*(px+.5-a[0]) for a,b in zip(polygon,polygon[1:]+polygon[:1])];return min(signs)>=0 or max(signs)<=0
        mesh,report=silhouette_prism(workspace,162,plane,3.,roof_pixel)
        for vertex in mesh.vertices:vertex.co=bynode[node].matrix_world.inverted()@vertex.co
        bynode[node].data=mesh;reports.append({'source_node':node,'description':'Native162 roof planks and edge on inherited roof plane.',**report})
    details=[('building-040','main-roof-support',160,main_support,lambda x,y:y>=1160 and not inside(x+.5,y+.5) and 0<=main_support(x+.5,y+.5)[2]<=94)]
    for label,px,py,z,foot_y,span in [('front',3003.,1126.,58.60,1176.,(2995,3008)),('back',3032.,1085.,65.92,1150.,(3026,3035))]:
        top_y=(-py-z*cosine)/sine;bottom_y=-foot_y/sine;dy=(bottom_y-top_y)/(foot_y-py)
        def plane(x,y,px=px,py=py,top_y=top_y,dy=dy):
            wy=top_y+(y-py)*dy;return x,wy,(-y-wy*sine)/cosine
        details.append(('building-047',f'annex-{label}-outer-post',162,plane,lambda x,y,span=span,py=py:span[0]<=x<=span[1] and y>=py))
    for node,component,index,plane,pixel_filter in details:
        mesh,report=silhouette_prism(workspace,index,plane,3.,pixel_filter);name=f'Leicester Mill South {component.title()}';obj=bpy.data.objects.get(name)
        if obj is None:obj=bpy.data.objects.new(name,mesh);bpy.data.collections[config['collection_name']].objects.link(obj)
        else:obj.data=mesh
        obj['source_node']=node;obj['asset_group']=config['asset_id'];obj['projection_component']=component;obj['part_name']=component.replace('-',' ').title();reports.append({'component':component,**report});assignments.append({'source_node':node,'projection_component':component,'mask_indices':[index],'reviewed':True,'evidence':'native-south-cottage-details.png and mill-south-masks-review.png distinguish full main roof159 plus extension160, front roof support160 and two outer annex posts162. Ground contact follows native post feet; hidden depth3 inferred.'})
    if update_masks:
        path=Path(config['source_mask_manifest']);contract=json.loads(path.read_text());rows=contract['projections']['exterior']['assignments'];components={r['projection_component'] for r in assignments};rows[:]=[r for r in rows if r.get('projection_component') not in components];rows.extend(assignments);path.write_text(json.dumps(contract,indent=2)+'\n')
    return {'parts':reports,'inference':'Source masks distinguish physical openings and post/brace counts. Main roof retains native anchors and7.32 hidden thickness. Annex side-frame foot positions determine receiver plane; outer post feetground0 with inherited roof heights imply a small concealed lean. Other hidden wall/roof volumes remain inherited.'}
