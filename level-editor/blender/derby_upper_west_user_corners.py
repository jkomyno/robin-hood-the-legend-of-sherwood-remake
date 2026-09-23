"""Reconstruct Upper West from immutable user-authored front-edge constraints.

Run with pixel-crenels-v6/model.blend loaded; arguments: frozen JSON, new packet.
The visible front rails determine XY wall planes and actual notch floor heights.
The inherited back thickness and connecting curved runs remain assumptions.
"""
import sys,json,math,hashlib,shutil
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload',
    '/usr/lib/python3.14/site-packages',str(Path(__file__).parent),
    str(Path(__file__).resolve().parents[1]/'refinement')]
import bpy,bmesh
import numpy as np
from PIL import Image
from mathutils import Vector
from audit_corner_constraints import derive
from derby_asset_lower_west_curtain import _wall
from refinement_workspace import _geometry,_reproject,_freeze_masks
from refinement_review import render_review,_tree

ASSET='derby-upper-west-curtain'
TOP=179.5
ANGLE=math.radians(35)
S,C=math.sin(ANGLE),math.cos(ANGLE)

def projected(p):return [p.x,-p.y*S-p.z*C]

def world(path,x,y=None):
    a,b=path['rails']['upper']
    top_y=a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0])
    return Vector((x,-(top_y+TOP*C)/S,TOP if y is None else TOP-(y-top_y)/C))

def gaps(path):
    rails=path['rails'];a,b=rails['upper'];stations=sorted(rails['transitions'])
    boundaries=[a[0],*stations,b[0]];upper=rails['startsUpper'];result=[]
    for left,right in zip(boundaries,boundaries[1:]):
        if not upper:result.append((left,right))
        upper=not upper
    return result

def stats(obj):
    bm=bmesh.new();bm.from_mesh(obj.data)
    result=dict(name=obj.name,source_node=obj.get('source_node'),vertices=len(bm.verts),faces=len(bm.faces),
        boundary=sum(e.is_boundary for e in bm.edges),nonmanifold=sum(not e.is_manifold for e in bm.edges),
        degenerate=sum(f.calc_area()<1e-8 for f in bm.faces),volume=bm.calc_volume(signed=True))
    bm.free()
    assert not(result['boundary'] or result['nonmanifold'] or result['degenerate']) and result['volume']>0,result
    return result

def repartition(config,packet):
    source=Path(config['source_mask_manifest']);manifest=json.loads(source.read_text())
    inventory_path=(source.parent/manifest['mask_inventory']).resolve()
    inventory=json.loads(inventory_path.read_text());records={r['index']:r for r in inventory['masks']}
    old={i:np.array(Image.open(inventory_path.parent/records[i]['png']).convert('L')) for i in (116,117)}
    new={i:old[i].copy() for i in old};union=np.maximum(old[116],old[117]);ox,oy=records[116]['box_top_left']
    assert records[116]['box_top_left']==records[117]['box_top_left']
    all_objects=[o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render]
    tree,owners,_=_tree(all_objects);toward=Vector((0,-C,S));transfers=[]
    for row,col in np.argwhere(union>0):
        x,y=int(col+ox),int(row+oy);p=Vector((x+.5,-(y+.5)/S,0))
        hit,normal,index,distance=tree.ray_cast(p+toward*10000,-toward,20000)
        if index is None:continue
        node=owners[index].get('source_node')
        if node not in ('building-116','building-117'):continue
        owner=int(node[-3:]);other=233-owner
        if new[other][row,col]>0:
            transfers.append(dict(pixel=[x,y],from_node=other,to_node=owner))
            new[owner][row,col]=union[row,col];new[other][row,col]=0
    assert np.array_equal(union,np.maximum(new[116],new[117]))
    directory=packet/'source-authority';directory.mkdir()
    for record in inventory['masks']:
        i=record['index']
        if i in new:
            file=directory/f'{i}.png';Image.fromarray(new[i]).save(file);record['png']=str(file)
        else:record['png']=str((inventory_path.parent/record['png']).resolve())
    (directory/'manifest.json').write_text(json.dumps(inventory,indent=2))
    manifest['mask_inventory']=str(directory/'manifest.json')
    file=packet/'source-masks.json';file.write_text(json.dumps(manifest,indent=2))
    config['source_mask_manifest']=str(file)
    report=dict(original_manifest=str(source),original_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        union_identical=True,added_authority_pixels=0,transfers=transfers,
        rule='Repartition existing116/117pixels only when nearest active scene receiver is116or117')
    (packet/'source-mask-transfer.json').write_text(json.dumps(report,indent=2))

