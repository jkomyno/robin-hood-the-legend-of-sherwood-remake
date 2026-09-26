"""Component-level workspace authority derived from immutable reviewed catalogs."""
import hashlib
import json
from pathlib import Path
from catalog_schema import parse_catalog, source_for_part


def scope_for(index, asset_id):
    return {'version': 1, 'split_sources': sorted(index.split_sources),
            'owned_components': [{'source_node': source, 'projection_component': component}
                                 for (source, component), (group, _) in sorted(index.component_owners.items())
                                 if group['id'] == asset_id],
            'canonical_originals': sorted(source for source in index.split_sources
                                         if index.canonical_owners[source] == asset_id)}


def validated_scope(config, objects=None):
    """Never trust mutable workspace component authority without its catalog."""
    if not config.get('source_path'):
        return None  # prepare() has not yet installed its immutable reference.
    path = Path(config['source_path']).parent / 'grouping.json'
    if not path.exists():
        if config.get('component_ownership'):
            raise ValueError('Component workspace requires immutable grouping reference')
        return None
    catalog = json.loads(path.read_text())
    if catalog.get('version') != 2:
        if config.get('component_ownership'):
            raise ValueError('Component scope requires a version2 catalog')
        return None
    if hashlib.sha256(path.read_bytes()).hexdigest() != config['grouping_manifest_sha256']:
        raise ValueError('Component grouping reference changed')
    index = parse_catalog(catalog)
    scope = scope_for(index, config['asset_id'])
    if scope != config.get('component_ownership'):
        raise ValueError('Workspace component ownership differs from reviewed catalog')
    expected = sorted(source_for_part(part) for part in index.groups[config['asset_id']]['parts'])
    if config.get('part_ids') != expected:
        raise ValueError('Component workspace source parts differ from reviewed catalog')
    if objects is not None:
        meshes = [obj for obj in objects if obj.type == 'MESH' and obj.get('source_node') != 'ground']
        index.validate_meshes([{'source_node': obj.get('source_node'),
                               'projection_component': obj.get('projection_component'),
                               'hide_render': obj.hide_render} for obj in meshes])
        for obj in meshes:
            group, _ = index.owner_for(obj.get('source_node'), obj.get('projection_component'))
            if obj.get('asset_group') != group['id']:
                raise ValueError('Mesh component moved outside its reviewed owner: '+obj.name)
    return scope


def owns_assignment(config, target_kind, target, component=None):
    if target_kind == 'asset_group':
        return target == config['asset_id']
    if target not in config['part_ids']:
        return False
    scope = validated_scope(config)
    if scope is None or target not in scope['split_sources']:
        return True
    # Canonical-wide masks affect neighboring assets even when this workspace
    # retains the hidden canonical original. Only explicit own components edit.
    return {'source_node': target, 'projection_component': component} in scope['owned_components']


def appearance_state(obj, cache=None):
    """Capture foreign UVs/material bindings without affecting legacy hashes."""
    if obj.type != 'MESH':
        return None
    def scalar(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        try:
            return list(value)
        except TypeError:
            return str(value)
    cache = {} if cache is None else cache
    materials = []
    for material in obj.data.materials:
        if material is None:
            materials.append(None)
            continue
        cache_key = ('material', material.as_pointer())
        if cache_key in cache:
            materials.append(cache[cache_key])
            continue
        record = {'name': material.name, 'use_nodes': material.use_nodes,
                  'diffuse_color': list(material.diffuse_color)}
        if material.use_nodes and material.node_tree:
            nodes = []
            for node in material.node_tree.nodes:
                item = {'name': node.name, 'type': node.bl_idname,
                        'inputs': [(socket.identifier, scalar(socket.default_value))
                                   for socket in node.inputs if hasattr(socket, 'default_value')]}
                for key in ('blend_type', 'operation', 'interpolation', 'extension', 'projection', 'uv_map'):
                    if hasattr(node, key):
                        item[key] = scalar(getattr(node, key))
                image = getattr(node, 'image', None)
                if image is not None:
                    packed = getattr(image, 'packed_file', None)
                    item['image'] = {'name': image.name, 'filepath': image.filepath,
                                     'size': list(image.size), 'dirty': image.is_dirty,
                                     'packed_sha256': hashlib.sha256(packed.data).hexdigest() if packed else None}
                nodes.append(item)
            record['nodes'] = sorted(nodes, key=lambda node: node['name'])
            record['links'] = sorted((link.from_node.name, link.from_socket.identifier,
                                      link.to_node.name, link.to_socket.identifier)
                                     for link in material.node_tree.links)
        cache[cache_key] = record
        materials.append(record)
    return {'uv_layers': [(layer.name, [list(loop.uv) for loop in layer.data]) for layer in obj.data.uv_layers],
            'active_uv': obj.data.uv_layers.active_index,
            'face_materials': [face.material_index for face in obj.data.polygons], 'materials': materials}
