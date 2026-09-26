"""Verify standalone/map coverage and exported ownership/provenance metadata."""
import json
import hashlib
from pathlib import Path
import struct
import sys
from catalog_schema import is_scenery_node, source_for_part
from publication_contract import publication_parts, validate_export_records
from texture_state_roles import partition_texture_states, validate_texture_state_role_evidence
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from asset_scenes import select_scene, scene_identity


def gltf(path):
    if Path(path).suffix == ".gltf": return json.loads(Path(path).read_text())
    with Path(path).open('rb') as handle:
        magic,version,_=struct.unpack('<III',handle.read(12))
        if magic!=0x46546c67 or version!=2:
            raise ValueError('Expected glTF binary v2')
        length,kind=struct.unpack('<II',handle.read(8))
        if kind!=0x4e4f534a:
            raise ValueError('Expected JSON chunk')
        return json.loads(handle.read(length))


# Selectable part nodes: native obstacles, mission-only models and authored scenery.
PART_PREFIXES = ('building-', 'mission-', 'foliage-', 'scenery-')


def verify_scenery_part(node, metadata):
    """Authored scenery stays visual only: no obstacle, footprint or mission profile."""
    if (metadata.get('scenery') is not True or any(metadata.get(key) is not None for key in
            ('source_obstacle', 'obstacle_local_game', 'mission_profile', 'mission_patch_profile'))):
        raise ValueError('Scenery part claims game obstacle or mission metadata: ' + node)


def verify_component_nodes(model, expected):
    """Reject duplicate part identities or meshes escaping their selector parent."""
    nodes=model['nodes']
    named=[node['name'] for node in nodes if 'mesh' not in node and node.get('name','').startswith(PART_PREFIXES)]
    if len(named)!=len(set(named)) or set(named)!=set(expected):
        raise ValueError('GLB selectable part identities overlap or differ from catalog')
    for node in nodes:
        identity=expected.get(node.get('name'))
        if not identity or not identity['source_components']:
            continue
        extra=node.get('extras',{})
        if (extra.get('source_node')!=identity['source_node'] or
                extra.get('source_components')!=identity['source_components'] or
                not extra.get('obstacle_local_game',{}).get('points')):
            raise ValueError('GLB split part lost provenance or scoped collision metadata')
        children=[nodes[index] for index in node.get('children',[])]
        if len(children)!=1 or 'mesh' not in children[0]:
            raise ValueError('Split selector must export exactly one reviewed component mesh')
        child=children[0].get('extras',{})
        if (child.get('source_node')!=identity['source_node'] or
                child.get('projection_component')!=identity['source_components'][0] or
                child.get('editor_part_node')!=node['name']):
            raise ValueError('GLB mesh differs from its exact component owner')


def verify_static_inventory(asset_id, descriptor, models, owned, imports, proof):
    """Bind disjoint endpoint exports to content-verified original workers."""
    primary = next((item for item in imports if item['asset_id'] == asset_id), None)
    isolated = bool(descriptor.get('standalone_variants'))
    if primary is None or (not isolated and primary.get('endpoint_id') != 'initial'):
        raise ValueError('Static endpoints require an approved initial handoff')
    reviewed = {'initial': primary, **{s['endpoint_id']: s for s in primary.get('texture_states', [])
                                     if s.get('endpoint_id')}}
    if isolated:
        validate_texture_state_role_evidence(primary)
        _, reviewed = partition_texture_states(primary)
    variants = descriptor['standalone_variants' if isolated else 'state_variants']
    if set(reviewed) != {'initial', 'applied'} or set(variants) != set(reviewed):
        raise ValueError('Static endpoint inventory differs from reviewed pair')
    if proof.get('status') != 'PASS':
        raise ValueError('Static assets require completed independent content verification')
    union = set()
    for state, variant in variants.items():
        records = [r for r in proof.get('static_variants', []) if r['asset_id'] == asset_id and r['state'] == state]
        if len(records) != 1 or records[0].get('status') != 'PASS':
            raise ValueError('Static endpoint lacks independent reviewed-worker comparison')
        record = records[0]
        if record.get('reviewed_source_blend_sha256') != reviewed[state]['blend_sha256']:
            raise ValueError('Static endpoint proof names a different reviewed worker')
        exact = set(record['reviewed_source_nodes'])
        if not exact or not record.get('reviewed_worker_reexport_matches'):
            raise ValueError('Static endpoint lacks exact reviewed native ownership/export proof')
        components = variant['components']
        if ({c['source_node'] for c in components} != exact or
                {p['node'] for p in variant['parts']} != exact or len(components) != record['meshes']):
            raise ValueError('Static descriptor differs from reviewed endpoint ownership: ' + asset_id + ' ' + state)
        model = models[state]
        canonical = [n['name'] for n in model['nodes'] if 'mesh' not in n and n.get('name', '').startswith(PART_PREFIXES)]
        if len(canonical) != len(exact) or set(canonical) != exact:
            raise ValueError('Static GLB differs from exact reviewed endpoint ownership: ' + asset_id + ' ' + state)
        if len([n for n in model['nodes'] if 'mesh' in n]) != len(components):
            raise ValueError('Static endpoint component count differs')
        forbidden = {'drawbridge_hinge_matrix', 'drawbridge_pose_angles_degrees', 'drawbridge_pose',
                     'drawbridge_patch_id', 'native_patch', 'native_patch_preview',
                     'reveal_hide_when_applied', 'reveal_show_when_applied', 'reveal_material_states',
                     'reveal_material_patch', 'reveal_material_state', 'reveal_patch_ids', 'reveal_component_patch_id'}
        if model.get('animations') or any(forbidden & set(n.get('extras', {})) for n in model['nodes']):
            raise ValueError('Standalone static endpoint carries animation/native-map binding')
        union |= exact
    if isolated:
        if not union <= owned or any(scene_identity(variant) == scene_identity(descriptor) for variant in variants.values()):
            raise ValueError('Isolated appearance escapes canonical ownership or replaces covered default')
        return union
    initial = variants['initial']
    if (scene_identity(descriptor) != scene_identity(initial) or descriptor['parts'] != initial['parts']
            or descriptor['components'] != initial['components']):
        raise ValueError('Primary standalone descriptor is not the isolated reviewed initial endpoint')
    if union != owned:
        raise ValueError('Union of reviewed endpoints differs from canonical catalog ownership')
    return union


