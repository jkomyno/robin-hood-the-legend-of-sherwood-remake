"""Bind an independently inspected spire correction for renewed user review."""
import hashlib
import json
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    workspace = Path(sys.argv[1]).resolve()
    def read(name):
        return json.loads((workspace / name).read_text())
    def write(name, value):
        (workspace / name).write_text(json.dumps(value, indent=2) + '\n')
    model, frames = sha(workspace / 'model.blend'), sha(workspace / 'modified/views.json')
    independent = read('inspection/independent-review.json')
    assert independent['status'] == 'PASS'
    assert independent['model_sha256'] == model and independent['modified_views_sha256'] == frames
    assert independent['inspected_views'] == list(range(8))
    for name, digest in independent['evidence_sha256'].items():
        assert sha(workspace / name) == digest, name
    geometry = read('geometry-report.json')
    assert geometry['model_sha256'] == model and geometry['modified_views_sha256'] == frames
    assert len(geometry['changed_objects']) == 2
    for part in geometry['parts']:
        assert part['after']['nonmanifold_edges'] == part['after']['degenerate_faces'] == 0
        assert part['after']['connected_components'] == 1
        assert part['after']['signed_volume'] >= part['before']['signed_volume']
    for name in ['validation.json', 'known-rgb-validation.json', 'inspection/source-domain-difference.json']:
        data = read(name)
        assert data['status'] == 'PASS', name
        assert data.get('model_sha256', model) == model, name
    materials = read('inspection/stored-materials/audit.json')
    assert materials['status'] in ['PASS', 'STRUCTURAL-PASS'] and not materials['problems']
    assert materials['model_sha256'] == model and materials['frame_manifest_sha256'] == frames
    assert set(materials['artifact_sha256']) == {'materials.png', *(f'view-{i}.png' for i in range(8))}
    for name, digest in materials['artifact_sha256'].items():
        assert sha(workspace / 'inspection/stored-materials' / name) == digest
    domain = read('inspection/source-domain-difference.json')
    assert domain['removed_source_pixel_count'] == 0 and domain['source_mask_assignments_unchanged']
    rgb = read('known-rgb-validation.json')
    assert rgb['source_rgb_mismatches'] == rgb['missing_geometry_hits'] == 0
    changes = ['Added compact closed metal edging and pegs at the source-painted roof ridges, replacing the broad grazing projection that stretched these details into ladder-shaped bands.', 'United each detail with its existing roof half while preserving the original roof volume, tower body and all other meshes.', 'Retained every originally accepted source pixel with unchanged source-mask assignments; independently checked the full native source domain and all eight saved-material and solid views.']
    limitations = independent['limitations']
    proofs = ['model.blend', 'modified/views.json', 'source-masks.json', 'reference/source.png', 'source-trace.json', 'geometry-report.json', 'validation.json', 'known-rgb-validation.json', 'inspection/independent-review.json', *independent['evidence_sha256']]
    audit = dict(version=1, status='PASS', asset_id=geometry['asset_id'], model_sha256=model, modified_views_sha256=frames, inspected_views=list(range(8)), actual_material_inspected_views=list(range(8)), source_visible_holes_found=False, geometry_changed=True, original_valid_source_pixels_retained=domain['retained_source_pixel_count'], restored_source_pixels=domain['added_source_pixel_count'], unexplained_source_losses=0, known_rgb_pixels=rgb['known_pixels'], known_rgb_mismatches=0, evidence_sha256={p: sha(workspace/p) for p in proofs}, limitations=limitations, independent_reviewer=independent['reviewer'])
    write('source-coverage-audit.json', audit)
    recipe = Path(__file__).with_name('correct_spire_metal_ridges.py')
    candidate = dict(version=1, asset_id=geometry['asset_id'], status='ready-for-user', geometry_refined=True, geometry_reviewed=True, inspected_views=list(range(8)), model_sha256=model, modified_views_sha256=frames, recipe=str(recipe), recipe_sha256=sha(recipe), changes=changes, limitations=limitations, independent_review='inspection/independent-review.json', source_rgb_validation='known-rgb-validation.json', source_visibility_evidence='inspection/source-domain-difference.json', stored_material_evidence='inspection/stored-materials/audit.json', source_comparison='inspection/source-material-comparison.png', source_comparison_secondary='inspection/native-domain-complement.png', user_approval='pending', geometry_approval='pending-new-user-review', texture_generation='not-started')
    (workspace/'review.md').write_text('# Spire source-projection correction\n\n' + '\n'.join('- ' + item for item in changes + limitations) + '\n\nOriginal approvals remain unchanged. This is a source-only geometry revision awaiting renewed user review. Hidden or source-occluded surfaces remain neutral.\n')
    write('candidate.json', candidate)
    print(workspace/'candidate.json')


if __name__ == '__main__':
    main()
