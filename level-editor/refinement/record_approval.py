"""Record explicit user approval, bound to the reviewed model and image hashes."""
import argparse
import hashlib
import json
from pathlib import Path


def record(manifest_path, asset_ids, decision):
    path = Path(manifest_path).resolve(strict=True)
    data = json.loads(path.read_text())
    items = {item['id']: item for item in data['items']}
    missing = set(asset_ids) - items.keys()
    if missing:
        raise ValueError(f'Unknown assets: {sorted(missing)}')
    for asset_id in asset_ids:
        item = items[asset_id]
        hashes = {}
        for key in ('model', 'solid', 'textured'):
            source = Path(item[key])
            if not source.is_absolute():
                source = path.parent / source
            hashes[key] = hashlib.sha256(source.read_bytes()).hexdigest()
        item.update(status='approved', user_approval='Approved: ' + decision,
                    approved_sha256=hashes,
                    ai_texture='Authorized by recorded user decision; generation pending')
    path.write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('asset_ids', nargs='+')
    parser.add_argument('--decision', required=True, help='Actual user decision and scope; never invent approval')
    args = parser.parse_args()
    record(args.manifest, args.asset_ids, args.decision)
