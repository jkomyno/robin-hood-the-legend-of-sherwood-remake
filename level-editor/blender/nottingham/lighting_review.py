"""Validate supplemental map lighting without rewriting frozen source packets."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_lighting_review(workspace, evidence, profile):
    workspace = Path(workspace).resolve()
    path = workspace / 'lighting-review/review.json'
    if not path.exists():
        return None, {}
    report = json.loads(path.read_text())
    def require(condition, message):
        if not condition:
            raise ValueError('Lighting review: ' + message)
    require(report.get('version') == 1 and report.get('status') == 'PASS', 'unfinished report')
    require(report.get('asset_id') == evidence['asset_id'], 'asset differs')
    require(report.get('model_sha256') == evidence['model_sha256'], 'model changed')
    require(report.get('modified_views_sha256') == evidence['packet_hashes']['modified']['views.json'], 'packet changed')
    require(report.get('lighting_config_sha256') == sha(profile), 'map lighting changed')
    config = json.loads(Path(profile).read_text())
    require(report.get('lighting') == config['lighting'], 'settings differ from map profile')
    states = evidence['state_packets']
    primary = Path(states['covered']['directory']) if 'covered' in states else workspace / 'modified'
    expected = {str((primary / 'solid.png').resolve())}
    expected.update(str((Path(v['directory']) / 'solid.png').resolve()) for k, v in states.items()
                    if k == 'revealed' or k.startswith('animation-'))
    replacements = {}
    for packet in report.get('packets', []):
        original = Path(packet['original_solid']).resolve()
        frame = Path(packet['frame_manifest']).resolve()
        solid = Path(packet['solid']).resolve()
        source_blend = Path(packet['source_blend']).resolve()
        require(original.is_relative_to(workspace) and frame == original.parent / 'views.json', 'foreign frame path')
        require(solid.is_relative_to(path.parent), 'image outside supplemental directory')
        require(source_blend.is_relative_to(workspace), 'state model outside workspace')
        require(sha(source_blend) == packet['source_blend_sha256'], 'state model changed')
        require(sha(original) == packet['original_solid_sha256'], 'original solid changed')
        require(packet.get('inspected_views') == list(range(8)), 'eight-view inspection incomplete')
        require(sha(frame) == packet['frame_manifest_sha256'], 'frame manifest changed')
        require(sha(solid) == packet['solid_sha256'], 'solid image changed')
        require(str(original) not in replacements, 'duplicate solid replacement')
        replacements[str(original)] = str(solid)
    require(expected <= replacements.keys(), 'displayed state missing supplemental lighting')
    return {'path': str(path), 'sha256': sha(path), 'lighting_config_sha256': sha(profile)}, replacements
