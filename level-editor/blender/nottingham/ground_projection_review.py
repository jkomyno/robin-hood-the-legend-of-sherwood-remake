"""Strict gallery validation for the shared, evidenced ground-only exclusion."""
import hashlib
from pathlib import Path

def validate(config, before, after):
    def require(ok,message):
        if not ok:raise ValueError(message)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record=config['source_projection_ground_exclusion']
    require(not config.get('projection_manifest'),'Ground exclusion cannot accompany layered projection')
    require(record.get('version')==1 and record.get('asset_id')==config['asset_id'],'Ground exclusion identity differs')
    require(bool(record.get('rationale','').strip()),'Ground exclusion lacks rationale')
    # This map's immutable import names its single generic ground mesh here.
    # It must remain a protected nonreceiver object in the baseline snapshot.
    name=config['map_name']+' Terrain'
    require(record.get('object_name')==name and name in config['outside_geometry'],'Ground exclusion is not the protected map terrain')
    require('ground' not in config['part_ids'],'Ground cannot be a receiver exclusion')
    require(record.get('source_sha256')==sha(config['source_path']),'Ground exclusion source changed')
    evidence=Path(record['evidence']).resolve(strict=True)
    require(record.get('evidence_sha256')==sha(evidence),'Ground exclusion evidence changed')
    require(len(before)==len(after)==1,'Ground exclusion requires one exterior layer')
    original=before[0]
    require(original.get('projection_label')=='exterior','Ground exclusion requires exterior projection')
    require(not original.get('ground_context_exclusion'),'Frozen layer already has an exclusion')
    require(original.get('source_path')==str(Path(config['source_path']).resolve()),'Ground layer source differs')
    require(original['occluder_nodes'].count('ground')==1,'Frozen layer must have exactly one ground node')
    require(set(config['part_ids'])<=set(original['receiver_nodes']),'Frozen receivers omit owned parts')
    expected={**original,'receiver_nodes':sorted(config['part_ids']),
              'occluder_nodes':sorted(n for n in original['occluder_nodes'] if n!='ground'),
              'ground_context_exclusion':{**record,'evidence':str(evidence),'excluded_source_node':'ground'}}
    require(after==[expected],'Ground exclusion changed other layers, receivers or foreground occluders')
    return expected['ground_context_exclusion']
