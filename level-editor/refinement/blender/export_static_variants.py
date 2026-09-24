"""Export independently reviewed static endpoints at a shared asset pivot."""
import hashlib,json
from pathlib import Path
import bpy
from export_editor import export_asset_library
from group_assets import reconcile_asset_groups
from import_reviewed_geometry import import_asset_geometry
from supplemental_parts import clean_static_metadata


def export_variants(plan, output):
    reports=[]
    for entry in plan.get('static_variants',[]):
        asset_id=entry['asset_id']
        imported=next(i for i in plan['imports'] if i['asset_id']==asset_id)
        if not imported.get('new_mission_part') and not (plan.get('approved_texture_imports') and imported.get('endpoint_id')=='initial'):
            raise ValueError('Static variant requires explicit supplemental or approved endpoint ownership')
        destination=output/'assets'/asset_id
        descriptor_path=destination/'asset.json'
        descriptor=json.loads(descriptor_path.read_text())
        variants={'initial':{'name':entry['initial_name'],'model':descriptor['model']}}
        for state,item in entry['states'].items():
            if state!='applied':raise ValueError('Only explicit initial/applied endpoints are supported')
            source=Path(item['blend_path']).resolve(strict=True)
            if hashlib.sha256(source.read_bytes()).hexdigest()!=item['blend_sha256']:raise ValueError('Static endpoint handoff changed')
            if plan.get('approved_texture_imports'):
                bpy.ops.wm.open_mainfile(filepath=str(source))
                displayed = set(item.get('render_object_names') or item['object_names'])
                for obj in bpy.data.collections[plan['collection_name']].all_objects:
                    if obj.type == 'MESH' and obj.get('asset_group') == asset_id:
                        obj.hide_render = obj.name not in displayed
            else:
                import_asset_geometry(source,asset_id=asset_id,object_names=item['object_names'],
                    source_nodes=imported['source_nodes'],collection_name=plan['collection_name'])
                reconcile_asset_groups(plan['catalog'])
            clean_static_metadata([o for o in bpy.data.collections[plan['collection_name']].all_objects
                if o.type=='MESH' and o.get('asset_group')==asset_id and not o.hide_render])
            variant_output=output/'variant-staging'/asset_id/state
            variant_output.mkdir(parents=True, exist_ok=False)
            bpy.ops.wm.save_as_mainfile(filepath=str(variant_output/'worker.blend'))
            export_asset_library(plan['map_name'],variant_output,plan['hackable_map'],asset_ids=[asset_id],
                standalone_pivots={asset_id:descriptor['source_origin_scene']})
            alternative=json.loads((variant_output/asset_id/'asset.json').read_text())
            (variant_output/asset_id/'model.glb').replace(destination/'model-applied.glb')
            if alternative['source_origin_scene']!=descriptor['source_origin_scene']:raise ValueError('Static endpoint pivot drift')
            variants[state]={'name':item['name'],'model':'model-applied.glb','parts':alternative['parts'],'components':alternative['components']}
            reports.append({'asset_id':asset_id,'state':state,'source_blend':str(source),
                'source_blend_sha256':item['blend_sha256'],'worker':str(variant_output/'worker.blend'),
                'worker_sha256':hashlib.sha256((variant_output/'worker.blend').read_bytes()).hexdigest(),'model':str(destination/'model-applied.glb'),
                'model_sha256':hashlib.sha256((destination/'model-applied.glb').read_bytes()).hexdigest()})
        descriptor['state_variants']=variants
        descriptor['state_usage']='Separate static endpoints; initial is the only map instance. No rigid animation is validated.'
        descriptor_path.write_text(json.dumps(descriptor,indent=2)+'\n')
        # The saved map stays initial-only, and later diagnostics must use it.
        bpy.ops.wm.open_mainfile(filepath=str(output/'worker.blend'))
    return reports
