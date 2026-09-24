"""Validate exact reviewed input or a narrowly authorized lighting derivation."""
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(manifest_path, read_rgba):
    """read_rgba must return top-down, lossless RGBA samples (integer or float)."""
    manifest_path = Path(manifest_path)
    packet = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    approval = json.loads((packet / 'approval.json').read_text())
    reviewed = Path(manifest['reviewed_packet'])
    original_hash = sha(reviewed / 'textured.png')
    input_hash = sha(packet / 'input.png')
    if approval.get('status') != 'approved' or approval.get('input_sha256') != input_hash:
        raise ValueError('Exact input sheet has not been approved')
    if approval.get('asset_id') != manifest['asset_id']:
        raise ValueError('Approval asset does not match camera manifest')
    if sha(reviewed / 'views.json') != manifest['reviewed_manifest_sha256']:
        raise ValueError('Reviewed cameras or lighting changed after approval')
    if original_hash == input_hash:
        return  # Preserve the existing byte-exact input contract.
    derived = approval.get('derived_input', {})
    if (derived.get('kind') != 'unknown-geometry-lighting-only'
            or derived.get('original_approved_source_sha256') != original_hash
            or derived.get('known_and_background_rgba_preserved') is not True
            or derived.get('alpha_preserved') is not True
            or not derived.get('approval_scope')):
        raise ValueError('Reviewed source sheet changed without a valid lighting derivation')
    lighting_hash = manifest.get('lighting_config_sha256')
    if not isinstance(lighting_hash, str) or len(lighting_hash) != 64 or derived.get('lighting_config_sha256') != lighting_hash:
        raise ValueError('Derived lighting configuration binding changed')
    if sha(packet / 'solid.png') != approval.get('solid_sha256') or approval.get('solid_sha256') != approval.get('lighting_sha256'):
        raise ValueError('Derived calibrated solid changed')
    original = json.loads((reviewed / 'views.json').read_text())
    for key in ('asset_id', 'tile_size', 'object_names', 'collection_name'):
        if manifest.get(key) != original.get(key):
            raise ValueError('Derived geometry or layout changed: ' + key)
    width, height = manifest['tile_size']
    if manifest['layout'] != dict(columns=4, rows=2, width=4*width, height=2*height):
        raise ValueError('Derived layout must retain the eight original tiles')
    if original['layout'].get('columns') != 4 or original['layout'].get('rows') != 2:
        raise ValueError('Original layout differs')
    views = manifest['views']
    if len(views) != 8 or [v['index'] for v in views] != list(range(8)):
        raise ValueError('Derived camera indices changed')
    if len(original['views']) != 8:
        raise ValueError('Original camera count differs')
    source, result, solid, mask = [read_rgba(p) for p in
        (reviewed/'textured.png', packet/'input.png', packet/'solid.png', packet/'mask.png')]
    shape = (2*height, 4*width, 4)
    if any(a.shape != shape for a in (source, result, solid, mask)):
        raise ValueError('Derived image dimensions changed')
    unknown = np.zeros(shape[:2], dtype=bool)
    for view, old in zip(views, original['views']):
        if {k:v for k,v in view.items() if k not in ('input','mask','crop')} != {k:v for k,v in old.items() if k not in ('input','mask','crop')}:
            raise ValueError('Derived camera or ownership metadata changed')
        i = view['index']
        expected = dict(left=i%4*width, top=i//4*height, width=width, height=height)
        if view.get('crop') != expected:
            raise ValueError('Derived tile crop changed')
        known_path = reviewed/'views'/f'view-{i}-known.png'
        if not view.get('ownership_sha256') or sha(known_path) != view['ownership_sha256']:
            raise ValueError('Derived ownership buffer changed')
        known = read_rgba(known_path)
        old_solid = read_rgba(reviewed/'views'/f'view-{i}-solid.png')
        if known.shape != (height,width,4) or old_solid.shape != known.shape:
            raise ValueError('Original ownership dimensions changed')
        rows, cols = slice(expected['top'],expected['top']+height), slice(expected['left'],expected['left']+width)
        if not np.array_equal(old_solid[:,:,3],solid[rows,cols,3]):
            raise ValueError('Derived solid silhouette changed')
        threshold = 127 if np.issubdtype(known.dtype, np.integer) else 0.5
        unknown[rows,cols] = (old_solid[:,:,3]>0) & (known[:,:,0]<=threshold)
    opaque = np.iinfo(mask.dtype).max if np.issubdtype(mask.dtype, np.integer) else 1.0
    if not np.array_equal(mask[:,:,3]==0, unknown) or np.any((mask[:,:,3]!=0) & (mask[:,:,3]!=opaque)):
        raise ValueError('Derived mask differs from original ownership')
    if not np.array_equal(source[:,:,3],result[:,:,3]):
        raise ValueError('Derived input alpha changed')
    if not np.array_equal(source[~unknown],result[~unknown]):
        raise ValueError('Derived known or background RGBA changed')
    if not np.array_equal(result[unknown,:3],solid[unknown,:3]):
        raise ValueError('Derived unknown RGB does not match calibrated solid')
