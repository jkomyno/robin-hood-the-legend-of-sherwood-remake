"""Read back the stair candidate and render an unrotated source-camera closeup."""
import sys,json,math,hashlib
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(Path(__file__).parent)]
import bpy
from mathutils import Vector
from PIL import Image,ImageDraw
from refinement_workspace import _geometry
from refinement_review import _tree
from derby_upper_west_user_corners import stats
def main():
    p=Path(bpy.data.filepath).parent;g=json.loads((p/'geometry.json').read_text());working=bpy.data.collections['Derby Working']
    actual={o.name:_geometry(o) for o in working.objects};assert actual==g['after']
    s,c=math.sin(math.radians(35)),math.cos(math.radians(35))
    def projected(v):return[v.x,-v.y*s-v.z*c]
    fit=json.loads((p/'user-constraint-fit.json').read_text());errors=[]
    for row in fit['correspondences']:
        o=bpy.data.objects[row['object']];v=o.matrix_world@o.data.vertices[row['vertex_index']].co
        errors.append(math.dist(projected(v),row['target']))
    stair=next(o for o in working.objects if o.get('source_node')=='building-114');sf=json.loads((p/'stair-fit.json').read_text());se=[]
    for row in sf['correspondences']:se.append(math.dist(projected(stair.matrix_world@stair.data.vertices[row['vertex_index']].co),row['target']))
    assert max(errors)<.001 and max(se)<.001
    result=dict(model_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),changed=g['changed'],unchanged=len(actual)-len(g['changed']),
        stair=stats(stair),max_nosing_fit_error=max(se),approved_corners_checked=len(errors),max_approved_corner_error=max(errors))
    frame=json.loads((p/'modified/views.json').read_text());source=Image.open(frame['source_image']).convert('RGB')
    box=(205,980,315,1195);scale=4;w,h=(box[2]-box[0])*scale,(box[3]-box[1])*scale
    raw=source.crop(box).resize((w,h),Image.Resampling.NEAREST);solid=Image.new('RGB',(w,h));pixels=solid.load()
    tree,owners,_=_tree([o for o in working.all_objects if o.type=='MESH' and not o.hide_render]);toward=Vector((0,-c,s));sun=Vector(frame['lighting']['toward_sun']).normalized()
    for y in range(h):
        for x in range(w):
            pt=Vector((box[0]+(x+.5)/scale,-(box[1]+(y+.5)/scale)/s,0));hit,n,index,distance=tree.ray_cast(pt+toward*10000,-toward,20000)
            if hit is None:continue
            shadow=n.dot(sun)>0 and tree.ray_cast(hit+sun*.03,sun)[0] is not None
            value=.16+(0 if shadow else .64*max(0,n.dot(sun)));v=round(255*(12.92*value if value<=.0031308 else 1.055*value**(1/2.4)-.055));pixels[x,y]=(v,v,v)
    camera=frame['views'][0];cx,cy,cz=camera['camera_location'];center=-cy*s-cz*c;tw,th=frame['tile_size'];step=camera['ortho_scale']/th
    textured=Image.open(p/'modified/views/view-0-textured.png').convert('RGB').transform((w,h),Image.Transform.AFFINE,
        (1/(step*scale),0,(box[0]-cx)/step+tw/2,0,1/(step*scale),(box[1]-center)/step+th/2),resample=Image.Resampling.BILINEAR)
    sheet=Image.new('RGB',(w*3,h+25),'#202020');draw=ImageDraw.Draw(sheet)
    for i,(im,label) in enumerate(((raw,'Untouched original'),(solid,'Actual full-scene gray / 48 degrees'),(textured,'Reprojected source-only model'))):sheet.paste(im,(i*w,25));draw.text((i*w+5,6),label,fill='white')
    sheet.save(p/'modified/stair-source-solid-textured.png')
    gray_edges=solid.copy();draw=ImageDraw.Draw(gray_edges)
    for edge in stair.data.edges:
        a,b=[stair.matrix_world@stair.data.vertices[i].co for i in edge.vertices];steps=max(1,math.ceil(math.dist(projected(a),projected(b))*4));previous=None
        for i in range(steps+1):
            v=a.lerp(b,i/steps);q=projected(v);hit,n,index,distance=tree.ray_cast(v+toward*10000,-toward,10001)
            visible=hit is not None and (hit-v).length<.12
            if visible:
                point=((q[0]-box[0])*scale,(q[1]-box[1])*scale)
                if previous is not None:draw.line((previous,point),fill='#ff4040',width=1)
                previous=point
            else:previous=None
    diagnostic=Image.new('RGB',(w*2,h+25),'#202020');diagnostic.paste(raw,(0,25));diagnostic.paste(gray_edges,(w,25));d=ImageDraw.Draw(diagnostic);d.text((5,6),'Original artwork',fill='white');d.text((w+5,6),'Gray with visible actual stair edges (diagnostic)',fill='white');diagnostic.save(p/'modified/stair-gray-edges.png')
    # Identify the receiving solid immediately under both upper rear corners.
    contacts=[]
    contact_tree,contact_owners,_=_tree([o for o in working.all_objects if o.type=='MESH' and not o.hide_render and o!=stair])
    for idx in (26,54):
        v=stair.matrix_world@stair.data.vertices[idx].co
        pt=v+Vector((0,.05,.1));hit,n,index,distance=contact_tree.ray_cast(pt,Vector((0,0,-1)),1000)
        contacts.append(dict(vertex_index=idx,world=list(v),receiver=contact_owners[index].name if index is not None else None,vertical_distance=distance))
    result['upper_contact_rays']=contacts
    stair_tree,_,_=_tree([stair]);landing=next(o for o in working.objects if o.get('source_node')=='building-128');landing_tree,_,_=_tree([landing]);rays=[]
    for y in range(1010,1042):
        for x in range(260,294):
            ray=Vector((x+.5,-(y+.5)/s,0))+toward*10000
            a,an,ai,ad=stair_tree.ray_cast(ray,-toward,20000);b,bn,bi,bd=landing_tree.ray_cast(ray,-toward,20000)
            if ai is not None and bi is not None:rays.append(dict(pixel=[x,y],margin=bd-ad,stair_first=ad<bd))
    clearance=dict(overlap_rays=len(rays),min_margin=min(r['margin'] for r in rays),receiver_in_front=sum(not r['stair_first'] for r in rays),samples=rays)
    (p/'upper-step-ray-clearance.json').write_text(json.dumps(clearance,indent=2));result['upper_step_clearance']={k:v for k,v in clearance.items() if k!='samples'}
    (p/'saved-model-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
