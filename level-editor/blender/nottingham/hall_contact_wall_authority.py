"""Restore the source-traced hall wall without widening foreign-spire exclusions."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def apply(authority, assignments, evidence_path):
    from PIL import Image, ImageChops
    authority, evidence_path = Path(authority), Path(evidence_path).resolve()
    evidence = json.loads(evidence_path.read_text())
    domain_path = Path(evidence['mask_path'])
    assert sha(domain_path) == evidence['mask_sha256']
    assert evidence['covered_revealed_rgb_different_pixels'] == 0
    inventory_path = authority / 'manifest.json'
    inventory = json.loads(inventory_path.read_text())
    records = {row['index']: row for row in inventory['masks']}
    size = Image.open(evidence['source_images']['exterior']['path']).size
    for source in evidence['source_images'].values():
        assert sha(source['path']) == source['sha256']
    def native(index):
        row = records[index]
        image = Image.new('L', size)
        image.paste(Image.open(authority / row['png']).convert('L'), tuple(row['box_top_left']))
        return image
    domain = Image.new('L', size)
    cropped = Image.open(domain_path).convert('L')
    box = evidence['source_box']
    assert cropped.size == (box[2]-box[0], box[3]-box[1])
    domain.paste(cropped, tuple(box[:2]))
    roof = json.loads((authority / 'authority-proof.json').read_text())['authored_domain_index']
    available = ImageChops.subtract(ImageChops.darker(native(442), native(449)), native(roof))
    assert ImageChops.subtract(domain, available).getbbox() is None
    assert sum(1 for value in domain.getdata() if value) == evidence['domain_pixels']
    next_index = max(records) + 1
    indices = {}
    for label, image in [('wall', domain), ('spire-remainder', ImageChops.subtract(native(442), domain)),
                         ('revealed-foreign-remainder', ImageChops.subtract(native(1110), domain))]:
        index = next_index + len(indices)
        bounds = image.getbbox()
        name = f'{index:06d}-hall-contact-{label}.png'
        image.crop(bounds).save(authority / name)
        inventory['masks'].append(dict(index=index, png=name, box_top_left=list(bounds[:2]),
            box_size=[bounds[2]-bounds[0], bounds[3]-bounds[1]], authored=True,
            derivation='Native source domains with the independently traced hall504 wall strip restored.',
            review_evidence=str(evidence_path), review_evidence_sha256=sha(evidence_path)))
        indices[label] = index
    for label, replaced, replacement in [('exterior', 442, indices['spire-remainder']),
                                          ('interior-patch-008', 1110, indices['revealed-foreign-remainder'])]:
        entry = next(row for row in assignments['projections'][label]['assignments']
                     if row.get('source_node') == 'building-504' and not row.get('projection_component'))
        assert replaced in entry['exclude_mask_indices']
        entry['exclude_mask_indices'] = [replacement if value == replaced else value
                                         for value in entry['exclude_mask_indices']]
        entry.update(review_evidence=str(evidence_path),
                     exclusion_reason='Preserve the foreign-spire silhouette except its source-traced overlap with the hall wall at x288..302 below the eave.',
                     review_note='Hall449 wall authority restored only inside the traced domain; saved source atlas restoration additionally requires physical first hit on504 face17. All prior valid source pixels remain protected.')
    inventory_path.write_text(json.dumps(inventory, indent=2) + '\n')
    (authority / 'wall-authority-proof.json').write_text(json.dumps(dict(
        source_evidence=str(evidence_path), source_evidence_sha256=sha(evidence_path),
        source_domain_sha256=sha(domain_path), domain_pixels=evidence['domain_pixels'],
        indices=indices, native_bitmap_changes=0, boundary_uncertainty_pixels=1,
        scope='Only hall504 source exclusions are narrowed. Native masks and other receivers remain unchanged.'), indent=2) + '\n')
    return indices
