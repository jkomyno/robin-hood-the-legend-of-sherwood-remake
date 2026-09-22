"""Render explicit animation endpoint selections with immutable worker cameras."""
import copy
import hashlib
import json
from pathlib import Path


def render_endpoints(workspace, output, definitions, selections, sources):
    """Definitions map endpoint labels to disjoint source projection layers.

    The caller owns geometry visibility and projection semantics. Each selection
    names the complete displayed asset for that endpoint, including its shell.
    """
    import bpy
    from refinement_review import render_review
    from refinement_workspace import _validated_masks, _validated_projection
    workspace, output = Path(workspace).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    config = json.loads((workspace/'workspace.json').read_text())
    _validated_projection(config)
    evidence = _validated_masks(config)
    framing = json.loads((workspace/'input/views.json').read_text())
    records = []
    for label, names in selections.items():
        source = Path(sources[label]).resolve(strict=True)
        frame = copy.deepcopy(framing)
        frame['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        selected = [bpy.data.objects[name] for name in names]
        hidden = {obj: obj.hide_render for obj in selected}
        try:
            for obj in selected:
                obj.hide_render = False
            result = render_review(output/label, scene_name=config['scene_name'],
                collection_name=config['collection_name'], asset_id=config['asset_id'],
                source_path=source, frame_manifest=frame,
                projection_layers=definitions[label], render_object_names=names,
                source_mask_manifest=config['source_mask_manifest'],
                allow_projection_revision=True, allow_mask_revision=True)
        finally:
            for obj, value in hidden.items():
                obj.hide_render = value
        records.append({'state': label, 'path': str(output/label),
                        'source_sha256': frame['source_sha256'],
                        'object_names': result['object_names']})
    report = {'version': 1, 'asset_id': config['asset_id'], 'states': records,
              'framing_sha256': hashlib.sha256((workspace/'input/views.json').read_bytes()).hexdigest(),
              'mask_evidence': evidence, 'user_approval': 'pending',
              'limitations': ['Discrete visible endpoints; intermediate 3D motion and collision are not inferred.']}
    (output/'states.json').write_text(json.dumps(report, indent=2)+'\n')
    return report
