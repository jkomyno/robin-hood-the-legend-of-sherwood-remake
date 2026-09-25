"""Separate explicitly reviewed map appearances from isolated library endpoints."""
import hashlib
import json
from pathlib import Path


def partition_texture_states(item):
    children = item.get('texture_states', [])
    identifiers = [child.get('id') for child in children]
    if any(not isinstance(key, str) or not key for key in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError('Reviewed texture states require unique explicit IDs')
    roles = item.get('texture_state_roles')
    if roles is None:
        if len(children) > 1:
            raise ValueError('Multiple reviewed states require explicit publication roles')
        return children, {}
    if not isinstance(roles, dict) or set(roles) != set(identifiers):
        raise ValueError('Texture state roles must cover exactly the reviewed children')
    if sorted(roles.values()) != ['map-reveal', 'standalone-applied', 'standalone-initial']:
        raise ValueError('Explicit state roles require one map reveal and a complete isolated endpoint pair')
    by_id = {child['id']: child for child in children}
    appearances = [by_id[key] for key, role in roles.items() if role == 'map-reveal']
    endpoints = {role.removeprefix('standalone-'): by_id[key] for key, role in roles.items() if role.startswith('standalone-')}
    if any(child.get('asset_id') != item['asset_id'] for child in children):
        raise ValueError('Reviewed state roles escape parent asset ownership')
    return appearances, endpoints


def validate_texture_state_role_evidence(item):
    """Bind isolated endpoints to reviewed packet inventories, not ID spelling."""
    _appearances, endpoints = partition_texture_states(item)
    if not endpoints:
        return
    evidence = item.get('texture_state_role_evidence', {})
    path = Path(evidence.get('states_json', ''))
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != evidence.get('states_sha256'):
        raise ValueError('Explicit endpoint roles require hash-bound reviewed state evidence')
    packet = json.loads(path.read_text())
    if packet.get('asset_id') != item['asset_id'] or len(packet.get('states', [])) != 2:
        raise ValueError('Endpoint role evidence differs from parent asset or pair')
    matched = set()
    for child in endpoints.values():
        view = json.loads(Path(child['review_manifest']).read_text())
        records = [record for record in packet['states'] if record['path'] == view.get('reviewed_packet')]
        if len(records) != 1:
            raise ValueError('Endpoint is absent from reviewed packet')
        record = records[0]
        if (record['path'] in matched or record['source_sha256'] != view['source_sha256'] or
                set(record['object_names']) != set(child.get('render_object_names') or child['object_names'])):
            raise ValueError('Endpoint role inventory or source artwork differs from reviewed packet')
        matched.add(record['path'])
