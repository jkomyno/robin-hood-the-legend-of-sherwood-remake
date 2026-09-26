"""Stage canonical local assets and map placements without touching live files."""
import argparse
import copy
import json
from asset_index import write_asset_index, generate_asset_index
import math
from pathlib import Path
from canonical_assets import AssetBundle, read_model, digest, encoded, localize_positions


def runtime_key(key):
    return key.startswith(('reveal_', 'sight_patch_', 'drawbridge_', 'mission_patch_')) or key in ('native_patch_preview', 'support_floor_scene_z')


def local_states(model):
    """Reusable appearance switches have asset-local names; missions bind instances."""
    model = copy.deepcopy(model)
    triggers = set()
    for node in model.get('nodes', []):
        extra = node.get('extras', {})
        if isinstance(extra.get('reveal_material_patch'), str): triggers.add(extra['reveal_material_patch'])
        for field in ('reveal_hide_when_applied','reveal_show_when_applied'):
            triggers.update(extra.get(field, []))
    names = {value:'appearance-'+str(index+1) for index,value in enumerate(sorted(triggers))}
    reusable = {'reveal_material_patch', 'reveal_material_state', 'reveal_hide_when_applied',
                'reveal_show_when_applied', 'mission_patch_profile'}
    for node in model.get('nodes', []):
        extra = node.get('extras', {})
        for key in list(extra):
            if (runtime_key(key) and key not in reusable) or key == 'reveal': extra.pop(key)
        if 'reveal_material_patch' in extra: extra['reveal_material_patch'] = names[extra['reveal_material_patch']]
        for field in ('reveal_hide_when_applied','reveal_show_when_applied'):
            if field in extra: extra[field] = [names[value] for value in extra[field]]
    return model


def local_descriptor(descriptor):
    descriptor = copy.deepcopy(descriptor)
    for key in ('source_origin_game', 'reveal'): descriptor.pop(key, None)
    for component in descriptor.get('components', []):
        for key in list(component):
            if runtime_key(key): component.pop(key)
    for field in ('state_variants', 'standalone_variants'):
        for variant in descriptor.get(field, {}).values():
            cleaned = local_descriptor(variant)
            variant.clear(); variant.update(cleaned)
    return descriptor


def scenery_origin(sources):
    """Scenery has no footprint: anchor at its horizontal mesh bounds centre, integer like footprints."""
    low, high = [math.inf, math.inf], [-math.inf, -math.inf]
    for model, _, _, child in sources:
        pending = [child]
        while pending:
            node = model['nodes'][pending.pop()]
            pending.extend(node.get('children', []))
            if any(key in node for key in ('matrix', 'translation', 'rotation', 'scale')):
                raise ValueError('Expected baked scenery positions: ' + node.get('name', ''))
            for primitive in model['meshes'][node['mesh']]['primitives'] if 'mesh' in node else []:
                accessor = model['accessors'][primitive['attributes']['POSITION']]
                for axis in range(2):
                    low[axis] = min(low[axis], accessor['min'][axis]); high[axis] = max(high[axis], accessor['max'][axis])
    if not math.isfinite(low[0]):
        raise ValueError('Scenery group has no mesh geometry')
    return [round((low[0] + high[0]) / 2), round((low[1] + high[1]) / 2), 0]


