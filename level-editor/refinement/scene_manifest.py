"""Import Blender handoffs into immutable library assets before publication."""
import copy
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location('split_scene_assets', Path(__file__).resolve().parents[1] / 'pipeline/split_scene_assets.py')
_splitter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_splitter)


def import_document(glb, output, document):
    report = _splitter.split(glb, output)
    result = copy.deepcopy(document)
    result.pop('glb', None)
    result.setdefault('provenance', {}).pop('glb_sha256', None)
    result['sceneAssets'] = report['sceneAssets']
    result.setdefault('sourceMap', result.get('map'))
    return result, report


def scene_metadata(library, document):
    if 'glb' in document or 'sceneAssets' not in document:
        raise ValueError('Expected a JSON/assets map; explicitly import older handoffs first')
    nodes = [{'name': 'map', 'children': [], 'extras':copy.deepcopy(document.get('sceneMetadata', {}))}]
    materials = {}
    verified = set()
    from asset_scenes import select_scene
    for asset in document['sceneAssets'] + document.get('assetSources', []):
        model_path = Path(library) / asset['model']
        if _splitter.digest(model_path.read_bytes()) != asset['model_sha256']:
            raise ValueError('Scene asset changed: ' + asset['model'])
        if asset.get('descriptor') and _splitter.digest((Path(library)/asset['descriptor']).read_bytes()) != asset['descriptor_sha256']:
            raise ValueError('Asset descriptor changed: '+asset['id'])
        for resource in asset.get('resources', []):
            key = (resource['path'], resource['sha256'])
            if key in verified:
                continue
            if _splitter.digest((Path(library) / resource['path']).read_bytes()) != resource['sha256']:
                raise ValueError('Scene resource changed: ' + resource['path'])
            verified.add(key)
        if model_path.suffix == '.glb':
            model, _, _ = _splitter.read_glb(model_path, allow_external=True)
        else:
            model = json.loads(model_path.read_text())
        model = select_scene(model, asset.get('model_scene'))
        if asset in document.get('assetSources', []):
            parts = {obj['node'].split(':', 2)[-1]:obj for obj in document['objects'] if obj['node'].startswith('asset:'+asset['id']+':')}
            for node in model['nodes']:
                for part in parts.values():
                    node.setdefault('extras', {}).update(copy.deepcopy(part.get('missionBindings', {}).get(node.get('name'), {})))
            root = model['nodes'][model['scenes'][0]['nodes'][0]]
            for group_index in root.get('children', []):
                group = model['nodes'][group_index]
                group['children'] = [i for i in group.get('children', []) if model['nodes'][i]['name'] in parts]
        offset = len(nodes)
        for node in model.get('nodes', []):
            node = copy.deepcopy(node)
            if 'children' in node:
                node['children'] = [index + offset for index in node['children']]
            nodes.append(node)
        roots = model['scenes'][model.get('scene', 0)].get('nodes', [])
        for index in roots:
            node = nodes[index + offset]
            if node.get('name') == 'map':
                nodes[0]['children'].extend(node.get('children', []))
                nodes[0].setdefault('extras', {}).update(node.get('extras', {}))
            else:
                nodes[0]['children'].append(index + offset)
        for material in model.get('materials', []):
            materials.setdefault(json.dumps(material, sort_keys=True), material)
    return {'nodes': nodes, 'materials': list(materials.values())}


def export_document(gltf, output, map_name, level, *, size=None, camera=None, export_bounds=None):
    """Publish Blender's separate resources directly as a map manifest."""
    output = Path(output)
    model = json.loads(Path(gltf).read_text())
    nodes = model['nodes']
    root = next(node for node in nodes if node.get('name') == 'map')
    groups, objects = [], []
    identity = dict(dx=0, dy=0, dz=0, rot_deg=0)
    for index in root.get('children', []):
        group = nodes[index]
        if group.get('name') == 'ground':
            continue
        group_id = group['extras']['asset_group']
        groups.append(dict(id=group_id, name=group['name'], transform=dict(identity)))
        for part_index in group.get('children', []):
            part = nodes[part_index]; extra = part['extras']; name = part['name']
            source = {'map': map_name}
            if extra.get('scenery') is True:
                # Authored scenery is visual only; the game has no obstacle for it.
                if any(key in extra for key in ('source_obstacle', 'mission_patch_profile', 'obstacle_local_game')):
                    raise ValueError('Scenery part claims game obstacle or mission metadata: ' + name)
                kind = 'scenery'; obstacle = None
            elif 'mission_patch_profile' in extra:
                kind = 'mission'; source['mission_profile'] = extra['mission_patch_profile']
                obstacle = extra['obstacle_local_game']
            else:
                kind = 'terrace' if name.startswith('terrace-') else 'building'
                source['obstacle'] = extra['source_obstacle']
                obstacle = level['sight_obstacles'][source['obstacle']]
                if extra.get('source_components'):
                    source['components'] = extra['source_components']
                    obstacle = extra['obstacle_local_game']
            item = dict(id=name, node=name, name=extra['part_name'], kind=kind, group=group_id,
                        transform=dict(identity), source=source)
            if obstacle is not None:
                item['obstacle'] = obstacle
            if extra.get('default_hidden'):
                item['hidden'] = True
            objects.append(item)
    document = dict(version=1, map=map_name, sourceMap=map_name, size=size,
                    camera=camera or {'kind': 'oblique-orthographic', 'elevation_deg': 35},
                    groups=groups, objects=objects, sceneAssets=[])
    if export_bounds is not None:
        document['exportBounds'] = export_bounds
    from local_map_export import export_local_map
    return export_local_map(gltf, output, document)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Explicitly import an older Blender handoff into a JSON/assets stage')
    parser.add_argument('glb', type=Path)
    parser.add_argument('document', type=Path)
    parser.add_argument('output', type=Path, help='Fresh staging directory; existing evidence is not changed')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    document, report = import_document(args.glb, args.output / 'map-assets', json.loads(args.document.read_text()))
    destination = args.output / (str(document['map']).lower() + '.rhlos-map.json')
    destination.write_text(json.dumps(document, indent=2)+'\n')
    (args.output / 'import-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(destination)
