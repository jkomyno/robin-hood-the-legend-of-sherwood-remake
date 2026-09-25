"""Build the Lincoln publication scene from explicitly approved worker models.

Run from the repository root (never promotes anything):

    blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/publish_stage.py -- <plan.json>

The plan binds a grouped baseline and every import by hash:

    {"baseline": ".../grouped/lincoln-grouped-v4.blend", "baseline_sha256": "...",
     "catalog": ".../grouping/catalog-v4.json", "catalog_sha256": "...",
     "approvals": ".../approvals.json", "output": ".../publication-N/stage-vM",
     "map_name": "Lincoln",
     "imports": [{"asset_id": "...", "blend_path": ".../model.blend", "blend_sha256": "...",
                  "approval": {"scope": "geometry", "model_sha256": "..."}}]}

Paths are repository-relative. Each import must be bound to an explicit approval record for
the same model hash; only the asset's visible owned meshes are replaced (shared
`import_asset_geometry` guards ownership, coverage, transforms and every outside object).
A later texture republish is a new plan whose imports name the approved baked workers.

The worker keeps the working `lincoln …` scene/collection names so baseline comparisons stay
direct; `publish_export.py` applies the display map name in memory. Writes
`<output>/worker.blend`, `<output>/catalog.json` (catalog with `map` set to `map_name`) and
`<output>/integration.json`.
"""
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(plan_path):
    root = Path.cwd().resolve()
    plan_path = Path(plan_path).resolve(strict=True)
    plan = json.loads(plan_path.read_text())
    resolve = lambda value: (root / value).resolve(strict=True)
    output = (root / plan['output']).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for key in ('baseline', 'catalog'):
        if sha(resolve(plan[key])) != plan[key + '_sha256']:
            raise ValueError('Publication input changed: ' + key)
    approvals = {}
    for record in json.loads(resolve(plan['approvals']).read_text())['approvals']:
        if record['decision'] == 'approved':
            approvals.setdefault(record['asset_id'], []).append(record)
    imports = []
    for item in plan['imports']:
        path = resolve(item['blend_path'])
        digest = sha(path)
        if digest != item['blend_sha256']:
            raise ValueError('Approved model changed: ' + item['asset_id'])
        bound = [record for record in approvals.get(item['asset_id'], [])
                 if record['scope'] == item['approval']['scope'] and record['model_sha256'] == digest]
        if not bound:
            raise ValueError('Import lacks an approval bound to its model: ' + item['asset_id'])
        imports.append((item, path, digest, bound[-1]))

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    tooling = select_tooling()
    import bpy
    from import_reviewed_geometry import import_asset_geometry
    from group_assets import reconcile_asset_groups

    working_scene, working_collection = 'lincoln Refinement', 'lincoln Working'
    owned = {}
    for item, path, _, _ in imports:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        owned[item['asset_id']] = sorted(
            o.name for o in bpy.data.collections[working_collection].all_objects
            if o.type == 'MESH' and not o.hide_render and o.get('asset_group') == item['asset_id'])
        if not owned[item['asset_id']]:
            raise ValueError('Approved model has no visible owned meshes: ' + item['asset_id'])

    bpy.ops.wm.open_mainfile(filepath=str(resolve(plan['baseline'])))
    bpy.context.window.scene = bpy.data.scenes[working_scene]
    results = []
    for item, path, digest, approval in imports:
        result = import_asset_geometry(str(path), asset_id=item['asset_id'],
                                       object_names=owned[item['asset_id']],
                                       collection_name=working_collection)
        results.append({**result, 'model_sha256': digest,
                        'approval': {key: approval[key] for key in
                                     ('asset_id', 'decision', 'scope', 'exact_text', 'model_sha256',
                                      'modified_views_sha256', 'recorded_utc', 'evidence_directory')}})
        print('IMPORTED', item['asset_id'], flush=True)

    # Each worker packs its own copy of shared source atlases; keep one image per content hash.
    by_content, remapped = {}, 0
    for image in list(bpy.data.images):
        if not image.packed_file:
            continue
        keeper = by_content.setdefault(hashlib.sha256(image.packed_file.data).hexdigest(), image)
        if keeper is not image:
            image.user_remap(keeper)
            bpy.data.images.remove(image)
            remapped += 1
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    grouping = reconcile_asset_groups(str(resolve(plan['catalog'])))
    if grouping['moved_components'] or grouping['created_groups'] or grouping['removed_groups']:
        raise RuntimeError('Staged grouping differs from the grouped baseline: ' + json.dumps(grouping)[:2000])

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'worker.blend'))
    catalog = json.loads(resolve(plan['catalog']).read_text())
    catalog['map'] = plan['map_name']
    staged_catalog = output / 'catalog.json'
    staged_catalog.write_text(json.dumps(catalog, indent=2) + '\n')
    report = {'version': 1, 'plan': str(plan_path), 'plan_sha256': sha(plan_path),
              'baseline': str(resolve(plan['baseline'])), 'baseline_sha256': plan['baseline_sha256'],
              'catalog': str(resolve(plan['catalog'])), 'catalog_sha256': plan['catalog_sha256'],
              'staged_catalog': str(staged_catalog), 'staged_catalog_sha256': sha(staged_catalog),
              'tooling': tooling['snapshot_id'], 'imports': results,
              'deduplicated_packed_images': remapped, 'unique_packed_images': len(by_content),
              'grouping': grouping, 'worker': str(output / 'worker.blend'),
              'worker_sha256': sha(output / 'worker.blend'),
              'scope': 'Publication scene; geometry-approved models with source-projected materials.'}
    (output / 'integration.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'imported': len(results), 'worker': report['worker']}), flush=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
