"""Review a continuous north church crown without assigning regional artwork RGB."""
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forest_fringe
import foliage_trees


def audit_evidence(workspace):
    """Check regional alpha, roof exclusions, and explicitly inferred upper crown."""
    workspace = Path(workspace).resolve()
    config = json.loads((workspace / 'workspace.json').read_text())
    if config['asset_id'] != 'leicester-north-church-tree':
        raise ValueError('North church recipe requires its exact isolated asset')
    source = workspace / 'inspection/continuous-volume'
    packet = json.loads((source / 'source-partition.json').read_text())
    spec = forest_fringe.SPECS[92]
    if packet['regional_mask_index'] != 28 or packet['source_rgb_projected']:
        raise ValueError('Regional crown evidence must not acquire source RGB ownership')
    manifest_path = Path(config['source_mask_manifest'])
    manifest = json.loads(manifest_path.read_text())
    inventory_path = (manifest_path.parent / manifest['mask_inventory']).resolve()
    inventory = json.loads(inventory_path.read_text())
    masks = {entry['index']: entry for entry in inventory['masks']}
    coverage = np.asarray(Image.open(source / 'derived-neutral-coverage.png')) > 0
    native = forest_fringe.paste_mask(masks[28], spec['box'])
    excluded = np.zeros_like(native)
    wood = np.zeros_like(native)
    for index in spec['roof']:
        excluded |= forest_fringe.paste_mask(masks[index], spec['box'])
    for index in spec['wood']:
        wood |= forest_fringe.paste_mask(masks[index], spec['box'])
    visible = np.indices(coverage.shape)[0] + spec['box'][1] >= 0
    if np.any(coverage & excluded) or np.any(coverage & visible & ~native):
        raise ValueError('Crown coverage exceeds native regional alpha or includes a roof')
    for lobe in packet['lobes']:
        left, top, right, bottom = lobe['bbox_source']
        alpha = np.asarray(Image.open(lobe['source']).convert('RGBA'))[:, :, 3] > 0
        local_wood = wood[top-spec['box'][1]:bottom-spec['box'][1], left-spec['box'][0]:right-spec['box'][0]]
        if alpha.shape != local_wood.shape or np.any(alpha & local_wood):
            raise ValueError('Front foliage alpha includes separately owned wood')
    front_alpha = np.asarray(Image.open(source / 'volume-front.png').convert('RGBA'))[:, :, 3] > 0
    if front_alpha.shape != wood.shape or np.any(front_alpha & wood):
        raise ValueError('Continuous front crown alpha includes separately owned wood')
    report = {
        'status': 'PASS', 'asset_id': config['asset_id'],
        'native_regional_mask': 28, 'excluded_roof_masks': spec['roof'],
        'separate_wood_masks': spec['wood'],
        'observed_regional_coverage_pixels': int((coverage & visible).sum()),
        'inferred_offmap_coverage_pixels': int((coverage & ~visible).sum()),
        'front_wood_exclusion_pixels': int((coverage & wood).sum()),
        'source_rgb_ownership': 'none',
        'native_alpha_sha256': foliage_trees.sha(masks[28]['png']),
        'source_rgb_sha256': foliage_trees.sha(config['source_path']),
        'limitations': [
            'Regional mask 28 bounds visible foliage but does not isolate this individual tree.',
            'Upper completion, lateral crown allocation and hidden crown depth remain inferred.',
            'Roof masks are excluded; wood remains separate geometry and is excluded from front foliage coverage.',
        ],
    }
    (workspace / 'inspection/church-crown-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def run(workspace):
    import forest_volume
    import foliage_packets
    workspace = Path(workspace).resolve()
    report = forest_volume.run(workspace, depth_fraction=.46)
    evidence = audit_evidence(workspace)
    foliage_packets.run(workspace)
    return {'geometry': report, 'evidence': evidence['status']}


if __name__ == '__main__':
    workspace = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    print(json.dumps(run(workspace)))
