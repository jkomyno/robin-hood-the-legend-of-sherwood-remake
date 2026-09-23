"""CPU orthographic crop of actual source-atlas meshes (no image generation).

Designed for emission-only map atlases; rejects textured hits with no explicit
UV map/image rather than inventing a material. Uses source-camera pixels at 35°.
"""
import sys,json,math
from pathlib import Path
from array import array
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refinement_review import _save

def render(collection_name,crop,output):
    left,top,right,bottom=crop;vertices=[];triangles=[];records=[];cache={}
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    direction=Vector((0,-cosine,sine));down=Vector((0,-sine,-cosine))
    for obj in bpy.data.collections[collection_name].all_objects:
        if obj.type!='MESH' or obj.hide_render:continue
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        if not points:continue
        px=[p.x for p in points];py=[p.dot(down) for p in points]
        if min(px)>right or max(px)<left or min(py)>bottom or max(py)<top:continue
        offset=len(vertices);vertices.extend(points);obj.data.calc_loop_triangles()
        for triangle in obj.data.loop_triangles:
            triangles.append(tuple(offset+i for i in triangle.vertices));records.append((obj,tuple(triangle.loops),triangle.material_index))
    tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True);pixels=[]
    for sy in range(bottom-1,top-1,-1):
        for sx in range(left,right):
            hit,normal,index,_=tree.ray_cast(Vector((sx+.5,0,0))+down*(sy+.5)+direction*100000,-direction)
            if hit is None:pixels.extend((0,0,0,1));continue
            obj,loops,slot=records[index];material=obj.data.materials[slot]
            textures=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
            uvnodes=[n for n in material.node_tree.nodes if n.type=='UVMAP']
            if not textures or not uvnodes:raise ValueError('Explicit source atlas required: '+obj.name)
            texture=textures[-1];image=texture.image
            if image.name not in cache:cache[image.name]=np.array(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
            data=cache[image.name];uv=obj.data.uv_layers[uvnodes[-1].uv_map]
            a,b,c=(vertices[i] for i in triangles[index]);u=b-a;v=c-a;q=hit-a
            denom=u.dot(u)*v.dot(v)-u.dot(v)**2
            bu=(q.dot(u)*v.dot(v)-q.dot(v)*u.dot(v))/denom
            bv=(q.dot(v)*u.dot(u)-q.dot(u)*u.dot(v))/denom
            st=uv.data[loops[0]].uv*(1-bu-bv)+uv.data[loops[1]].uv*bu+uv.data[loops[2]].uv*bv
            x=st.x*image.size[0]-.5;y=st.y*image.size[1]-.5;x0=math.floor(x);y0=math.floor(y);tx=x-x0;ty=y-y0
            h,w=data.shape[:2];sample=lambda xx,yy:data[max(0,min(h-1,yy)),max(0,min(w-1,xx)),:3]
            rgb=(sample(x0,y0)*(1-tx)+sample(x0+1,y0)*tx)*(1-ty)+(sample(x0,y0+1)*(1-tx)+sample(x0+1,y0+1)*tx)*ty
            pixels.extend((*rgb,1))
    _save(Path(output),right-left,bottom-top,array('f',pixels))

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];render(args[0],json.loads(args[1]),args[2])
