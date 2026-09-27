"""Publish the exact derived models checked by the browser visual audit.

Existing source assets and scenes are never rewritten. Run build_segments.py,
then render-audit.mjs --segments --force, and inspect the comparison images first.
"""
import json
import shutil

from build_segments import ROOT, LIB, STAGE, sha, write_asset_index


def publish():
    rows = json.loads((ROOT / 'work/wall-presets/segments.json').read_text())
    entries = {entry['id']: entry for entry in json.loads((LIB / 'index.json').read_text())['assets']}
    for row in rows:
        folder = STAGE / row['id']
        audit = json.loads((ROOT / f"work/wall-presets/segments/{row['id']}.json").read_text())
        if audit.get('model_sha256') != sha(folder / 'model.glb') or not audit.get('vertices'):
            raise ValueError(f"Missing or stale visual audit: {row['id']}")
        if any(audit.get(key) != value for key, value in row.items()):
            raise ValueError(f"Preset parameters changed since visual audit: {row['id']}")
        descriptor = json.loads((folder / 'asset.json').read_text())
        provenance = descriptor['provenance']
        source = entries[row['source']]
        if provenance['model_sha256'] != sha(LIB / source['model']):
            raise ValueError(f"Source model changed during review: {row['source']}")
        if provenance['descriptor_sha256'] != sha(LIB / source['descriptor']):
            raise ValueError(f"Source descriptor changed during review: {row['source']}")
    # All inputs pass before any output is replaced.
    for row in rows:
        target = LIB / row['id']
        target.mkdir(exist_ok=True)
        for name in ['model.glb', 'asset.json']:
            shutil.copy2(STAGE / row['id'] / name, target / name)
    write_asset_index(LIB)
    fields = {'name', 'asset', 'width', 'repeatLength', 'axis', 'sourceAngle',
              'sourceStraight', 'sourceStart', 'sourceEnd', 'source_map',
              'cornerAsset', 'cornerScale', 'cornerMinAngle'}
    catalog = [{key: value for key, value in row.items() if key in fields} for row in rows]
    (ROOT / 'app/src/assets/wall-presets.json').write_text(json.dumps(catalog, indent=2) + '\n')
    print(f"Published {len(rows)} reviewed copies; original assets and scenes unchanged.")


if __name__ == '__main__':
    publish()
