"""Recover the native concealed courtyard support without duplicating its neighboring stair.

The map's elevation boundaries identify221 as the connected stair to ground.
352 is a constant-height collision support behind the courtyard wall. This
helper restores its archived mesh exactly; it never suppresses its display.
"""
import hashlib,json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def restore_support(source_blend, target_collection, destination_asset, destination_name):
    import bpy
    source_blend=Path(source_blend).resolve()
    objects=list(bpy.data.collections[target_collection].all_objects)
    targets=[o for o in objects if o.type=='MESH' and o.get('source_node')=='building-352']
    assert len(targets)==1, [o.name for o in targets]
    target=targets[0]
    with bpy.data.libraries.load(str(source_blend),link=False) as (source,destination):
        names=[n for n in source.objects if n=='Castle courtyard southwestern stair / Structural volume 352']
        assert len(names)==1,names
        destination.objects=names
    archived=destination.objects[0]
    assert archived.get('source_node')=='building-352'
    expected=[list(archived.matrix_world@v.co) for v in archived.data.vertices]
    faces=[list(p.vertices) for p in archived.data.polygons]
    target.data=archived.data.copy()
    target.matrix_world=archived.matrix_world.copy()
    target['asset_group']=destination_asset
    target['asset_name']=destination_name
    target['part_name']='Hidden courtyard support volume'
    target['source_node']='building-352'
    target['source_obstacle']='building-352'
    assert not target.hide_render, 'Source-hidden support must remain display-enabled'
    bpy.data.objects.remove(archived,do_unlink=True)
    bpy.context.view_layer.update()
    actual=[list(target.matrix_world@v.co) for v in target.data.vertices]
    assert expected==actual
    assert faces==[list(p.vertices) for p in target.data.polygons]
    return dict(status='PASS',source_blend=str(source_blend),source_blend_sha256=digest(source_blend),source_node='building-352',target_object=target.name,vertices=len(actual),faces=len(faces),world_vertices_sha256=hashlib.sha256(json.dumps(actual).encode()).hexdigest(),original_world_vertices_exact=True,original_faces_exact=True,display_enabled=not target.hide_render,asset_group=destination_asset,reason='Restore original constant-height support; approved221 already supplies the complete stair to the ground.')
