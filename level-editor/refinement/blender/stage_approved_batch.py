"""Create a guarded publication plan from approved bake handoffs, then stage it.

Run in Blender with -- <config.json>. Config paths are repository-relative;
each import supplies asset_id, blend_path and review_manifest. The output is
never promoted to the live editor by this script.
"""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage_reviewed_publication import stage
from catalog_schema import source_for_part


def run(config_path):
    config_path = Path(config_path).resolve(strict=True)
    config = json.loads(config_path.read_text())
    root = Path(config.pop('repository_root', '.')).resolve(strict=True)
    for key in ('baseline', 'output', 'catalog', 'hackable_map'):
        config[key] = str((root / config[key]).resolve())
    if config.get('ground_texture_handoff'):
        for key in ('blend_path', 'proof'):
            config['ground_texture_handoff'][key] = str((root / config['ground_texture_handoff'][key]).resolve(strict=True))
    catalog = json.loads(Path(config['catalog']).read_text())
    groups = {group['id']: group for group in catalog['groups']}
    for item in config['imports']:
        for key in ('blend_path', 'review_manifest'):
            item[key] = str((root / item[key]).resolve(strict=True))
        actual_sha = hashlib.sha256(Path(item['blend_path']).read_bytes()).hexdigest()
        if item.get('blend_sha256') and item['blend_sha256'] != actual_sha:
            raise ValueError('Approved handoff hash changed: ' + item['asset_id'])
        item['blend_sha256'] = actual_sha
        # Discover only visible meshes owned by this exact catalog group. A
        # worker can contain the whole map, including stale sibling buildings.
        item['discover_asset_members'] = not config.get('approved_texture_imports')
        if item.get('source_nodes') == ['ground']:
            if not config.get('approved_texture_imports') or item.get('projection_kind')!='planar-atlas':
                raise ValueError('Ground requires a validated planar texture handoff')
            continue
        owned = {source_for_part(part) for part in groups[item['asset_id']]['parts']}
        selected = item.get('source_nodes', sorted(owned))
        if not selected or set(selected) - owned:
            raise ValueError('Selected source nodes escape catalog ownership: ' + item['asset_id'])
        item['source_nodes'] = selected
    plan_path = Path(config['output']).with_suffix('.plan.json')
    if plan_path.exists():
        raise FileExistsError(plan_path)
    plan_path.write_text(json.dumps(config, indent=2) + '\n')
    return stage(plan_path)


if __name__ == '__main__':
    run(sys.argv[sys.argv.index('--') + 1])
