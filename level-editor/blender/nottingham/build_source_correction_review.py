"""Build an isolated source-correction gallery from separate snapshot decisions.

Populate source-correction-review/workspace-overrides.json and approvals.json
first. This never updates the map's original overrides or user approvals.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def enrich(item):
    workspace=Path(item['workspace']).resolve()
    candidate=json.loads((workspace/'candidate.json').read_text())
    relative=candidate.get('stored_material_evidence')
    if not relative:
        raise ValueError('Ready correction lacks actual saved-material evidence: '+item['id'])
    audit_path=(workspace/relative).resolve()
    if not audit_path.is_relative_to(workspace):raise ValueError('Audit escaped workspace')
    audit=json.loads(audit_path.read_text())
    frames=json.loads((workspace/'modified/views.json').read_text())
    if (audit.get('status') not in ('PASS','STRUCTURAL-PASS') or audit.get('problems') or
        audit.get('asset_id')!=item['id'] or audit.get('model_sha256')!=sha(workspace/'model.blend') or
        audit.get('frame_manifest_sha256')!=sha(workspace/'modified/views.json') or
        audit.get('render_object_names')!=(frames.get('render_object_names') or frames['object_names'])):
        raise ValueError('Actual saved-material audit binding failed: '+item['id'])
    required={'materials.png',*(f'view-{i}.png' for i in range(8))}
    artifacts=audit.get('artifact_sha256',{})
    if not required <= artifacts.keys():raise ValueError('Actual material audit lacks all eight views')
    for name in required:
        path=(audit_path.parent/name).resolve()
        if not path.is_relative_to(workspace) or sha(path)!=artifacts[name]:
            raise ValueError('Actual material image changed: '+name)
    item.update(stored_material_textured=str(audit_path.parent/'materials.png'),stored_material_audit=str(audit_path))
    item['notes'].append('This corrected revision requires a new decision. Previous geometry and texture approvals do not approve this revision; texture generation remains on hold.')
    return item


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=WORK/'source-correction-review')
    parser.add_argument('--reuse-collected',action='store_true',help='Enrich the already validated collector snapshot without collecting again')
    args=parser.parse_args();root=args.root.resolve();output=root/'gallery'
    snapshots=[WORK/'workspace-overrides.json',WORK/'approvals.json']
    before={str(p):sha(p) for p in snapshots}
    if not args.reuse_collected:
        subprocess.run([sys.executable,str(Path(__file__).with_name('build_gallery.py')),
            '--workspace-map',str(root/'workspace-overrides.json'),'--approvals',str(root/'approvals.json'),
            '--output',str(output)],check=True)
    manifest=root/'gallery-candidates.json';data=json.loads(manifest.read_text())
    for item in data['items']:
        if item['status']=='ready-for-user' and item.get('user_approval')!='approved':enrich(item)
    enriched=root/'gallery-source-candidates.json';enriched.write_text(json.dumps(data,indent=2)+'\n')
    path=ROOT/'level-editor/refinement/blender/build_review_gallery.py'
    spec=importlib.util.spec_from_file_location('shared_source_gallery',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.build(enriched,output,pending_only=True,map_name='Nottingham source correction')
    if before!={str(p):sha(p) for p in snapshots}:raise ValueError('Original map approval or overrides changed during isolated build')
    print(json.dumps({'gallery':str(output/'index.html'),'original_records_unchanged':True}))


if __name__=='__main__':main()
