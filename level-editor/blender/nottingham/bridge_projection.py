"""Review the bridge above its depicted stream rather than the flat terrain proxy.

Install this adapter before preparing or regenerating the bridge packet. It
retains all neighboring structure occluders and native silhouette constraints.
The terrain receiver is excluded because the source-visible arches descend
below the imported flat terrain. Terrain repair remains a separate asset task.
"""
import hashlib
from pathlib import Path


ASSET = 'nottingham-village-stone-bridge'
POLICY = {
    'version': 1,
    'excluded_occluder_nodes': ['ground'],
    'evidence': 'Native mask 202 and the source context show the two arch supports '
                'and stream below the parapets; the flat ground proxy intersects them.',
    'limitation': 'This projection policy does not repair terrain geometry. '
                  'The stream depression must be reconciled before map publication.',
}


def install(workspace_module):
    """Use the reusable bake and review APIs with a recorded explicit partition."""
    if getattr(workspace_module, '_nottingham_bridge_adapter', False):
        return
    original_reproject = workspace_module._reproject
    original_layers = workspace_module._review_layers

    def partition(config):
        import bpy
        nodes = sorted({obj.get('source_node') for obj in
                        bpy.data.collections[config['collection_name']].all_objects
                        if obj.type == 'MESH' and not obj.hide_render})
        if 'ground' not in nodes or not {'building-290', 'building-291'} <= set(nodes):
            raise ValueError('Bridge projection requires both parapets and explicit terrain context')
        policy = {**POLICY, 'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        if config.get('bridge_projection_policy', policy) != policy:
            raise ValueError('Bridge projection policy differs from its frozen packet')
        config['bridge_projection_policy'] = policy
        return nodes, [node for node in nodes if node != 'ground']

    def reproject(config, report_dir):
        if config['asset_id'] != ASSET:
            return original_reproject(config, report_dir)
        if config.get('projection_manifest'):
            raise ValueError('Bridge adapter expects an explicit covered-state source, not interior layers')
        from reproject_map import restore_projection, reproject_map
        from source_projection_bake import bake
        _, occluders = partition(config)
        restore_projection(config['map_name'])
        report = reproject_map(config['map_name'], config['source_path'],
            Path(report_dir) / 'source.json', elevation_deg=config['elevation_degrees'],
            receiver_nodes=config['part_ids'], occluder_nodes=occluders)
        report['ownership'] = bake(config['map_name'], config['source_path'],
            Path(report_dir) / 'ownership.json', receiver_nodes=config['part_ids'],
            occluder_nodes=occluders, projection_label='exterior',
            elevation_deg=config['elevation_degrees'], preserve_authored=False,
            source_mask_manifest=config.get('source_mask_manifest'))
        report['bridge_projection_policy'] = config['bridge_projection_policy']
        return report

    def layers(config):
        if config['asset_id'] != ASSET:
            return original_layers(config)
        receivers, occluders = partition(config)
        return [{'source_path': config['source_path'], 'receiver_nodes': receivers,
                 'occluder_nodes': occluders, 'projection_label': 'exterior'}]

    workspace_module._reproject = reproject
    workspace_module._review_layers = layers
    workspace_module._nottingham_bridge_adapter = True
