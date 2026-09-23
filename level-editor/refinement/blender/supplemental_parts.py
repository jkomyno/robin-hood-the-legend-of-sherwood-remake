"""Import explicit mission-only geometry without inventing obstacle-table rows."""
from pathlib import Path
import bpy
from catalog_schema import source_for_part


def clean_static_metadata(objects):
    for obj in objects:
        for key in ('drawbridge_hinge_matrix','drawbridge_pose_angles_degrees','drawbridge_pose'):
            if key in obj:del obj[key]
        obj['drawbridge_export_mode']='static-endpoint'
        obj['drawbridge_rigid_animation_validated']=False


def import_mission_part(item, collection_name):
    collection=bpy.data.collections[collection_name]
    nodes=set(item['source_nodes'])
    if len(nodes)!=1:raise ValueError('Supplemental import must declare one mission part')
    source=next(iter(nodes))
    source_for_part({'node':source,'mission_profile':item['mission_profile']})
    if any(o.get('source_node') in nodes or o.get('asset_group')==item['asset_id'] for o in collection.all_objects):
        raise ValueError('Supplemental part/group already exists')
    names=item['object_names']
    if not names or len(names)!=len(set(names)):raise ValueError('Expected explicit unique component names')
    before=set(bpy.data.objects)
    if any(bpy.data.objects.get(name) is not None for name in names):raise ValueError('Supplemental object name collision')
    kept=set();temporary=bpy.data.collections.new('Supplemental import transforms')
    bpy.context.scene.collection.children.link(temporary)
    try:
        with bpy.data.libraries.load(str(Path(item['blend_path']).resolve(strict=True)),link=False) as (src,dst):
            if set(names)-set(src.objects):raise ValueError('Missing supplemental meshes')
            dst.objects=list(names)
        for obj in set(bpy.data.objects)-before:temporary.objects.link(obj)
        bpy.context.view_layer.update()
        loaded=list(dst.objects)
        if any(o is None or o.type!='MESH' or o.hide_render or o.get('asset_group')!=item['asset_id']
               or o.get('source_node')!=source or o.get('mission_patch_profile')!=item['mission_profile']
               or o.get('source_obstacle') is not None for o in loaded):
            raise ValueError('Supplemental handoff ownership/state mismatch')
        for obj in loaded:
            world=obj.matrix_world.copy();obj.parent=None;obj.matrix_world=world
            collection.objects.link(obj);kept.add(obj)
            if item.get('native_patch_preview'):
                obj['native_patch_preview'] = item['native_patch_preview']
        clean_static_metadata(loaded)
        bpy.context.view_layer.update()
    finally:
        bpy.data.collections.remove(temporary)
        for obj in set(bpy.data.objects)-before-kept:bpy.data.objects.remove(obj,do_unlink=True)
    return {'asset_id':item['asset_id'],'source_blend':str(Path(item['blend_path']).resolve()),
            'visible_components':len(kept),'canonical_parts':sorted(nodes),'supplemental_mission_part':True,
            'mission_profile':item['mission_profile'],'static_endpoints_only':True}
