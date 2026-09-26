"""Scope asset validation to an explicitly selected glTF scene."""
import copy


def scene_identity(record):
    scene = record.get('model_scene')
    if scene is not None and (not isinstance(scene, str) or not scene.strip()):
        raise ValueError('model_scene must be a nonempty scene name')
    return record['model'], scene


def select_scene(model, scene=None):
    """Keep reachable nodes only, preserving shared resource indices."""
    scenes = model.get('scenes')
    if not scenes:
        if scene is not None:
            raise ValueError('Explicit model scene is missing')
        return model
    if scene is None:
        index = model.get('scene', 0)
    else:
        matches = [i for i, value in enumerate(scenes) if value.get('name') == scene]
        if len(matches) != 1:
            raise ValueError('Model scene name is missing or ambiguous')
        index = matches[0]
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(scenes):
        raise ValueError('Model scene is outside the GLB scene inventory')
    nodes = model.get('nodes', [])
    reachable, visiting = set(), set()

    def visit(i):
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(nodes):
            raise ValueError('Invalid scene node index')
        if i in visiting:
            raise ValueError('Cyclic scene hierarchy')
        if i in reachable:
            return
        visiting.add(i)
        for child in nodes[i].get('children', []):
            visit(child)
        visiting.remove(i)
        reachable.add(i)

    for root in scenes[index].get('nodes', []):
        visit(root)
    remap = {old: new for new, old in enumerate(sorted(reachable))}
    result = copy.deepcopy(model)
    result['nodes'] = [copy.deepcopy(nodes[i]) for i in sorted(reachable)]
    for node in result['nodes']:
        if 'children' in node:
            node['children'] = [remap[i] for i in node['children']]
    result['scenes'] = [{**scenes[index], 'nodes': [remap[i] for i in scenes[index].get('nodes', [])]}]
    result['scene'] = 0
    used_meshes = sorted({node['mesh'] for node in result['nodes'] if 'mesh' in node})
    mesh_map = {old: new for new, old in enumerate(used_meshes)}
    result['meshes'] = [copy.deepcopy(model['meshes'][i]) for i in used_meshes]
    for node in result['nodes']:
        if 'mesh' in node:
            node['mesh'] = mesh_map[node['mesh']]
    used_materials = sorted({primitive['material'] for mesh in result['meshes']
                             for primitive in mesh.get('primitives', []) if 'material' in primitive})
    material_map = {old: new for new, old in enumerate(used_materials)}
    result['materials'] = [copy.deepcopy(model['materials'][i]) for i in used_materials]
    for mesh in result['meshes']:
        for primitive in mesh.get('primitives', []):
            if 'material' in primitive:
                primitive['material'] = material_map[primitive['material']]
    result['animations'] = [animation for animation in model.get('animations', [])
                            if not animation.get('channels') or any(
                                channel.get('target', {}).get('node') in reachable
                                for channel in animation['channels'])]
    return result
