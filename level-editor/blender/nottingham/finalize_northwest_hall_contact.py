"""Bind paired source corrections only after independent saved-material review."""
import hashlib
import json
import shutil
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def main():
    parent = Path(sys.argv[1]).resolve()
    pair = parent / 'paired-source-audit/source-retention.json'
    proof = read(pair)
    assert proof['status'] == 'PASS' and proof['unexplained_losses'] == 0
    visual = parent / 'paired-visual-review/actual/materials.png'
    assert visual.exists()
    pending = []
    def publish_json(path, value):
        pending.append((path, (json.dumps(value, indent=2) + '\n').encode()))
    for asset, key in [('nottingham-castle-northwest-spire', 'spire'), ('nottingham-castle-main-hall', 'hall')]:
        workspace = parent / asset
        model, frames = sha(workspace / 'model.blend'), sha(workspace / 'modified/views.json')
        assert proof[key + '_model_sha256'] == model
        independent_path = workspace / 'inspection/independent-contact-review.json'
        independent = read(independent_path)
        assert independent['status'] == 'PASS'
        assert independent['model_sha256'] == model and independent['modified_views_sha256'] == frames
        assert independent['inspected_views'] == independent['paired_inspected_views'] == list(range(8))
        assert independent['paired_material_sheet_sha256'] == sha(visual)
        assert independent['paired_source_comparison_sha256'] == sha(parent / 'paired-visual-review/source-comparison.png')
        audit_path = workspace / 'inspection/stored-materials/audit.json'
        audit = read(audit_path)
        assert audit['status'] in ['PASS', 'STRUCTURAL-PASS'] and not audit['problems']
        assert audit['model_sha256'] == model and audit['frame_manifest_sha256'] == frames
        for name, digest in audit['artifact_sha256'].items():
            assert sha(audit_path.parent / name) == digest
        assert read(workspace / 'validation.json')['status'] == 'PASS'
        rgb = read(workspace / 'known-rgb-validation.json')
        assert rgb['status'] == 'PASS' and rgb['source_rgb_mismatches'] == rgb['missing_geometry_hits'] == 0
        evidence = [pair, independent_path, audit_path, workspace / 'known-rgb-validation.json']
        if key == 'spire':
            domain = read(workspace / 'inspection/source-domain-difference.json')
            assert domain['removed_source_pixel_count'] == proof['transferred_original_pixels']
            assert {tuple(p) for p in domain['removed_source_pixels']} == {tuple(r['source']) for r in proof['pixels']}
            evidence.append(workspace / 'inspection/source-domain-difference.json')
            changes = ['Added compact metal roof edging and pegs without stretching the original artwork.',
                       'Moved adjacent hall shingle ownership onto the paired closed roof contact; retained tower masonry and door artwork.',
                       'Closed the unsupported right body edge below the eave to expose the original hall roof without painting shingles onto the tower.']
        else:
            material_path = workspace / 'inspection/contact-material-provenance.json'
            material = read(material_path)
            assert material['status'] == 'PASS' and material['model_sha256'] == model
            assert material['transferred_pixels'] == material['all_source_pixels'] == proof['transferred_original_pixels']
            assert material['noncap_pixels'] == material['no_source_pixels'] == material['mixed_source_pixels'] == 0
            evidence.append(material_path)
            states = read(workspace / 'inspection/state-models/manifest.json')
            assert states['primary_model_sha256'] == model and len(states['states']) == 2
            for state in states['states']:
                assert sha(state['model']) == state['model_sha256']
                preservation = read(state['preservation_report'])
                assert preservation['status'] == 'PASS'
                assert preservation['original_owned_object_hashes'] == preservation['saved_owned_object_hashes']
                assert len(preservation['original_owned_object_hashes']) == 47
                wall = preservation['wall_source_restoration']
                assert sha(wall['report']) == wall['report_sha256']
                restoration = read(wall['report'])
                assert restoration['status'] == 'PASS' and restoration['changed_texels'] > 0
                for preserved in ['geometry_uv_material_schema_preserved',
                                  'prior_allowed_source_texels_preserved', 'alpha_preserved',
                                  'all_outside_patch_rgba_preserved']:
                    assert restoration[preserved]
                assert restoration['packed_image_sha256'] == wall['packed_image_sha256']
                assert restoration['edge_padding_texels'] == 24
                taps_path = Path(state['model']).parent / 'native709-taps.json'
                taps = read(taps_path)
                assert taps['model_sha256'] == state['model_sha256']
                assert taps['packed_image_sha256'] == wall['packed_image_sha256']
                assert taps['count'] == taps['all_source_or_authorized_padding'] == 709
                assert taps['mixed'] == taps['fully_neutral'] == 0
                assert taps['minimum_source_weight'] >= 1-1e-6
                assert taps['edge_padding_texels'] == 24 and taps['max_padding_atlas_distance'] <= 1
                assert taps['max_padding_world_distance'] <= 1.001
                evidence.append(taps_path)
                evidence.append(Path(wall['report']))
                evidence.append(Path(state['preservation_report']))
            evidence.append(workspace / 'inspection/state-models/manifest.json')
            changes = ['Added a closed contact tile cap joining the northwest tower to the existing roof slope.',
                       'Preserved original hall geometry and UVs; restored the source-traced wall504 strip while protecting every prior valid source pixel and all other objects.']
        limits = ['The concealed tower attachment is inferred. Its closed cap is 2 world units thick and offset 0.5 toward the source camera (0.287 vertically), overlapping the existing roof.',
                  'Review the two assets together in the paired material sheet. The source-traced cap stops at x304 to preserve adjacent state-dependent roof/wall ownership.',
                  'Hidden faces remain neutral pending renewed user approval and texture generation.',
                  'The source-traced tower/hall wall join at x287/288 has one pixel of boundary uncertainty; the dark join itself is retained.',
                  'Twenty-four previously unknown wall-atlas texels use nearest same-face source-edge padding for filtering; all prior valid source texels are unchanged.']
        if proof.get('inherited_occlusions'):
            assert [r['source'] for r in proof['inherited_occlusions']] == [[249, 615]]
            limits.append('One existing source-pixel boundary at (249,615) remains occluded by the hall stair/parapet edge, 0.1416 world units ahead of the tower. Both approved hit positions are unchanged; this correction creates no new source loss.')
        pending.append((workspace / 'inspection/paired-materials.png', visual.read_bytes()))
        pending.append((workspace / 'inspection/paired-source-comparison.png', (parent / 'paired-visual-review/source-comparison.png').read_bytes()))
        pending.append((workspace / 'inspection/paired-source-retention.json', pair.read_bytes()))
        contract = dict(version=1, status='PASS', asset_id=asset, model_sha256=model,
                        modified_views_sha256=frames, inspected_views=list(range(8)), geometry_changed=True,
                        source_visible_holes_found=False, unexplained_source_losses=0,
                        source_sha256=sha(workspace / 'reference/source.png'), source_masks_sha256=sha(workspace / 'source-masks.json'),
                        changes=changes, limitations=limits,
                        evidence=[dict(path=str(p), sha256=sha(p)) for p in evidence])
        publish_json(workspace / 'source-coverage-audit.json', contract)
        recipe = Path(__file__).with_name('correct_northwest_spire_contact.py' if key == 'spire' else 'correct_hall_northwest_contact.py')
        candidate = dict(version=1, asset_id=asset, status='ready-for-user', geometry_refined=True,
                         geometry_reviewed=True, inspected_views=list(range(8)), model_sha256=model,
                         modified_views_sha256=frames, recipe=str(recipe.resolve()), recipe_sha256=sha(recipe),
                         changes=changes, limitations=limits, independent_review='inspection/independent-contact-review.json',
                         stored_material_evidence='inspection/stored-materials/audit.json',
                         source_visibility_evidence='inspection/paired-source-retention.json', source_rgb_validation='known-rgb-validation.json',
                         source_comparison_secondary='inspection/paired-materials.png', user_approval='pending',
                         geometry_approval='pending-new-user-review', texture_generation='not-started')
        candidate['recipe_steps'] = [dict(script=str(Path(__file__).with_name(name).resolve()),
                                         sha256=sha(Path(__file__).with_name(name))) for name in
                                    ['spire_roof_contact.py', 'northwest_spire_source_authority.py',
                                     'audit_northwest_hall_contact.py', 'preserve_hall_contact_states.py',
                                     'render_northwest_hall_contact.py', 'verify_hall_contact_atlas.py',
                                     'hall_contact_wall_authority.py', 'restore_hall_wall_source.py',
                                     'finalize_northwest_hall_contact.py']]
        candidate['source_comparison'] = 'inspection/paired-source-comparison.png'
        if key == 'hall':
            for state in ['covered', 'revealed']:
                for kind in ['textured', 'solid', 'context']:
                    candidate[f'{state}_{kind}'] = f'states-contact/patch-008/{state}/{kind}.png'
        pending.append((workspace / 'review.md', ('# Paired northwest roof contact correction\n\n' +
                        '\n'.join('- ' + s for s in changes + limits) + '\n\nRenewed user approval pending.\n').encode()))
        publish_json(workspace / 'candidate.json', candidate)
    # Both packets pass all gates before either receives a ready-for-user flag.
    for path, payload in pending:
        path.write_bytes(payload)


if __name__ == '__main__':
    main()
