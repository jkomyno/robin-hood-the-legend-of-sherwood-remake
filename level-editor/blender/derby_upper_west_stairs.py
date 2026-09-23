"""Fit the access stair's nosings to observed artwork, retaining approved walls.

Run on user-corners-v1-contact/model.blend with destination packet after --.
The bottom two obscured endpoints are continuity assumptions, not observed art.
"""
import sys, json, math, hashlib, shutil
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(Path(__file__).parent)]
import bpy,bmesh
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw
from refinement_workspace import _geometry, _freeze_masks, _reproject
from refinement_review import render_review,_tree
from derby_upper_west_user_corners import stats

S,C=math.sin(math.radians(35)),math.cos(math.radians(35))
NEAR=[(225,1176),(228,1162),(231,1148),(234,1134),(237,1120),(240,1106),(243,1092),(246,1078),(249,1064),(252,1050),(255,1037),(258,1024),(261,1010)]
FAR=[(259,1183),(262,1169),(265,1155),(268,1141),(271,1127),(274,1113),(277,1099),(280,1085),(283,1071),(286,1057),(290,1043),(293,1030),(296,1016)]
def project(v):return [v.x,-v.y*S-v.z*C]
def trim_landing(stair,landing):
    vertices=[]
    for offset in (0,28):
        profile=[stair.matrix_world@stair.data.vertices[i].co for i in range(offset+1,offset+27)]
        # Put the carved receiver just below the stair, avoiding two coplanar
        # ownership receivers and the resulting salt-and-pepper projection.
        for point in profile:
            point.z-=.03
            point.y+=.1
        profile += [Vector((profile[-1].x,profile[-1].y,220)),Vector((profile[0].x,profile[0].y,220))]
        vertices.extend(profile)
    n=len(vertices)//2
    faces=[tuple(range(n)),tuple(range(n,2*n))[::-1]]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new('Access stair landing contact cutter');mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    cutter=bpy.data.objects.new('Access stair landing contact cutter',mesh);bpy.context.collection.objects.link(cutter)
    bpy.context.view_layer.objects.active=landing;modifier=landing.modifiers.new('Expose corrected access treads','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name);bpy.data.objects.remove(cutter,do_unlink=True)
    return stats(landing)
def repartition(config,packet):
    src=Path(config['source_mask_manifest']);manifest=json.loads(src.read_text());ip=(src.parent/manifest['mask_inventory']).resolve();inventory=json.loads(ip.read_text());records={r['index']:r for r in inventory['masks']}
    old={i:np.array(Image.open(ip.parent/records[i]['png']).convert('L')) for i in (114,128)};new={i:a.copy() for i,a in old.items()};union=np.maximum(old[114],old[128]);ox,oy=records[114]['box_top_left'];assert records[128]['box_top_left']==[ox,oy]
    tree,owners,_=_tree([o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render]);toward=Vector((0,-C,S));transfers=[]
    for row,col in np.argwhere(union>0):
        x,y=int(col+ox),int(row+oy);p=Vector((x+.5,-(y+.5)/S,0));h,n,index,distance=tree.ray_cast(p+toward*10000,-toward,20000)
        if index is None:continue
        node=owners[index].get('source_node')
        if node not in ('building-114','building-128'):continue
        owner=int(node[-3:]);other=242-owner
        if new[other][row,col]>0:
            new[owner][row,col]=union[row,col];new[other][row,col]=0;transfers.append(dict(pixel=[x,y],from_node=other,to_node=owner))
    assert np.array_equal(union,np.maximum(new[114],new[128]));directory=packet/'source-authority';directory.mkdir()
    for record in inventory['masks']:
        i=record['index']
        if i in new:
            file=directory/f'{i}.png';Image.fromarray(new[i]).save(file);record['png']=str(file)
        else:record['png']=str((ip.parent/record['png']).resolve())
    (directory/'manifest.json').write_text(json.dumps(inventory,indent=2));manifest['mask_inventory']=str(directory/'manifest.json');path=packet/'source-masks.json';path.write_text(json.dumps(manifest,indent=2));config['source_mask_manifest']=str(path)
    (packet/'source-mask-transfer.json').write_text(json.dumps(dict(union_identical=True,added_authority_pixels=0,transfers=transfers,rule='Existing114/128 union repartitioned to nearest saved scene receiver'),indent=2))
def main():
    packet=Path(sys.argv[sys.argv.index('--')+1]).resolve();packet.mkdir(exist_ok=True)
    base=Path(bpy.data.filepath).parent;root=base.parent.parent
    working=bpy.data.collections['Derby Working'];before={o.name:_geometry(o) for o in working.objects}
    obj=next(o for o in working.objects if o.get('source_node')=='building-114')
    old=[obj.matrix_world@v.co for v in obj.data.vertices];inverse=obj.matrix_world.inverted();rows=[]
    # Preserve each height, moving each vertical riser as a unit. The upper
    # back contact gets the same footprint offset as the last riser.
    for offset,targets in ((0,NEAR),(28,FAR)):
        for step,(x,y) in enumerate(targets):
            nose=offset+2*step+1;p=old[nose];target=Vector((x,-(y+p.z*C)/S,p.z))
            delta=target-p
            for index in (nose-1,nose):obj.data.vertices[index].co=inverse@(old[index]+delta)
            rows.append(dict(step=step+1,side='near' if offset==0 else 'far',vertex_index=nose,
                target=[x,y],old_projected=project(p),old_error_pixels=math.dist(project(p),(x,y)),
                confidence='occluded continuation' if step<2 or (offset==0 and step==2) else 'visible edge; approximately 1–2 pixel uncertainty'))
        for index in (offset+26,offset+27):obj.data.vertices[index].co=inverse@(old[index]+delta)
    obj.data.update();bpy.context.view_layer.update()
    for row in rows:
        v=obj.matrix_world@obj.data.vertices[row['vertex_index']].co
        row.update(world=list(v),projected=project(v),error_pixels=math.dist(project(v),row['target']))
        assert row['error_pixels']<.001
    landing=next(o for o in working.objects if o.get('source_node')=='building-128');trim_landing(obj,landing)
    after={o.name:_geometry(o) for o in working.objects};changed=[n for n in before if before[n]!=after[n]]
    assert set(changed)=={obj.name,landing.name},changed
    meshes=[stats(o) for o in working.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')=='derby-upper-west-curtain']
    (packet/'geometry.json').write_text(json.dumps(dict(before=before,after=after,changed=changed),indent=2))
    (packet/'stair-fit.json').write_text(json.dumps(dict(base_model=str(base/'model.blend'),correspondences=rows,meshes=meshes,
        height_changes=0,risers=13,top_contact_delta_world=list(delta),authority='Manually inspected source artwork; no change to approved battlement user constraints'),indent=2))
    for name in ('user-corners.json','user-constraint-fit.json') :shutil.copyfile(base/name,packet/name)
    config=json.loads((root/'candidates/rear-notch-native108/workspace.json').read_text())
    config['source_mask_manifest']=str(base/'source-masks.json');repartition(config,packet)
    _freeze_masks(packet,config);_reproject(config,packet/'projection')
    assert after=={o.name:_geometry(o) for o in working.objects}
    bpy.ops.wm.save_as_mainfile(filepath=str(packet/'model.blend'))
    frame=json.loads((base/'modified/views.json').read_text())
    render_review(packet/'modified',scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id='derby-upper-west-curtain',
        source_path=frame['source_image'],frame_manifest=frame,projection_layers=frame['projection_layers'],lighting=frame['lighting'],source_mask_manifest=config['source_mask_manifest'],allow_mask_revision=True)
    source=Image.open(frame['source_image']).convert('RGB');box=(210,995,310,1190);scale=5
    raw=source.crop(box).resize((500,975),Image.Resampling.NEAREST);oldim=raw.copy();newim=raw.copy()
    for im,key in ((oldim,'old_projected'),(newim,'projected')):
        d=ImageDraw.Draw(im)
        for step in range(13):
            ends=[next(r for r in rows if r['step']==step+1 and r['side']==side) for side in ('near','far')]
            pts=[((r[key][0]-box[0])*scale,(r[key][1]-box[1])*scale) for r in ends]
            d.line(pts,fill='#ff3939',width=1);d.text((pts[1][0]+3,pts[1][1]-8),str(step+1),fill='#ffff22')
    panel=Image.new('RGB',(1500,1000),'#202020');d=ImageDraw.Draw(panel)
    for i,(im,label) in enumerate(((raw,'Original artwork'),(oldim,'Previous saved nosings'),(newim,'Corrected saved nosings / numbered bottom-up'))):panel.paste(im,(i*500,25));d.text((i*500+5,6),label,fill='white')
    panel.save(packet/'modified/stair-nosing-comparison.png')
    print('STAIR FIT',json.dumps(rows),flush=True)
if __name__=='__main__':main()
