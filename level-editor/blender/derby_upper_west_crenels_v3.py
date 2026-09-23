"""Rebuild Upper West crenels against reviewed source opening positions."""
import sys,json,math,hashlib
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(Path(__file__).parent)]
import bpy
from derby_asset_lower_west_curtain import _wall
from refinement_workspace import _geometry, _reproject, _freeze_masks
from refinement_review import render_review,_tree
from mathutils import Vector
from PIL import Image

LOWER=[(177,184),(197,203.5),(217,224),(237,243.5),(256.5,264),
 (277,283),(296.5,303.5),(316.5,323),(337,343.5),(356.5,364),
 (376.5,383.5),(396.5,404),(416,422)]
UPPER=[(184.5,189),(195.5,200),(207.5,212),(219,224),(231,236)]

def transfer_terminal_authority(config, packet):
    """Repartition existing native-derived asset pixels, never enlarge authority."""
    source=Path(config['source_mask_manifest'])
    masks=json.loads(source.read_text())
    inventory_path=(source.parent/masks['mask_inventory']).resolve()
    inventory=json.loads(inventory_path.read_text())
    records={r['index']:r for r in inventory['masks']}
    old={i:Image.open(inventory_path.parent/records[i]['png']).convert('L') for i in (116,117)}
    updated={i:old[i].copy() for i in old}
    assert records[116]['box_top_left']==records[117]['box_top_left']
    ox,oy=records[116]['box_top_left']
    objects=[o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render]
    tree,owners,_=_tree(objects)
    angle=math.radians(35);direction=Vector((0,-math.cos(angle),math.sin(angle)))
    changed=[]
    for y in range(1360,1450):
        for x in range(414,446):
            pixel=x-ox,y-oy
            value=old[116].getpixel(pixel)
            if not value:continue
            p=Vector((x+.5,-(y+.5)/math.sin(angle),0))
            hit,norm,index,distance=tree.ray_cast(p+direction*10000,-direction,20000)
            if index is not None and owners[index].get('source_node')=='building-117':
                updated[116].putpixel(pixel,0)
                updated[117].putpixel(pixel,max(value,old[117].getpixel(pixel)))
                changed.append([x,y])
    assert changed,'No terminal authority pixels transferred'
    import numpy as np
    assert np.array_equal(np.maximum(np.array(old[116]),np.array(old[117])),
                          np.maximum(np.array(updated[116]),np.array(updated[117])))
    directory=packet/'source-authority';directory.mkdir()
    for record in inventory['masks']:
        index=record['index']
        if index in updated:
            path=directory/f'{index}.png';updated[index].save(path);record['png']=str(path)
        else:record['png']=str((inventory_path.parent/record['png']).resolve())
    (directory/'manifest.json').write_text(json.dumps(inventory,indent=2))
    masks['mask_inventory']=str(directory/'manifest.json')
    path=packet/'source-masks.json';path.write_text(json.dumps(masks,indent=2))
    (packet/'source-mask-transfer.json').write_text(json.dumps(dict(
        source_manifest=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        rule='Transfer existing116pixels only where new117is nearest source-view hit',
        added_authority_pixels=0,union_identical=True,transferred_pixels=changed),indent=2))
    config['source_mask_manifest']=str(path)

def main():
    packet=Path(sys.argv[sys.argv.index('--')+1]).resolve()
    packet.mkdir(exist_ok=True)
    base=packet.parent/'rear-notch-native108'
    objects=bpy.data.collections['Derby Working'].objects
    before={o.name:_geometry(o) for o in objects}
    source=next(o for o in objects if o.type=='MESH' and o.get('source_node')=='building-117' and o.hide_render)
    current=next(o for o in objects if o.type=='MESH' and o.get('source_node')=='building-117' and not o.hide_render)
    cuts=[(68,69,0,LOWER),(76,75,0,UPPER),(77,76,0,((146,158),)),
        (81,77,0,((111,122),)),(82,81,1,((1040,1049),)),
        (82,78,0,((101,110),)),(78,68,0,((132,147),))]
    original_data=source.data
    source.data=original_data.copy()
    inverse=source.matrix_world.inverted()
    a=source.matrix_world@source.data.vertices[68].co
    b=source.matrix_world@source.data.vertices[69].co
    endpoint=a.lerp(b,(431.0-a.x)/(b.x-a.x))
    c=source.matrix_world@source.data.vertices[71].co
    d=source.matrix_world@source.data.vertices[70].co
    back_endpoint=c.lerp(d,(endpoint.y-c.y)/(d.y-c.y))
    source.data.vertices[69].co=inverse@endpoint
    source.data.vertices[70].co=inverse@back_endpoint
    try:
        result=_wall(source,cuts,notch_depth=26,allow_corner_cuts=True)
    finally:
        temporary=source.data
        source.data=original_data
        bpy.data.meshes.remove(temporary)
    rebuilt=bpy.data.objects[result['object']]
    # The lower run's painted recess is much shallower than the upper walk.
    # Retain full wall masonry; only opening floors in the long run rise.
    for v in rebuilt.data.vertices:
        if abs(v.co.z-153.5)<.02 and v.co.x>170 and v.co.y < -2160:
            v.co.z=170.0
    current.data=rebuilt.data.copy()
    current['crenellation_notches']=sum(len(c[3]) for c in cuts)
    current['upper_west_crenels_revision']='source-openings-v6'
    bpy.data.objects.remove(rebuilt,do_unlink=True)
    bpy.context.view_layer.update()
    after={o.name:_geometry(o) for o in objects}
    changed=[n for n in before if before[n]!=after[n]]
    assert changed==[current.name],changed
    config=json.loads((base/'workspace.json').read_text())
    transfer_terminal_authority(config,packet)
    _freeze_masks(packet,config)
    _reproject(config,packet/'projection')
    bpy.ops.wm.save_as_mainfile(filepath=str(packet/'model.blend'))
    frame=json.loads((base/'modified/views.json').read_text())
    frame['lighting']['toward_sun']=[-.4916794601,-.4538579920,.7431448255]
    render_review(packet/'modified',scene_name=config['scene_name'],collection_name=config['collection_name'],
        asset_id=config['asset_id'],source_path=frame['source_image'],frame_manifest=frame,
        projection_layers=frame['projection_layers'],lighting=frame['lighting'],source_mask_manifest=config['source_mask_manifest'],allow_mask_revision=True)
    (packet/'geometry.json').write_text(json.dumps(dict(changed=changed,before=before,after=after,
        lower_intervals=LOWER,upper_intervals=UPPER,lower_notch_depth=9.5),indent=2))

if __name__=='__main__':main()
