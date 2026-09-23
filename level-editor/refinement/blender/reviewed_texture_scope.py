"""Strict optional layer and display-state scopes for approved texture packets."""
import hashlib,json
from pathlib import Path

def selected_layers(manifest):
    layers=manifest['projection_layers'];labels=manifest.get('texture_projection_labels')
    if labels is None:return layers
    if (not isinstance(labels,list) or not labels or any(not isinstance(x,str) or not x for x in labels)
            or len(set(labels))!=len(labels)):
        raise ValueError('Texture projection labels must be unique nonempty names')
    if set(labels)-{layer['projection_label'] for layer in layers}:
        raise ValueError('Texture projection label is absent from approved layers')
    return [layer for layer in layers if layer['projection_label'] in labels]

def displayed_objects(manifest,objects):
    names=manifest.get('render_object_names')
    if names is None:return objects
    if (not isinstance(names,list) or not names or any(not isinstance(x,str) or not x for x in names)
            or len(set(names))!=len(names)):
        raise ValueError('Reviewed display names must be unique nonempty names')
    reviewed=Path(manifest['reviewed_packet'])/'views.json'
    if hashlib.sha256(reviewed.read_bytes()).hexdigest()!=manifest.get('reviewed_manifest_sha256'):
        raise ValueError('Reviewed display-state frame changed')
    original=json.loads(reviewed.read_text())
    if original.get('asset_id')!=manifest['asset_id'] or original.get('render_object_names')!=names:
        raise ValueError('Display selection differs from approved state')
    available={obj.name:obj for obj in objects}
    if set(names)-set(available):raise ValueError('Display names include absent, hidden or foreign asset meshes')
    return [obj for obj in objects if obj.name in names]

def layer_objects(layer,objects):
    nodes=set(layer['receiver_nodes'])
    components={}
    for selector in layer.get('receiver_components',[]):
        components.setdefault(selector['source_node'],set()).update(selector['projection_components'])
    return [obj for obj in objects if obj.get('source_node') in nodes and
            (obj.get('source_node') not in components or obj.get('projection_component') in components[obj['source_node']])]
