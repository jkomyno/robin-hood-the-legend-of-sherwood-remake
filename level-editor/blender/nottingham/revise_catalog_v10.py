"""Correct inherited market descriptions without changing frozen V9 ownership."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    previous = WORK / 'grouping/catalog-v9.json'
    catalog = json.loads(previous.read_text())
    for group in catalog['groups']:
        if group['id'].startswith('nottingham-market-'):
            group['review_notes'] = ('One separately selectable market building, following the user request for seven buildings. '
                                     'Canonical source parts and any disjoint masonry-base component remain separately selectable within this building. '
                                     'Previously approved exterior geometry is preserved; the new membership requires review.')
    catalog['revision'] = 10
    catalog['revision_notes'] = ['Metadata-only correction of inherited market review notes; V9 ownership, component selectors, geometry and packets are unchanged.']
    target = WORK / 'grouping/catalog-v10.json'
    write(target, catalog)
    validation = json.loads((WORK / 'grouping/validation-v9.json').read_text())
    validation.update(metadata_only=True, ownership_changes=0, description='Replaced obsolete one-terrace descriptions in the seven new market groups.')
    write(WORK / 'grouping/validation-v10.json', validation)
    review = json.loads((WORK / 'grouping/grouping-review-v9.json').read_text())
    review.update(catalog_sha256=sha(target), previous_catalog_sha256=sha(previous), notes=catalog['revision_notes'], validation=validation)
    write(WORK / 'grouping/grouping-review-v10.json', review)
    assignments = json.loads((WORK / 'worker-assignments-v9.json').read_text())
    assignments.update(version=6, catalog='grouping/catalog-v10.json')
    write(WORK / 'worker-assignments-v10.json', assignments)
    print('V10 metadata-only correction; existing frozen V9 packets remain valid.')


if __name__ == '__main__':
    main()