def stage(library, output):
    library, output = Path(library).resolve(), Path(output).resolve()
    if library == output: raise ValueError('Use a separate staging directory')
    output.mkdir(parents=True,exist_ok=True)
    sources = {}
    def read_json(relative):
        data = (library/relative).read_bytes(); sources[relative] = digest(data)
        return json.loads(data)
    if (library/'3d-assets/index.json').exists():
        sources['3d-assets/index.json'] = digest((library/'3d-assets/index.json').read_bytes())
    index = generate_asset_index(library/'3d-assets')
    entries = {entry['id']:copy.deepcopy(entry) for entry in index['assets']}
    descriptors, origins, references, proofs = {}, {}, {}, {}
    from stored_map import expand_document
    documents = [(path, expand_document(library, read_json(str(path.relative_to(library)))))
                 for path in sorted((library/'scenes').glob('*.rhlos-map.json'))]
    for entry in index['assets']:
        identity = entry['id']; relative = '3d-assets/'+entry['descriptor']
        original = read_json(relative)
        origins[identity] = original.get('source_origin_scene',[0,0,0])
        descriptor = local_descriptor(original)
        parent = Path(relative).parent
        bundle = AssetBundle(output)
        variant_field = 'state_variants' if original.get('state_variants') else 'standalone_variants' if original.get('standalone_variants') else None
        primary = 'initial' if variant_field == 'state_variants' else 'default'
        requested = [(primary,original)]
        if variant_field: requested.extend((name,value) for name,value in original[variant_field].items() if name != primary)
        for name, value in requested:
            path = str(parent/value['model']); raw=(library/path).read_bytes();sources[path]=digest(raw)
            model,binary,external = read_model(library/path,library)
            selected = value.get('model_scene')
            model = local_states(model)
            bundle.add(name,model,binary,external,selected)
        reference = bundle.write(identity)
        descriptor.update(model='model.gltf',model_scene=primary,resources=reference['resources'],
                          source_origin_scene=origins[identity])
        if variant_field:
            for name,value in descriptor[variant_field].items(): value.update(model='model.gltf',model_scene=name)
        entry = entries[identity];entry.update(model=str(Path(entry['descriptor']).parent/'model.gltf'),model_scene=primary)
        # Rewritten source bytes require newly derived display models.
        entry.pop('lossy_model', None)
        # Derived GLB previews keep their original encoding and are not canonical geometry.
        descriptors[identity]=descriptor;references[identity]=reference;proofs[identity]=bundle.proofs
        print('catalog '+identity,flush=True)
    maps=[]
    for path, document in documents:
        source_nodes={};part_owners={};ground=[];metadata={};bindings={}
        for reference in document['sceneAssets']:
            sources[reference['model']] = reference['model_sha256']
            for resource in reference['resources']: sources[resource['path']] = resource['sha256']
            model,binary,external = read_model(library/reference['model'],library)
            if reference['role']=='metadata':
                for node in model['nodes']:
                    if node.get('name')=='map':metadata.update(node.get('extras',{}))
                continue
            if reference['role']=='ground':
                identity=document['map'].lower()+'-terrain'
                if identity in entries:raise ValueError('Terrain asset identity collision: '+identity)
                bundle=AssetBundle(output);bundle.add('default',model,binary,external)
                ref=bundle.write(identity);references[identity]=ref;proofs[identity]=bundle.proofs
                descriptor={'version':1,'kind':'projection-mapped-asset','id':identity,'name':document['map']+' terrain','source_map':document['map'],
                            'model':'model.gltf','model_scene':'default','resources':ref['resources'],'editor_usage':'map-background','parts':[],
                            'components':[{'name':'ground','source_node':'ground'}]}
                descriptors[identity]=descriptor;entries[identity]={'id':identity,'name':descriptor['name'],'source_map':document['map'],'descriptor':identity+'/asset.json','model':identity+'/model.gltf','model_scene':'default','editor_usage':'map-background'}
                ground.append({'id':identity,'role':'ground',**ref,'model_scene':'default'})
                continue
            roots=model['scenes'][model.get('scene',0)]['nodes']
            if len(roots)==1 and model['nodes'][roots[0]].get('name')=='map':roots=model['nodes'][roots[0]].get('children',[])
            for root in roots:
                group=model['nodes'][root];identity=group.get('extras',{}).get('asset_group')
                for child in group.get('children',[]):
                    name=model['nodes'][child]['name'];source_nodes[name]=(model,binary,external,child)
                    if identity:part_owners[name]=identity
                    collected={}
                    def visit(i):
                        node=model['nodes'][i]
                        values={k:v for k,v in node.get('extras',{}).items()
                                if k in ('reveal_hide_when_applied', 'reveal_show_when_applied',
                                         'reveal_material_patch', 'reveal_material_state') and v}
                        if values:collected[node['name']]=values
                        for c in node.get('children',[]):visit(c)
                    visit(child)
                    if collected:bindings[name]=collected
        # Existing authored catalog entries are authoritative. Ungrouped reconstructions
        # become normal local assets using the editor's existing logical groups.
        unmatched={}
        for part in document['objects']:
            if part['node'].startswith('asset:') or part_owners.get(part['node']) in entries:continue
            key=part.get('group',part['id'])
            unmatched.setdefault(key,[]).append(part)
        for group_id,parts in unmatched.items():
            identity=part_owners.get(parts[0]['node'], document['map'].lower()+'-'+group_id)
            if identity in entries:raise ValueError('Asset identity collision: '+identity)
            bundle=AssetBundle(output)
            points=[p for part in parts for p in part.get('obstacle',{}).get('points',[])]
            angle=math.radians(document['camera']['elevation_deg'])
            # Integer anchors retain the precision of the stored float32 coordinates.
            if points:
                origin=[round(sum(p['x']for p in points)/len(points)),round(-sum(p['y']for p in points)/len(points)/math.sin(angle)),0]
            else:
                origin=scenery_origin([source_nodes[part['node']] for part in parts])
            game_origin=[origin[0],-origin[1]*math.sin(angle),0];origins[identity]=origin
            descriptor={'version':1,'kind':'projection-mapped-asset','id':identity,'name':next((g.get('name',group_id)for g in document['groups']if g['id']==group_id),group_id),
                        'source_map':document['map'],'source_origin_scene':origin,
                        'model':'model.gltf','model_scene':'default','parts':[]}
            for part in parts:
                if part_owners.get(part['node']) in entries:continue
                model,binary,external,child=source_nodes[part['node']]
                local, local_external = localize_positions(model,binary,external,origin)
                if part['kind']=='scenery':
                    if 'obstacle' in part:raise ValueError('Scenery part claims a game obstacle: '+part['node'])
                    record={'node':part['node'],'name':part.get('name',part['node']),'scenery':True}
                else:
                    obstacle=copy.deepcopy(part['obstacle'])
                    for p in obstacle['points']:
                        p['x']-=game_origin[0];p['y']-=game_origin[1]
                    record={'node':part['node'],'name':part.get('name',part['node']),'obstacle_local_game':obstacle, **({'mission_profile':part['source']['mission_profile']} if part['kind']=='mission' else {'source_obstacle':part['source']['obstacle']})}
                if part['source'].get('components'):record['source_components']=part['source']['components']
                descriptor['parts'].append(record)
                extra=local['nodes'][child].setdefault('extras',{})
                if 'source_obstacle' in record:extra['source_obstacle']=record['source_obstacle']
                if 'obstacle_local_game' in extra:extra['obstacle_local_game']=record['obstacle_local_game']
                group=len(local['nodes']);local['nodes'].append({'name':descriptor['name'],'extras':{'asset_group':identity},'children':[child]})
                root=len(local['nodes']);local['nodes'].append({'name':'map','rotation':[-math.sqrt(.5),0,0,math.sqrt(.5)],'children':[group]})
                local['scenes']=[{'nodes':[root]}];local['scene']=0
                bundle.add(part['node'],local_states(local),binary,local_external)
                part_owners[part['node']]=identity
            # The default scene contains every part once in one reusable asset group.
            roots=[bundle.model['nodes'][s['nodes'][0]] for s in bundle.model['scenes']]
            groups=[bundle.model['nodes'][root['children'][0]]for root in roots]
            groups[0]['children']=[child for group in groups for child in group['children']]
            bundle.model['scenes']=[{'name':'default','nodes':bundle.model['scenes'][0]['nodes']}]
            ref=bundle.write(identity);references[identity]=ref;proofs[identity]=bundle.proofs;descriptor['resources']=ref['resources']
            descriptors[identity]=descriptor;entries[identity]={'id':identity,'name':descriptor['name'],'source_map':document['map'],'descriptor':identity+'/asset.json','model':identity+'/model.gltf','model_scene':'default'}
        maps.append({'file':str(path.relative_to(library)),'document':document,'owners':part_owners,'ground':ground,'metadata':metadata,'bindings':bindings})
        print('map '+document['map'],flush=True)
    for identity,descriptor in descriptors.items():
        path=output/'3d-assets'/entries[identity]['descriptor'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encoded(descriptor))
        references[identity].update(descriptor='3d-assets/'+entries[identity]['descriptor'],descriptor_sha256=digest(path.read_bytes()))
    write_asset_index(output/'3d-assets')
    plan={'library':str(library),'output':str(output),'sources':sources,'maps':maps,'origins':origins,'references':references,'proofs':proofs}
    (output.parent/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    return {'assets':len(descriptors),'maps':len(maps),'verified_scenes':sum(len(v)for v in proofs.values())}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('library',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(stage(a.library,a.output))