def main():
    frozen,packet=map(Path,sys.argv[sys.argv.index('--')+1:]);packet=packet.resolve();packet.mkdir(exist_ok=False)
    raw=frozen.read_bytes();data=json.loads(raw)
    asset=next(a for a in data['assets'] if a['id']==ASSET)
    assert hashlib.sha256(Path(asset['image_path']).read_bytes()).hexdigest()==asset['source_sha256']
    paths=sorted(asset['paths'],key=lambda p:p['rails']['upper'][1][0]-p['rails']['upper'][0][0],reverse=True)
    assert len(paths)==2
    for path in paths:
        points,stations=derive(path['rails']);assert points==path['points'];assert path['edge']=='front'
    long,short=paths
    assert len(long['rails']['transitions'])==31 and len(short['rails']['transitions'])==8
    (packet/'user-corners.json').write_bytes(raw)
    working=bpy.data.collections['Derby Working'];before={o.name:_geometry(o) for o in working.objects}
    source=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')=='building-117' and o.hide_render)
    current=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')=='building-117' and not o.hide_render)
    original=source.data;source.data=original.copy();inv=source.matrix_world.inverted()
    old_world={i:source.matrix_world@v.co for i,v in enumerate(source.data.vertices)}
    modifications={}
    # Change the actual front footprint lines, not the user's image coordinates.
    for start,end,rear_end,path in [(68,69,70,long),(73,74,75,short)]:
        # The upper observed endpoint is inside the keep contact. Continue the
        # final upper rail through the inherited hidden contact, without adding
        # a transition. The explicitly open lower endpoint remains clipped.
        end_x=old_world[end].x if path is short else path['rails']['upper'][1][0]
        for index,x in [(start,old_world[start].x),(end,end_x)]:
            target=world(path,x);source.data.vertices[index].co=inv@target
            modifications[index]=dict(before=list(old_world[index]),after=list(target))
        delta=world(path,end_x)-old_world[end]
        target=old_world[rear_end]+delta;target.z=TOP
        source.data.vertices[rear_end].co=inv@target
        modifications[rear_end]=dict(before=list(old_world[rear_end]),after=list(target))
    for index,p in old_world.items():
        if abs(p.z-TOP)<.01:
            point=source.matrix_world@source.data.vertices[index].co;point.z=TOP;source.data.vertices[index].co=inv@point
    long_gaps=gaps(long);short_gaps=gaps(short)
    # The long final opening is genuinely open-ended. The extra cutter travel
    # clears the angled back boundary; it is not another authored transition.
    cut_long=long_gaps[:-1]+[(long_gaps[-1][0],long_gaps[-1][1]+4)]
    cuts=[(68,69,0,cut_long),(73,74,0,short_gaps),
        (77,76,0,((146,158),)),(81,77,0,((111,122),)),
        (82,81,1,((1040,1049),)),(82,78,0,((101,110),)),(78,68,0,((132,147),))]
    try:result=_wall(source,cuts,notch_depth=26,allow_corner_cuts=True)
    finally:
        temporary=source.data;source.data=original;bpy.data.meshes.remove(temporary)
    rebuilt=bpy.data.objects[result['object']]
    for v in rebuilt.data.vertices:
        if abs(v.co.z-(TOP-26))>.025:continue
        if v.co.x>165 and v.co.y < -2160:v.co.z=TOP-long['rails']['depth']/C
        elif v.co.x>180 and v.co.y > -2050:v.co.z=TOP-short['rails']['depth']/C
    current.data=rebuilt.data.copy();bpy.data.objects.remove(rebuilt,do_unlink=True)
    # Split continuous source-front edges at explicit user endpoints. Targets
    # may lie inside a top face edge rather than an existing Boolean corner.
    bm=bmesh.new();bm.from_mesh(current.data)
    for path in paths:
        for x,y in path['points']:
            target=world(path,x,y);nearest=min(bm.verts,key=lambda v:(v.co-target).length)
            if (nearest.co-target).length<.003:
                nearest.co=target;continue
            found=False
            for edge in list(bm.edges):
                a,b=[v.co for v in edge.verts];delta=b-a
                t=(target-a).dot(delta)/delta.length_squared
                if .000001<t<.999999 and (a+delta*t-target).length<.003:
                    _,vertex=bmesh.utils.edge_split(edge,edge.verts[0],t);vertex.co=target;found=True;break
            assert found,dict(path=path['id'],target=[x,y],nearest_distance=(nearest.co-target).length)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(current.data);bm.free();current.data.update()
    current['crenellation_notches']=len(long_gaps)+len(short_gaps)+5
    current['upper_west_crenels_revision']='exact-user-front-rails-v1'
    bpy.context.view_layer.update()
    after={o.name:_geometry(o) for o in working.objects};changed=[n for n in before if before[n]!=after[n]]
    assert changed==[current.name]
    correspondences=[]
    for path in paths:
        for index,(x,y) in enumerate(path['points']):
            target=world(path,x,y)
            vertex=min(current.data.vertices,key=lambda v:(current.matrix_world@v.co-target).length)
            point=current.matrix_world@vertex.co;image=projected(point)
            error=math.dist([x,y],image);assert error<.001,error
            correspondences.append(dict(path_id=path['id'],target_index=index,target=[x,y],object=current.name,
                source_node='building-117',vertex_index=vertex.index,world=list(point),projected=image,error_pixels=error))
    checked=[stats(o) for o in working.all_objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==ASSET]
    proof=dict(input_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=asset['source_sha256'],
        correspondences=correspondences,max_error_pixels=max(r['error_pixels'] for r in correspondences),
        front_footprint_changes=modifications,top_world_z=TOP,source_camera_elevation=35,
        long_intervals=long_gaps,short_intervals=short_gaps,
        long_ends_lower=True,short_ends_upper=True,meshes=checked)
    (packet/'user-constraint-fit.json').write_text(json.dumps(proof,indent=2))
    (packet/'geometry.json').write_text(json.dumps(dict(before=before,after=after,changed=changed),indent=2))
    print('EXACT USER FIT '+json.dumps(dict(max_error=proof['max_error_pixels'],corners=len(correspondences),long_openings=len(long_gaps),short_openings=len(short_gaps))),flush=True)
    base=packet.parent/'rear-notch-native108';config=json.loads((base/'workspace.json').read_text())
    repartition(config,packet);_freeze_masks(packet,config);_reproject(config,packet/'projection')
    assert after=={o.name:_geometry(o) for o in working.objects}
    bpy.ops.wm.save_as_mainfile(filepath=str(packet/'model.blend'))
    frame=json.loads((base/'modified/views.json').read_text())
    frame['lighting']['toward_sun']=[-.4916794601,-.4538579920,.7431448255]
    render_review(packet/'modified',scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=ASSET,
        source_path=frame['source_image'],frame_manifest=frame,projection_layers=frame['projection_layers'],
        lighting=frame['lighting'],source_mask_manifest=config['source_mask_manifest'],allow_mask_revision=True)

if __name__=='__main__':main()
