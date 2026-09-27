"""Prevent unreviewed source ownership from entering Sherwood synthesis."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_validated_source(record):
    binding = record.get('source_ownership_validation')
    if not isinstance(binding, dict) or not binding.get('path') or not binding.get('sha256'):
        raise ValueError('Native-mask source ownership has not been validated; rebuild the source packet')
    path = Path(binding['path'])
    if sha(path) != binding['sha256']:
        raise ValueError('Source ownership validation changed')
    validation = json.loads(path.read_text())
    if (validation.get('status') != 'PASS'
            or validation.get('unresolved_source_nodes') != 0
            or validation.get('unconstrained_receivers') != 0
            or validation.get('worker_sha256') != record.get('worker_sha256')):
        raise ValueError('Source ownership is incomplete or belongs to a different worker')
    evidence = validation.get('evidence')
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError('Source ownership validation has no bound evidence')
    for filename, expected in evidence.items():
        if sha(filename) != expected:
            raise ValueError('Source ownership evidence changed: '+filename)
    return binding
