"""Validate exact reproduced state evidence linked to an approved geometry revision."""
import json
from pathlib import Path
from review_evidence import sha


def validate_reconstruction(report_path, item, frames_path):
    report_path=Path(report_path).resolve(strict=True)
    report=json.loads(report_path.read_text())
    revision=item['revision'];frames_path=Path(frames_path).resolve(strict=True)
    if (report.get('status')!='PASS' or report.get('asset_id')!=item['id'] or
            report.get('geometry_revision')!=revision['sha256'] or
            report.get('model_sha256')!=revision['model_sha256']):
        raise ValueError('Reconstructed state identity differs from approved revision')
    if any(report.get(key) is not True for key in ('source_rgb_preserved','solid_pixels_preserved','ownership_buffers_reproduced')):
        raise ValueError('Reconstructed state lacks exact pixel preservation')
    if (Path(report['reviewed_state_manifest']).resolve()!=frames_path or
            sha(frames_path)!=report['reviewed_state_manifest_sha256']):
        raise ValueError('Reconstructed state manifest changed')
    bound=revision['evidence'].values()
    for key in ('primary_manifest','visibility_audit'):
        path=Path(report[key]).resolve(strict=True);digest=sha(path)
        if digest!=report[key+'_sha256'] or not any(Path(e['path']).resolve()==path and e['sha256']==digest for e in bound):
            raise ValueError('Reconstruction dependency is not directly approved: '+key)
    frames=json.loads(frames_path.read_text());primary=json.loads(Path(report['primary_manifest']).read_text())
    audit=json.loads(Path(report['visibility_audit']).read_text())
    for key in ('asset_id','scene_name','collection_name','tile_size','elevation_degrees','lighting','projection_layers','source_mask_evidence'):
        if frames.get(key)!=primary.get(key):raise ValueError('Reconstruction changed approved '+key)
    clean=lambda v:{k:x for k,x in v.items() if k not in ('counts','ownership_sha256')}
    if [clean(v) for v in frames['views']]!=[clean(v) for v in primary['views']]:
        raise ValueError('Reconstruction changed approved cameras')
    if sorted(frames['render_object_names'])!=sorted(audit['render_object_names']):
        raise ValueError('Reconstruction changed approved display selection')
    reproduced=Path(report['reconstructed_directory']).resolve(strict=True)
    expected=['solid.png','textured.png']+[f'views/view-{i}-known.png' for i in range(8)]
    if set(report['artifact_sha256'])!=set(expected):raise ValueError('Reconstruction artifacts incomplete')
    for name in expected:
        digest=report['artifact_sha256'][name]
        if sha(reproduced/name)!=digest or sha(frames_path.parent/name)!=digest:
            raise ValueError('Reproduced state pixels changed: '+name)
    return {'path':str(report_path),'sha256':sha(report_path),'record':report}
