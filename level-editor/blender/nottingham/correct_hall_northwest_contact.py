"""Prepare the hall side of the paired, unapproved northwest roof contact."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]
from correct_spire_metal_ridges import sha


def main():
    import bpy
    import refinement_workspace as rw
    from render_slots import acquire
    from northwest_spire_source_authority import prepare_authority
    new = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    spire = new.parent / 'nottingham-castle-northwest-spire'
    old = WORK / 'round-42/assets/nottingham-castle-main-hall'
    assert sha(old / 'model.blend') == '7f11aef8ed118710b098633cdfa50341bd7964fd33ba38d7eb5219a1b0d3404e'
    authority = new.parent / 'hall-contact-source-authority-v2'
    if not authority.exists():
        prepare_authority(old, spire / 'contact-trace.json', authority)
        assignments = json.loads((old / 'source-masks.json').read_text())
        assignments['mask_inventory'] = str(authority / 'manifest.json')
        index = json.loads((authority / 'authority-proof.json').read_text())['authored_domain_index']
        assignments['projections']['exterior']['assignments'].append(dict(
            source_node='building-505', projection_component='castle-hall-northwest-contact',
            mask_indices=[index], reviewed=True, authored_source_ownership_reviewed=True,
            constraint_kind='reviewed-authored-source-domain',
            review_evidence=str(spire / 'contact-trace.json'),
            review_note='Exact source-traced foreground shingles at northwest tower attachment.'))
        if '--wall-authority' in sys.argv:
            from hall_contact_wall_authority import apply as apply_wall_authority
            apply_wall_authority(authority, assignments,
                Path(sys.argv[sys.argv.index('--wall-authority') + 1]))
        (authority / 'assignments.json').write_text(json.dumps(assignments, indent=2) + '\n')
    layers_path = authority / 'projection-layers.json'
    if not layers_path.exists():
        layers = json.loads((old / 'projection-layers.json').read_text())
        selectors = layers['projection_reviews']['patch-008']['receiver_components']['exterior']
        selector = next(s for s in selectors if s['source_node'] == 'building-505')
        selector['projection_components'].append('castle-hall-northwest-contact')
        layers_path.write_text(json.dumps(layers, indent=2) + '\n')
    acquire(slots=2)
    bpy.ops.wm.open_mainfile(filepath=str(old / 'model.blend'))
    config = json.loads((old / 'workspace.json').read_text())
    with bpy.data.libraries.load(str(spire / 'model.blend'), link=False) as (source, target):
        target.objects = [n for n in source.objects if n == 'building-505__castle-hall-northwest-contact']
    extension = target.objects[0]
    if extension is None:
        raise ValueError('Paired contact extension missing')
    extension['projection_component'] = 'castle-hall-northwest-contact'
    extension['reveal_component_patch_id'] = 'patch-008'
    extension['reveal_component_role'] = 'retained-roof'
    bpy.data.collections[config['collection_name']].objects.link(extension)
    # Every paired tower component must match the scene used by source audits.
    # The original sloped roof otherwise blocks the newly assigned roof contact.
    context_nodes = {'building-519', 'building-520', 'building-521'}
    with bpy.data.libraries.load(str(spire / 'model.blend'), link=False) as (source, target):
        target.objects = [n for n in source.objects if n.startswith('Castle hall northwestern spire /')]
    donors = {o.get('source_node'): o for o in target.objects if o and o.type == 'MESH'}
    if set(donors) != context_nodes:
        raise ValueError('Expected all three paired northwest tower components')
    for node, donor in donors.items():
        body = next(o for o in bpy.data.collections[config['collection_name']].all_objects
                    if o.type == 'MESH' and o.get('source_node') == node)
        # Unlinked library transforms are unevaluated; retain canonical placement.
        body.data = donor.data.copy()
        bpy.data.objects.remove(donor, do_unlink=True)
    rw.prepare(new, asset_id=config['asset_id'], scene_name=config['scene_name'],
               collection_name=config['collection_name'], source_path=old / 'reference/source.png',
               grouping_manifest=old / 'reference/grouping.json', inventory_path=old / 'reference/inventory.json',
               review_path=old / 'reference/grouping-review.json', projection_manifest=layers_path,
               source_mask_manifest=authority / 'assignments.json', width=384, height=384,
               context_padding=25, framing_padding=1.08,
               lighting=json.loads((WORK / 'lighting-calibration/map-lighting.json').read_text())['lighting'])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(new / 'model.blend'))
    rw.modified(new)
    (new / 'inspection').mkdir(exist_ok=True)
    # A dense atlas keeps bilinear footprints inside the small traced contact.
    # The ordinary one-texel atlas blended neutral samples into its source edge.
    from source_projection_bake import bake
    extension = bpy.data.objects['building-505__castle-hall-northwest-contact']
    extension['source_contact_texels_per_unit'] = 16
    bake(config['map_name'], old / 'reference/source.png',
         new / 'inspection/contact-dense-source-bake.json',
         receiver_nodes=['building-505'], receiver_object_names=[extension.name],
         receiver_asset_id=config['asset_id'], projection_label='exterior',
         source_mask_manifest=new / 'source-masks.json', preserve_authored=False,
         collection_name=config['collection_name'], texels_per_unit=16)
    bpy.ops.wm.save_as_mainfile(filepath=str(new / 'model.blend'))
    from restore_foreign_uv_schema import restore_foreign_uv_schema
    restore_foreign_uv_schema(new, apply=True)
    from audit_stored_materials import run
    run(new, new / 'inspection/stored-materials', render=True, export=False)
    report = dict(status='awaiting-independent-review', asset_id=config['asset_id'],
                  original_model_sha256=sha(old / 'model.blend'), model_sha256=sha(new / 'model.blend'),
                  modified_views_sha256=sha(new / 'modified/views.json'),
                  paired_spire_model_sha256=sha(spire / 'model.blend'),
                  changes=['Continued existing retained roof plane into the traced northwest contact.',
                           'All three paired tower context components match the corrected spire, including its closed concealed contact recess.'],
                  limitations=['Hidden attachment geometry is inferred; renewed paired user review is required.',
                               'Covered and revealed state verification remains required before readiness.'])
    (new / 'geometry-report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