def verify(directory,catalog_path):
    directory=Path(directory)
    catalog=json.loads(Path(catalog_path).read_text())
    stage=json.loads((directory/'stage.json').read_text())
    index=json.loads((directory/'assets/index.json').read_text())
    expected={g['id']:g for g in catalog['groups']}
    declared=publication_parts(catalog)
    plan=json.loads(Path(stage['plan']).read_text()) if stage.get('plan') else {}
    proof_path=directory/'handoff-verification.json'
    proof=json.loads(proof_path.read_text()) if proof_path.exists() else {}
    selected=set(plan.get('export_asset_ids',expected))
    ground_ids={item['asset_id'] for item in plan.get('imports',[]) if item.get('source_nodes')==['ground']}
    if selected-set(expected)-ground_ids:raise ValueError('Export subset contains unknown assets')
    if {a['id'] for a in index['assets']}!=selected:
        raise ValueError('Standalone group catalog differs from authored ownership')
    nodes=set();components=0;component_metadata=0;masked_generated=0
    asset_material_coverage=[]
    for asset in index['assets']:
        descriptor=json.loads((directory/'assets'/asset['descriptor']).read_text())
        owned={'ground'} if asset['id'] in ground_ids else {key for key,value in declared.items() if value['asset_id']==asset['id']}
        actual={c.get('editor_part_node',c['source_node']) for c in descriptor['components']}
        if (asset['id'] not in ground_ids and not descriptor.get('state_variants')
                and any(declared[key]['source_components'] for key in owned)):
            bindings=validate_export_records(catalog,[dict(c,asset_group=asset['id']) for c in descriptor['components']], [asset['id']])
            if any(c.get('editor_part_node',c['source_node'])!=bindings[c['name']] for c in descriptor['components']):
                raise ValueError('Descriptor component has an incorrect selectable identity')
            part_nodes=[part['node'] for part in descriptor['parts']]
            if len(part_nodes)!=len(set(part_nodes)) or set(part_nodes)!=owned:
                raise ValueError('Standalone part identities overlap or omit catalog parts')
            for part in descriptor['parts']:
                identity=declared[part['node']]
                if identity['source_components']:
                    if (part.get('source_node')!=identity['source_node'] or
                            part.get('source_components')!=identity['source_components'] or
                            part.get('source_obstacle')!=int(identity['source_node'][9:]) or
                            not part.get('obstacle_local_game',{}).get('points') or
                            not part.get('footprint_basis','').startswith('Reviewed component mesh')):
                        raise ValueError('Split part lost exact provenance or scoped collision metadata')
        for part in descriptor.get('parts', []):
            if is_scenery_node(part['node']):
                verify_scenery_part(part['node'], part)
        if asset['id'] in ground_ids and (descriptor.get('parts')!=[] or descriptor.get('editor_usage')!='map-background' or asset.get('editor_usage')!='map-background'):
            raise ValueError('Ground must declare map-background capability without obstacle parts')
        model=select_scene(gltf(directory/'assets'/asset['model']), descriptor.get('model_scene'))
        if any(declared.get(key,{}).get('source_components') for key in owned):
            verify_component_nodes(model,{key:declared[key] for key in owned})
            model_parts={node.get('name'):node.get('extras',{}) for node in model['nodes']}
            for part in descriptor['parts']:
                if part.get('source_components') and part['obstacle_local_game']!=model_parts[part['node']].get('obstacle_local_game'):
                    raise ValueError('Standalone component collision differs from exported mesh metadata')
        if descriptor.get('state_variants'):
            models={state:select_scene(gltf(directory/'assets'/Path(asset['descriptor']).parent/variant['model']), variant.get('model_scene'))
                    for state,variant in descriptor['state_variants'].items()}
            actual=verify_static_inventory(asset['id'],descriptor,models,owned,plan.get('imports',[]),proof)
            for state,variant in descriptor['state_variants'].items():
                record=next(r for r in proof['static_variants'] if r['asset_id']==asset['id'] and r['state']==state)
                model_path=directory/'assets'/Path(asset['descriptor']).parent/variant['model']
                if (hashlib.sha256(model_path.read_bytes()).hexdigest()!=record['model_sha256'] or
                        variant.get('model_scene') != record.get('model_scene')):
                    raise ValueError('Static endpoint changed after independent content verification')
        if descriptor.get('standalone_variants'):
            alternatives = descriptor['standalone_variants']
            models = {state: select_scene(gltf(directory/'assets'/Path(asset['descriptor']).parent/variant['model']), variant.get('model_scene'))
                      for state, variant in alternatives.items()}
            verify_static_inventory(asset['id'], descriptor, models, owned, plan.get('imports', []), proof)
            for state, variant in alternatives.items():
                record = next(r for r in proof['static_variants'] if r['asset_id'] == asset['id'] and r['state'] == state)
                model_path = directory/'assets'/Path(asset['descriptor']).parent/variant['model']
                if (hashlib.sha256(model_path.read_bytes()).hexdigest() != record['model_sha256'] or
                        variant.get('model_scene') != record.get('model_scene')):
                    raise ValueError('Isolated appearance changed after independent content verification')
        if owned!=actual or nodes & actual:
            raise ValueError('Standalone canonical ownership differs: '+asset['id'])
        nodes |= actual
        materials=model.get('materials',[])
        generated_materials=[m for m in materials if m.get('extras',{}).get('generated_source_sha256')]
        asset_material_coverage.append({'asset_id':asset['id'],'material_count':len(materials),
            'generated_material_count':len(generated_materials),
            'generated_source_sha256':sorted({m['extras']['generated_source_sha256'] for m in generated_materials}),
            'interpretation':'Generated provenance is present; this does not certify that every surface texel is filled.'})
        exported=[n.get('extras',{}) for n in model['nodes']]
        for component in descriptor['components']:
            if component.get('projection_component'):
                component_metadata+=1
                if not any(e.get('projection_component')==component['projection_component'] for e in exported):
                    raise ValueError('Standalone lost component ownership metadata')
        components+=len(descriptor['components'])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scene_manifest import scene_metadata
    document = json.loads(Path(stage['map']['file']).read_text())
    model = scene_metadata(Path(stage['map']['library']), document)
    expected_map=set(declared)
    actual_names=[n['name'] for n in model['nodes'] if 'mesh' not in n and n.get('name','').startswith(PART_PREFIXES)]
    if len(actual_names)!=len(set(actual_names)):
        raise ValueError('Full map contains duplicate selectable identities')
    actual_map=set(actual_names)
    for node in model['nodes']:
        if 'mesh' not in node and is_scenery_node(node.get('name')):
            verify_scenery_part(node['name'], node.get('extras',{}))
    if actual_map!=expected_map:raise ValueError('Full map canonical coverage differs from publication catalog')
    if any(identity['source_components'] for identity in declared.values()):
        verify_component_nodes(model,declared)
    generated={}
    for material in model.get('materials',[]):
        extra=material.get('extras',{})
        if extra.get('generated_source_sha256'):
            generated[extra['generated_source_sha256']]=generated.get(extra['generated_source_sha256'],0)+1
            masked_generated+=bool(extra.get('generated_source_mask_evidence_sha256'))
    for sha,names in stage['generated_materials'].items():
        if generated.get(sha)!=len(names):
            raise ValueError('Map lost selected generated materials: '+sha)
    if component_metadata and not any(n.get('extras',{}).get('projection_component') for n in model['nodes']):
        raise ValueError('Map lost component selectors')
    # Lossy models and previews are optional, but any that an index declares must bind its
    # current model bytes (and previews their lossy model or model).
    from lossy_assets import verify_derivatives
    derivative_problems=[]
    for root in (directory/'map-assets/3d-assets', directory/'assets'):
        if (root/'index.json').exists():
            derivative_problems+=[f'{root.relative_to(directory)}: {problem}' for problem in verify_derivatives(root)]
    if derivative_problems:
        raise ValueError('Stale or broken lossy/preview derivatives: '+'; '.join(derivative_problems[:10]))
    lossy=stage.get('lossy')
    report={'status':'PASS','groups':len(selected),'parts':len(nodes-{'ground'}),'full_map_parts':len(actual_map),'components':components,
            'component_metadata':component_metadata,'generated_materials':generated,
            'masked_generated_materials':masked_generated,
            'groups_with_generated_materials':sum(bool(a['generated_material_count']) for a in asset_material_coverage),
            'asset_material_coverage':asset_material_coverage,
            'lossy':None if lossy is None else {'catalog':lossy['catalog'],'enabled':lossy['lossy'],
                'derived':len(lossy['derived']),'current':len(lossy['current']),'refused':lossy['refused']}}
    (directory/'asset-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    print(json.dumps(verify(*sys.argv[1:])),flush=True)
