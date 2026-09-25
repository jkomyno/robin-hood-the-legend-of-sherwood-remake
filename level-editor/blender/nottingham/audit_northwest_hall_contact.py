"""Check source retention on the paired saved hall and northwest-spire meshes."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]
from correct_spire_metal_ridges import sha


def main():
    import bpy
    from audit_spire_source_projection import source_census
    parent = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    spire = parent / 'nottingham-castle-northwest-spire'
    hall = parent / 'nottingham-castle-main-hall'
    hall_model = (Path(sys.argv[sys.argv.index('--hall-model') + 1]).resolve()
                  if '--hall-model' in sys.argv else hall / 'model.blend')
    output = parent / 'paired-source-audit'
    output.mkdir(exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(hall_model))
    config = json.loads((hall / 'workspace.json').read_text())
    collection = bpy.data.collections[config['collection_name']]
    names = json.loads((spire / 'geometry-report.json').read_text())['changed_objects']
    original = {o['source_node']: o for o in collection.all_objects
                if o.type == 'MESH' and o.get('source_node') in ['building-519', 'building-520', 'building-521']}
    with bpy.data.libraries.load(str(spire / 'model.blend'), link=False) as (source, target):
        target.objects = names
    for donor in target.objects:
        receiver = original[donor['source_node']]
        receiver.data = donor.data.copy()
        receiver.hide_render = donor.hide_render
        bpy.data.objects.remove(donor, do_unlink=True)
    masks = json.loads((hall / 'source-masks.json').read_text())
    spire_masks = json.loads((spire / 'source-masks.json').read_text())
    spire_inventory = Path(spire_masks['mask_inventory'])
    hall_inventory = Path(masks['mask_inventory'])
    old_index = json.loads((spire_inventory.parent / 'authority-proof.json').read_text())['authored_domain_index']
    new_index = json.loads((hall_inventory.parent / 'authority-proof.json').read_text())['authored_domain_index']
    inventories = [{r['index']: r for r in json.loads(p.read_text())['masks']}
                   for p in [spire_inventory, hall_inventory]]
    exterior = masks['projections']['exterior']['assignments']
    exterior[:] = [r for r in exterior if r['source_node'] not in original]
    for row in spire_masks['projections']['exterior']['assignments']:
        if row['source_node'] in original:
            row = copy.deepcopy(row)
            for key in ['mask_indices', 'exclude_mask_indices']:
                if key in row:
                    for index in row[key]:
                        destination_index = new_index if index == old_index else index
                        a, b = inventories[0][index], inventories[1][destination_index]
                        assert a['box_top_left'] == b['box_top_left'] and a['box_size'] == b['box_size']
                        assert sha(spire_inventory.parent / a['png']) == sha(hall_inventory.parent / b['png'])
                    row[key] = [new_index if i == old_index else i for i in row[key]]
            exterior.append(row)
    (output / 'source-masks.json').write_text(json.dumps(masks, indent=2) + '\n')
    (output / 'workspace.json').write_text(json.dumps(config, indent=2) + '\n')
    (output / 'reference').symlink_to(hall / 'reference', target_is_directory=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'model.blend'))
    difference = json.loads((spire / 'inspection/source-domain-difference.json').read_text())
    rows, _ = source_census(output, [config['asset_id'], 'nottingham-castle-northwest-spire'],
                            [215, 180, 345, 700], render_materials=False)
    witnesses = [dict(source=p, **rows[tuple(p)]) for p in difference['removed_source_pixels']]
    bad = [r for r in witnesses if r['state'] != 'accepted' or r['receiver'] != 'building-505']
    original_pixels = [r['source'] for r in difference['pixels'] if r['old']['state'] == 'accepted']
    all_bad = [dict(source=p, **rows[tuple(p)]) for p in original_pixels if rows[tuple(p)]['state'] != 'accepted']
    inherited = []
    boundary_path = parent / 'inherited-boundary-evidence.json'
    if boundary_path.exists():
        import math
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        boundary = json.loads(boundary_path.read_text())
        assert boundary['source'] == [249, 615]
        assert {r['object'] for r in boundary['baseline_receivers']} == {
            'Castle hall northwestern spire / Structural volume 519',
            'Castle western stair tower / Structural volume 497'}
        matching = [r for r in all_bad if r['source'] == boundary['source']]
        if matching:
            x, y = boundary['source']
            sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
            toward, down = Vector((0, -cosine, sine)), Vector((0, -sine, -cosine))
            origin = Vector((x+.5, 0, 0)) + down*(y+.5) + toward*10000
            def hit(obj):
                tree = BVHTree.FromPolygons([obj.matrix_world @ v.co for v in obj.data.vertices],
                                            [list(p.vertices) for p in obj.data.polygons])
                return tree.ray_cast(origin, -toward)[0]
            current_hits = {r['object']: hit(bpy.data.objects[r['object']]) for r in boundary['baseline_receivers']}
            for record in boundary['baseline_receivers']:
                assert sha(record['model']) == record['model_sha256']
                bpy.ops.wm.open_mainfile(filepath=record['model'])
                bpy.context.view_layer.update()
                baseline_hit = hit(bpy.data.objects[record['object']])
                assert baseline_hit is not None and current_hits[record['object']] is not None
                assert (baseline_hit-current_hits[record['object']]).length < 1e-5
            inherited = [dict(**r, classification='Unchanged approved hall/tower boundary occlusion',
                              baseline_evidence_sha256=sha(boundary_path)) for r in matching]
    unexplained = [r for r in all_bad if not any(r['source'] == q['source'] for q in inherited)]
    proof = dict(status='PASS' if not bad and not unexplained else 'FAIL',
                 original_spire_pixels=len(original_pixels), retained_in_pair=len(original_pixels)-len(all_bad),
                 transferred_original_pixels=len(witnesses), unexplained_losses=len(unexplained),
                 inherited_occlusions=inherited,
                 wrong_transfer_receivers=bad, original_pixel_failures=all_bad,
                 spire_model_sha256=sha(spire / 'model.blend'), hall_model_sha256=sha(hall_model),
                 paired_model_sha256=sha(output / 'model.blend'), pixels=witnesses,
                 limits=['This validates receiver ownership; saved source-atlas and oblique review are separate gates.'])
    (output / 'source-retention.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(proof['status'], 'transferred', len(witnesses), 'wrong transfers', len(bad),
          'inherited', len(inherited), 'unexplained', unexplained[:12])


if __name__ == '__main__':
    main()
