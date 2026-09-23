"""Evidence-bound exclusions of inaccurate generic ground from source rays."""
import hashlib
from pathlib import Path

def ground_exclusion(config, objects):
    record=config.get('source_projection_ground_exclusion')
    if record is None:return None
    if config.get('projection_manifest'):
        raise ValueError('Ground context exclusion currently requires an exterior-only workspace')
    if record.get('version')!=1 or record.get('asset_id')!=config['asset_id']:
        raise ValueError('Ground exclusion must name the exact receiver asset')
    if not record.get('rationale','').strip():raise ValueError('Missing ground exclusion rationale')
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if record.get('source_sha256')!=digest(config['source_path']):raise ValueError('Ground exclusion source changed')
    evidence=Path(record['evidence']).resolve(strict=True)
    if record.get('evidence_sha256')!=digest(evidence):raise ValueError('Ground exclusion evidence changed')
    name=record.get('object_name');matches=[o for o in objects if o.name==name]
    if len(matches)!=1:raise ValueError('Ground exclusion object is absent or ambiguous: '+str(name))
    obj=matches[0]
    if obj.type!='MESH' or obj.get('source_node')!='ground' or obj.get('asset_group')==config['asset_id']:
        raise ValueError('Only an exact nonreceiver generic ground mesh may be excluded')
    if len([o for o in objects if o.get('source_node')=='ground'])!=1:
        raise ValueError('Ground source node is shared; cannot exclude another object indirectly')
    if obj.hide_render:raise ValueError('Ground exclusion names an already hidden object')
    return {**record,'evidence':str(evidence),'excluded_source_node':'ground'}
