"""Validate a nonplanar ground atlas without interpreting it as camera tiles."""
import json
from pathlib import Path

from review_evidence import sha


def validate(experiment, bake, frames, validation, approval, model_path):
    import numpy as np
    from PIL import Image
    experiment, bake = Path(experiment), Path(bake)
    before_path, after_path = experiment/'uv-evidence.json', bake/'uv-evidence.json'
    if (sha(before_path) != frames.get('uv_evidence_sha256') or
            sha(after_path) != validation.get('baked_uv_evidence_sha256') or
            sha(experiment/'preparation.json') != validation.get('preparation_sha256')):
        raise ValueError('Ground atlas evidence changed')
    before, after = [json.loads(path.read_text()) for path in (before_path, after_path)]
    if (before['model_sha256'] != approval['saved_model_sha256'] or
            after['model_sha256'] != sha(model_path) or
            validation.get('baked_model_sha256') != after['model_sha256']):
        raise ValueError('Ground atlas model binding changed')
    for field in ('asset_id', 'receiver', 'source_node', 'geometry',
                  'geometry_uv_matrix_sha256', 'atlas_dimensions', 'uv_layer',
                  'material_slot', 'physical_opacity', 'direct_image_color',
                  'alpha_mode', 'interpolation'):
        if before.get(field) != after.get(field):
            raise ValueError('Ground atlas geometry/material contract changed: ' + field)
    if (before['source_node'] != 'ground' or before['physical_opacity'] != 'OPAQUE' or
            before['direct_image_color'] is not True):
        raise ValueError('Ground atlas requires one direct opaque ground receiver')
    if (after['atlas_sha256'] != validation['generated_sha256'] or
            sha(bake/'atlas.png') != after['atlas_sha256']):
        raise ValueError('Ground packed atlas differs from reviewed generation')
    original = np.asarray(Image.open(experiment/'input.png').convert('RGBA'))
    final = np.asarray(Image.open(bake/'atlas.png').convert('RGBA'))
    mask = np.asarray(Image.open(experiment/'mask.png').convert('RGBA'))
    if original.shape != final.shape or original.shape != mask.shape:
        raise ValueError('Ground atlas dimensions differ')
    if (not np.array_equal(original[mask[:, :, 3] > 127], final[mask[:, :, 3] > 127]) or
            not np.array_equal(original[:, :, 3], final[:, :, 3])):
        raise ValueError('Ground atlas changed protected artwork or alpha')
    return {path: sha(path) for path in (before_path, after_path, bake/'atlas.png',
                                        experiment/'preparation.json', experiment/'mask.png')}
