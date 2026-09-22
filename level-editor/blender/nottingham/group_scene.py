"""Apply a reviewed Nottingham catalog to a new, immutable worker checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.output.exists():
        raise FileExistsError(args.output)
    review = json.loads(args.review.read_text())
    if (review.get('status') != 'reviewed' or not review.get('reviewer')
            or review.get('catalog_sha256') != sha(args.catalog)
            or review.get('inventory_sha256') != sha(args.inventory)):
        raise ValueError('Catalog and inventory require matching reviewed evidence')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import bpy
    from refinement_inventory import validate_catalog
    from group_assets import group_assets
    from refinement_workspace import _geometry
    validation = validate_catalog(args.inventory, args.catalog)
    source_hash = sha(args.source)
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    objects = list(bpy.data.collections['nottingham Working'].all_objects)
    before = {obj: (obj.matrix_world.copy(),
                    [tuple(v.co) for v in obj.data.vertices] if obj.type == 'MESH' else None)
              for obj in objects}
    for obj in objects:
        if obj.type == 'MESH':
            if not obj.get('source_node'):
                raise ValueError('Missing canonical source identity: ' + obj.name)
            if obj.get('source_obstacle') != obj['source_node']:
                obj['imported_source_obstacle'] = obj['source_obstacle']
                obj['source_obstacle'] = obj['source_node']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    evidence = args.output.with_suffix('.evidence')
    evidence.mkdir(exist_ok=False)
    for name, path in (('catalog.json', args.catalog), ('inventory.json', args.inventory),
                       ('grouping-review.json', args.review)):
        shutil.copy2(path, evidence / name)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    result = group_assets(args.catalog)
    for obj, (matrix, vertices) in before.items():
        if vertices is None:
            continue
        if vertices != [tuple(v.co) for v in obj.data.vertices]:
            raise RuntimeError('Grouping changed mesh coordinates: ' + obj.name)
        if max(abs(obj.matrix_world[r][c] - matrix[r][c])
               for r in range(4) for c in range(4)) > 1e-5:
            raise RuntimeError('Grouping changed world transform: ' + obj.name)
    if sha(args.source) != source_hash:
        raise RuntimeError('Frozen source checkpoint changed')
    record = dict(version=1, catalog_validation=validation, grouping=result,
                  source_sha256=source_hash, grouped_sha256=sha(args.output),
                  catalog_sha256=sha(args.catalog), inventory_sha256=sha(args.inventory),
                  recipe_sha256=sha(__file__), argv=sys.argv,
                  working_objects={obj.name: _geometry(obj) for obj in
                                   bpy.data.collections['nottingham Working'].all_objects})
    args.output.with_suffix('.validation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
