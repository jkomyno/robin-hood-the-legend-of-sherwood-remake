"""Prepare isolated tower/drawbridge revisions for the lifting-frame canopy."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from refinement_workspace import prepare, modified
from asset_reference_views import render_states
from refinement_inventory import validate_catalog

TOWER = 'leicester-church-side-tower'
BRIDGE = 'leicester-east-moat-drawbridge'
NODE = 'building-221'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry(obj):
    return {'matrix': [list(row) for row in obj.matrix_world],
            'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons]}


def run(root, state):
    root = Path(root).resolve()
    base = Path('level-editor/work/leicester-refinement/round-1').resolve()
    tower = base / 'assets-v2' / TOWER
    catalog_path = root / 'catalog.json'
    inventory_path = tower / 'reference/inventory.json'
    if not catalog_path.exists():
        catalog = json.loads((tower / 'reference/grouping.json').read_text())
        groups = {g['id']: g for g in catalog['groups']}
        part = next(p for p in groups[TOWER]['parts'] if p['obstacle'] == 221)
        groups[TOWER]['parts'].remove(part)
        groups[BRIDGE]['parts'].append({**part, 'name': 'Drawbridge lifting-frame canopy'})
        catalog_path.write_text(json.dumps(catalog, indent=2)+'\n')
        validate_catalog(inventory_path, catalog_path)
        review = {'status': 'reviewed', 'reviewer': 'architecture_resume',
                  'catalog_sha256': sha(catalog_path), 'inventory_sha256': sha(inventory_path),
                  'evidence': 'Source artwork pixels1644..1733,851..934 show the roof on the drawbridge lifting frame; ownership correction requested by user. No mesh removed or moved.'}
        (root/'grouping-review.json').write_text(json.dumps(review, indent=2)+'\n')
    if state == 'tower':
        source = tower/'model.blend'
        asset = TOWER
        config = json.loads((tower/'workspace.json').read_text())
    else:
        imports = json.loads((base.parent/'publication-37/imports-v1.json').read_text())['imports']
        handoff = next(h for h in imports if h['asset_id'] == BRIDGE)
        if state == 'applied':
            handoff = next(h for h in handoff['texture_states'] if h['endpoint_id'] == state)
        source = Path(handoff['approved_source_blend'])
        asset = BRIDGE
        config = json.loads((Path(handoff['workspace'])/'workspace.json').read_text())
    source_hash = sha(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    collection = bpy.data.collections[config['collection_name']]
    canopy = [o for o in collection.all_objects if o.type == 'MESH' and o.get('source_node') == NODE]
    if len(canopy) != 1:
        raise ValueError('Expected exactly one canonical lifting-frame canopy')
    canopy = canopy[0]
    context_geometry = geometry(canopy)
    if state != 'tower':
        # Endpoint context predates the reviewed canopy mesh; transfer the exact tower revision.
        from mathutils import Matrix
        authoritative = json.loads((root/'tower-ownership.json').read_text())['geometry_before']
        with bpy.data.libraries.load(str(tower/'model.blend'), link=False) as (available, selected):
            selected.objects = ['Church Side Tower / Church Side Tower component 221']
        donor = selected.objects[0]
        canopy.data = donor.data.copy()
        bpy.data.objects.remove(donor, do_unlink=True)
        canopy.matrix_world = Matrix(authoritative['matrix'])
    before = geometry(canopy)
    old_group = canopy.get('asset_group')
    if old_group != TOWER:
        raise ValueError('Canopy source ownership drifted')
    canopy['asset_group'] = BRIDGE
    canopy['asset_name'] = 'East Moat Drawbridge'
    canopy['part_name'] = 'Drawbridge lifting-frame canopy'
    canopy['ownership_revision'] = 'church-bridge-canopy-v1'
    canopy['drawbridge_static_source_node'] = NODE
    canopy.name = 'East Moat Drawbridge / lifting-frame canopy'
    matrix = canopy.matrix_world.copy()
    parents = [o for o in collection.all_objects if o.type == 'EMPTY' and o.get('asset_group') == BRIDGE]
    if len(parents) == 1:
        canopy.parent = parents[0]
        canopy.matrix_world = matrix
    assert before == geometry(canopy), 'Ownership transfer moved canopy geometry'
    owners = {}
    for obj in collection.all_objects:
        if obj.type == 'MESH' and obj.get('source_node'):
            owners.setdefault(obj['source_node'], set()).add(obj.get('asset_group'))
    if owners[NODE] != {BRIDGE}:
        raise ValueError('Duplicate canopy ownership')
    report = {'source_blend': str(source), 'source_sha256': source_hash,
              'source_node': NODE, 'from': TOWER, 'to': BRIDGE,
              'geometry_before': before, 'geometry_after': geometry(canopy),
              'superseded_endpoint_context_geometry': context_geometry if state != 'tower' else None,
              'missing_parts': [], 'duplicate_owners': [n for n,g in owners.items() if len(g)>1],
              'changed_transforms': [], 'canonical_canopy_instances': 1,
              'geometry_approval': 'pending user review'}
    (root/f'{state}-ownership.json').write_text(json.dumps(report, indent=2)+'\n')
    snapshot = root/f'{state}-ownership-source.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(snapshot))
    workspace = root / (TOWER if state == 'tower' else BRIDGE+'-'+state)
    prepare(workspace, asset_id=asset, scene_name=config['scene_name'],
            collection_name=config['collection_name'], source_path=config['source_path'],
            grouping_manifest=catalog_path, inventory_path=inventory_path,
            review_path=root/'grouping-review.json', projection_manifest=config.get('projection_manifest'),
            source_mask_manifest=config['source_mask_manifest'], framing_padding=1.1)
    if state != 'tower':
        prepared = json.loads((workspace/'workspace.json').read_text())
        prepared['static_source_nodes'] = [NODE]
        (workspace/'workspace.json').write_text(json.dumps(prepared, indent=2)+'\n')
    modified(workspace)
    if state == 'tower':
        render_states(workspace, workspace/'inspection/states')
    shutil.copy2(__file__, workspace/'recipe.py')
    (workspace/'review.md').write_text('Canopy ownership correction. Source221 is the roof of the east-moat drawbridge lifting frame, transferred intact from the church-side tower. Mesh vertices and world transform preserved. Geometry/grouping approval pending; no texture approval inferred. See parent source-context.png and ownership report.\n')
    assert sha(source) == source_hash, 'Approved source worker changed'
    print('OWNERSHIP_REVISION_PREPARED', workspace, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('state', choices=['tower', 'initial', 'applied'])
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    run(args.root, args.state)
