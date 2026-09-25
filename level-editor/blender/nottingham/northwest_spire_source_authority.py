"""Freeze a scoped, source-traced hall-roof domain beside untouched native masks."""
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_authority(original, proposal_path, destination):
    from PIL import Image
    import numpy as np
    original, proposal_path, destination = map(Path, (original, proposal_path, destination))
    assignments = json.loads((original / 'source-masks.json').read_text())
    inventory_path = Path(assignments['mask_inventory'])
    inventory = json.loads(inventory_path.read_text())
    proposal = json.loads(proposal_path.read_text())
    assert proposal['receiver'] == 'building-519'
    destination.mkdir(parents=True, exist_ok=False)
    preserved = {}
    for record in inventory['masks']:
        if not record.get('png'):
            continue
        source = inventory_path.parent / record['png']
        relative = Path(record['png'])
        if relative.is_absolute():
            relative = Path(f"native-{record['index']:06d}-{relative.name}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
        preserved[str(relative)] = sha(source)
        record['png'] = str(relative)
    index = max(row['index'] for row in inventory['masks']) + 1
    size = Image.open(original / 'reference/source.png').size
    # Match source rays at pixel centers, including the traced polygon boundary.
    # Integer drawing routines round sloping edges differently from mesh hits.
    yy, xx = np.mgrid[:size[1], :size[0]]
    xx, yy = xx + .5, yy + .5
    inside = np.zeros(xx.shape, dtype=bool)
    boundary = np.zeros(xx.shape, dtype=bool)
    polygon = proposal['polygon']
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (xx-ax)*(by-ay) - (yy-ay)*(bx-ax)
        boundary |= ((np.abs(cross) < 1e-7) & (xx >= min(ax,bx)) &
                     (xx <= max(ax,bx)) & (yy >= min(ay,by)) & (yy <= max(ay,by)))
        if ay != by:
            inside ^= ((ay > yy) != (by > yy)) & (xx < (bx-ax)*(yy-ay)/(by-ay)+ax)
    bitmap = Image.fromarray((inside | boundary).astype('uint8') * 255)
    box = bitmap.getbbox()
    name = f'{index:06d}-authored-hall-roof-contact.png'
    bitmap.crop(box).save(destination / name)
    record = dict(index=index, png=name, box_top_left=list(box[:2]),
                  box_size=[box[2]-box[0], box[3]-box[1]], authored=True,
                  derivation='Source-traced foreground hall shingles at the northwest spire contact; excludes tower masonry and window.',
                  source_trace_sha256=sha(proposal_path))
    inventory['masks'].append(record)
    (destination / 'manifest.json').write_text(json.dumps(inventory, indent=2)+'\n')
    assignments['mask_inventory'] = str((destination/'manifest.json').resolve())
    for assignment in assignments['projections']['exterior']['assignments']:
        if assignment['source_node'] == 'building-519':
            assignment.setdefault('exclude_mask_indices', []).append(index)
            assignment.update(exclusions_reviewed=True, exclusion_reason='Adjacent hall roof owns the source-traced shingles; tower stone and slit window remain owned.', review_evidence=str(proposal_path.resolve()))
        elif assignment['source_node'] == 'building-505':
            assignment.update(mask_indices=[index], reviewed=True, authored_source_ownership_reviewed=True,
                              constraint_kind='reviewed-authored-source-domain',
                              review_note='Only the source-traced foreground roof contact is accepted as an occluder in this spire packet.',
                              review_evidence=str(proposal_path.resolve()))
            assignment.pop('accepted_source_pixels', None)
    (destination/'assignments.json').write_text(json.dumps(assignments, indent=2)+'\n')
    shutil.copyfile(proposal_path, destination/'source-trace.json')
    proof = dict(original_inventory_sha256=sha(inventory_path), source_sha256=sha(original/'reference/source.png'),
                 preserved_native_bitmap_hashes=preserved, authored_domain_index=index,
                 authored_domain_sha256=sha(destination/name), source_trace_sha256=sha(proposal_path),
                 semantics=proposal['semantics'], boundary_uncertainty_pixels=proposal['boundary_uncertainty_pixels'])
    (destination/'authority-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    return destination/'assignments.json'
