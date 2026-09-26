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
            if state not in ('initial','applied'):raise ValueError('Only explicit initial/applied endpoints are supported')
            source=Path(item['blend_path']).resolve(strict=True)
            if hashlib.sha256(source.read_bytes()).hexdigest()!=item['blend_sha256']:raise ValueError('Static endpoint handoff changed')
            if plan.get('approved_texture_imports'):
                bpy.ops.wm.open_mainfile(filepath=str(source))
                displayed = set(item.get('render_object_names') or item['object_names'])
                for obj in list(bpy.data.collections[plan['collection_name']].all_objects):
                    if obj.type == 'MESH' and obj.get('asset_group') == asset_id:
                        obj.hide_render = obj.name not in displayed
            else:
                import_asset_geometry(source,asset_id=asset_id,object_names=item['object_names'],
                    source_nodes=imported['source_nodes'],collection_name=plan['collection_name'])
                reconcile_asset_groups(plan['catalog'])
            active=[o for o in bpy.data.collections[plan['collection_name']].all_objects
                if o.type=='MESH' and o.get('asset_group')==asset_id and not o.hide_render]
            clean_static_metadata(active)
            for obj in active:
                for key in ('native_patch', 'native_patch_preview', 'drawbridge_patch_id',
                            'reveal_hide_when_applied', 'reveal_show_when_applied'):
                    if key in obj:
                        del obj[key]
            variant_output=output/'variant-staging'/asset_id/state
            variant_output.mkdir(parents=True, exist_ok=False)
            bpy.ops.wm.save_as_mainfile(filepath=str(variant_output/'worker.blend'))
            export_asset_library(plan['map_name'],variant_output,plan['hackable_map'],asset_ids=[asset_id],
                standalone_pivots={asset_id:descriptor['source_origin_scene']})
            alternative=json.loads((variant_output/asset_id/'asset.json').read_text())
            model_name='model.glb' if state=='initial' else 'model-applied.glb'
            (variant_output/asset_id/'model.glb').replace(destination/model_name)
            if alternative['source_origin_scene']!=descriptor['source_origin_scene']:raise ValueError('Static endpoint pivot drift')
            if state=='initial':
                descriptor=alternative
            variants[state]={'name':item['name'],'model':model_name,'parts':alternative['parts'],'components':alternative['components']}
            reports.append({'asset_id':asset_id,'state':state,'source_blend':str(source),
                'source_blend_sha256':item['blend_sha256'],'worker':str(variant_output/'worker.blend'),
                'worker_sha256':hashlib.sha256((variant_output/'worker.blend').read_bytes()).hexdigest(),'model':str(destination/model_name),
                'model_sha256':hashlib.sha256((destination/model_name).read_bytes()).hexdigest()})
        descriptor['state_variants']=variants
        descriptor['state_usage']=('Both reviewed endpoints are present in the map under their canonical parts; patch state selects the visible endpoint. The applied endpoint is also available as a separate static model. No rigid animation is validated.' if plan.get('approved_texture_imports') else 'Separate static endpoints; initial is the only map instance. No rigid animation is validated.')
        descriptor_path.write_text(json.dumps(descriptor,indent=2)+'\n')
        # Restore the staged map after exporting the independent endpoint worker.
        bpy.ops.wm.open_mainfile(filepath=str(output/'worker.blend'))
    from export_appearance_variants import export_appearance_variants
    reports.extend(export_appearance_variants(plan, output))
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bundle_publication_states import bundle_exported_variants
    return bundle_exported_variants(output, reports)
