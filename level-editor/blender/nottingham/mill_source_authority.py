"""Freeze the mill's authored chimney/hay boundary alongside unchanged native masks."""
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_authority(work, destination):
    work, destination = Path(work), Path(destination)
    original = work / 'round-1/assets/nottingham-village-mill'
    assignments = json.loads((original / 'source-masks.json').read_text())
    source_inventory = Path(assignments['mask_inventory'])
    inventory = json.loads(source_inventory.read_text())
    proposal = work / 'coordinator-audit/mill-chimney-depth'
    trace = json.loads((proposal / 'domain-proposal.json').read_text())
    assert trace['source_sha256'] == sha(original / 'reference/source.png')
    assert len(inventory['masks']) == 529
    destination.mkdir(parents=True, exist_ok=False)
    preserved = {}
    for record in inventory['masks']:
        relative = record.get('png')
        if relative is None:
            continue
        source = source_inventory.parent / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
        preserved[relative] = sha(source)
    bitmap = destination / '000529-authored-stone.png'
    shutil.copyfile(proposal / 'native155-stone-proposal.png', bitmap)
    record = dict(inventory['masks'][155])
    record.update(index=529, png=bitmap.name, authored=True,
                  derivation='Source-traced chimney masonry; native155 hay overreach removed.',
                  source_native_index=155, source_trace_sha256=sha(proposal / 'domain-proposal.json'))
    inventory['masks'].append(record)
    (destination / 'manifest.json').write_text(json.dumps(inventory, indent=2) + '\n')
    assignments['mask_inventory'] = str((destination / 'manifest.json').resolve())
    for assignment in assignments['projections']['exterior']['assignments']:
        if assignment['source_node'] == 'building-241':
            assignment.update(mask_indices=[529], review_evidence=str(proposal / 'stone-boundary-proposal.png'),
                              review_note='Authored source trace separates chimney masonry from native155 hay overreach.')
        elif assignment['source_node'] == 'building-240':
            assignment.update(mask_indices=[144], exclude_mask_indices=[529], exclusions_reviewed=True,
                              exclusion_reason='Only source-traced chimney masonry is excluded; original native155 hay remains owned by mound240.',
                              review_evidence=str(proposal / 'stone-boundary-proposal.png'))
    (destination / 'assignments.json').write_text(json.dumps(assignments, indent=2) + '\n')
    proof = dict(original_inventory_sha256=sha(source_inventory),
                 source_sha256=trace['source_sha256'], preserved_native_bitmap_hashes=preserved,
                 authored_domain_index=529, authored_domain_sha256=sha(bitmap),
                 source_trace=trace, source_trace_sha256=sha(proposal / 'domain-proposal.json'))
    (destination / 'authority-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return destination / 'assignments.json'
