"""Apply reviewed Leicester ownership to a new checkpoint and dispatch workers.

Run in background Blender with --python-exit-code 1. The source remains frozen;
this writes a new grouped checkpoint and commands, never starts render workers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from group_assets import group_assets
from refinement_inventory import validate_catalog
from refinement_workspace import dispatch


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'inventory', 'catalog', 'review', 'source-image', 'output', 'assets'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--projection-manifest', type=Path)
    parser.add_argument('--source-mask-manifest', type=Path)
    parser.add_argument('--max-concurrency', type=int, default=2)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    paths = {key: str(value.resolve()) for key, value in vars(args).items() if isinstance(value, Path)}
    review = json.loads(args.review.read_text())
    if (review.get('status') != 'reviewed' or not review.get('reviewer')
            or review.get('catalog_sha256') != sha(args.catalog)
            or review.get('inventory_sha256') != sha(args.inventory)):
        raise ValueError('Reviewed ownership must match the exact catalog and inventory')
    validation = validate_catalog(args.inventory, args.catalog)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    before = sha(args.source)
    bpy.ops.wm.open_mainfile(filepath=paths['source'], load_ui=False)
    bpy.context.window.scene = bpy.data.scenes['Leicester Refinement']
    initialized_uvs = []
    for obj in bpy.data.collections['Leicester Working'].all_objects:
        if obj.type != 'MESH' or obj.data.uv_layers:
            continue
        if not obj.get('restoration_reason') or not obj.data.materials:
            raise ValueError(f'Missing authored UV/material provenance: {obj.name}')
        # Restored surfaces begin with a neutral material. A placeholder UV
        # channel lets the projection baker replace it with reviewed evidence.
        obj.data.uv_layers.new(name='Unprojected neutral surface')
        initialized_uvs.append(obj['source_node'])
    # Set the new save path before the grouping helper saves its hierarchy.
    bpy.ops.wm.save_as_mainfile(filepath=paths['output'])
    report = group_assets(paths['catalog'])
    result = dispatch(paths['assets'], source_blend=paths['output'], max_concurrency=args.max_concurrency,
                      scene_name='Leicester Refinement', collection_name='Leicester Working',
                      source_path=paths['source_image'], grouping_manifest=paths['catalog'],
                      inventory_path=paths['inventory'], review_path=paths['review'],
                      projection_manifest=paths.get('projection_manifest'),
                      source_mask_manifest=paths.get('source_mask_manifest'))
    if before != sha(args.source):
        raise RuntimeError('Frozen source changed during grouping')
    evidence = {'map': 'Leicester', 'source_sha256': before, 'grouped_sha256': sha(args.output),
                'catalog_validation': validation, 'grouping': report, 'dispatch': result,
                'neutral_uv_initialization': initialized_uvs,
                'arguments': paths, 'script_sha256': sha(__file__)}
    args.output.with_suffix('.grouping.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
