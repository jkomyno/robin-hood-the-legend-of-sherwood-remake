"""Independent upper and lower west tower cutaways from native patch states."""
import math
import bpy
from towers import horizontal_shell,split_mesh,write_mesh,diagnostics


def refine_shells(collection, asset_id, manifest):
    objects={o.get('source_node'):o for o in collection.all_objects if o.get('asset_group')==asset_id}
    obj=objects['building-249'];world,faces=horizontal_shell(obj)
    middle=120/math.cos(math.radians(35));pieces=[]
    for upper,patch in [(True,'patch-013'),(False,'patch-014')]:
        level=split_mesh(world,faces,2,middle,upper)
        for retained in [True,False]:
            pieces.append((patch,retained,split_mesh(*level,1,-1847,retained)))
    report=[]
    for i,(patch,retained,piece) in enumerate(pieces):
        target=obj if i==0 else obj.copy()
        if i:collection.objects.link(target)
        name=('upper' if patch=='patch-013' else 'lower')+('-retained' if retained else '-cover')
        target.name='West Moat Tower / component 249 '+name
        write_mesh(target,*piece,target.name)
        component='tower-'+name
        target['projection_component']=component;target['reveal_component_patch_id']=patch
        target['reveal_component_role']='retained-shell' if retained else 'removable-cover'
        target['tower_recipe']='leicester-tower-shells-v1'
        r=manifest['projection_reviews'][patch]
        if 'building-249' not in r['receiver_nodes']:r['receiver_nodes'].append('building-249')
        selector={'source_node':'building-249','projection_component':component,'patch_id':patch}
        role='interior-'+patch if retained else 'exterior'
        r['receiver_components'].setdefault(role,[]).append({'source_node':'building-249','projection_components':[component],'patch_id':patch})
        if not retained:
            r['exclude_occluder_components'].append(selector)
            r['render_visibility']['revealed']['hidden_components'].append(selector)
        report.append(dict(object=target.name,patch=patch,retained=retained,mesh=diagnostics(target)))
    for n,patch in [(277,'patch-013'),(278,'patch-014')]:
        node=f'building-{n:03}';r=manifest['projection_reviews'][patch]
        r['render_visibility']['revealed']['hidden_nodes'].append(node)
        r['exclude_occluder_components'].append({'source_node':node,'projection_component':'native-state-cover','patch_id':patch})
        r['evidence']+=f'; Native old_sight_obstacles removes{n} when {patch} applies; its entire old proxy is hidden in that revealed state.'
        objects[node]['reveal_component_patch_id']=patch
        objects[node]['projection_component']='native-state-cover'
        objects[node]['reveal_component_role']='removable-cover'
    lower=manifest['projection_reviews']['patch-014']
    lower['geometry_ready']=True;lower['state_visibility_review']['cutaway_complete']=True
    lower['render_visibility']['limitations']=['Stone body249 split into independent upper/lower front covers at measured middle floor. Hidden cut depth remains a review hypothesis.']
    return report
