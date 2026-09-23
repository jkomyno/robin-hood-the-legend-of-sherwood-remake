"""Review separately baked endpoint workers as one revision-bound asset."""
import json
import re
from pathlib import Path
from review_evidence import material_evidence, sha


def load_endpoint_mapping(path, known_ids):
    if path is None:
        return {}
    path = Path(path).resolve(strict=True)
    data = json.loads(path.read_text())
    if data.get('version') != 1 or not isinstance(data.get('groups'), list):
        raise ValueError('Expected endpoint mapping version 1 with groups')
    result = {}
    for group in data['groups']:
        asset = group.get('asset_id')
        if asset not in known_ids or asset in result:
            raise ValueError('Unknown or duplicate endpoint asset')
        states = group.get('states', {})
        if set(states) != {'initial', 'applied'}:
            raise ValueError('Endpoint review requires initial and applied workers')
        records = []
        for state in ('initial', 'applied'):
            value = states[state]
            location = value.get('worker')
            if not isinstance(location, str) or not location.strip():
                raise ValueError('Endpoint worker path is required')
            digest = value.get('model_sha256')
            if digest is not None and not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('Invalid endpoint model hash')
            records.append({'id': state, 'workspace': (path.parent / location).resolve(),
                            'expected_model_sha256': digest})
        if records[0]['workspace'] == records[1]['workspace']:
            raise ValueError('Paired endpoint workers must be distinct')
        result[asset] = records
    return result


def endpoint_evidence(records, asset_id, map_name):
    """Retain available evidence and fail readiness for any incomplete endpoint."""
    endpoints, evidence, errors = [], {}, []
    for record in records:
        state, workspace = record['id'], record['workspace']
        prefix = 'endpoint_' + state
        local_errors = []
        item = {'id': state, 'workspace': str(workspace)}
        def file(key, relative):
            target = (workspace / relative).resolve()
            if not target.is_relative_to(workspace):
                local_errors.append('evidence escapes worker: ' + key)
                return None
            if not target.is_file():
                local_errors.append('missing ' + relative)
                return None
            evidence[prefix + '_' + key] = target
            item[key] = str(target)
            return target
        def document(key, relative):
            target = file(key, relative)
            if target:
                try:
                    value = json.loads(target.read_text())
                    if isinstance(value, dict):
                        return value
                except (ValueError, OSError):
                    pass
                local_errors.append('invalid JSON object: ' + relative)
            return {}
        config = document('workspace_config', 'workspace.json')
        if config.get('asset_id') != asset_id or config.get('map_name') != map_name:
            local_errors.append('worker identity differs from catalog asset')
        handoff = document('handoff', 'handoff.json')
        if handoff.get('status') != 'ready-for-user' or not handoff.get('all_eight_views_inspected'):
            local_errors.append('endpoint worker review is not ready')
        if handoff.get('endpoint_state') != state:
            local_errors.append('handoff endpoint state differs from mapping')
        for key, relative in [('model', 'model.blend'), ('solid', 'modified/solid.png'),
                              ('textured', 'modified/textured.png'), ('context', 'input/context.png'),
                              ('review', 'review.md')]:
            file(key, relative)
        for key in ('recipe', 'ownership'):
            relative = handoff.get(key)
            if not isinstance(relative, str) or not relative:
                local_errors.append('missing ' + key + ' declaration')
            else:
                file(key, relative)
        validation = document('validation', 'validation.json')
        if validation.get('status') != 'PASS':
            local_errors.append('endpoint validation is not PASS')
        frames = document('frames', 'modified/views.json')
        views = frames.get('views', [])
        if not isinstance(views, list) or sorted(v.get('index', -1) for v in views if isinstance(v, dict)) != list(range(8)):
            local_errors.append('endpoint requires all eight frozen views')
        model_hash = sha(Path(item['model'])) if item.get('model') else None
        item['model_sha256'] = model_hash
        for expected in (record.get('expected_model_sha256'), handoff.get('model_sha256')):
            if expected is not None and expected != model_hash:
                local_errors.append('declared endpoint model hash is stale')
        audit_path = workspace / 'inspection/stored-materials/audit.json'
        try:
            files, issues, _ = material_evidence(workspace, audit_path,
                workspace / 'modified/views.json', model_hash, prefix + '_stored_material')
        except (ValueError, OSError, TypeError) as exc:
            files, issues = {}, ['invalid endpoint material evidence: ' + str(exc)]
        evidence.update(files)
        local_errors.extend(issues)
        for key, path in [('stored_material_audit', audit_path),
                          ('stored_material_textured', audit_path.parent / 'materials.png'),
                          ('stored_material_glb', audit_path.parent / 'asset.glb')]:
            if path.is_file():
                item[key] = str(path)
        item['errors'] = local_errors
        item['status'] = 'ready-for-user' if not local_errors else 'validation-pending'
        endpoints.append(item)
        errors.extend(state + ': ' + error for error in local_errors)
    return endpoints, evidence, errors
