"""Bind a texture bake to the approved source blend and exact mesh geometry.

Run in Blender with -- <packet/views.json> <baked/worker.blend> <report.json>.
This checks current source-mask evidence as well as the retained approval hash.
"""
import hashlib
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refinement_workspace import _geometry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(packet_path, worker_path, output):
    packet_path=Path(packet_path);worker_path=Path(worker_path)
    packet=json.loads(packet_path.read_text())
    approval=json.loads((packet_path.parent/'approval.json').read_text())
    if approval['status']!='approved':raise ValueError('Packet is not approved')
    if sha(packet['source_blend'])!=approval['geometry_revision']:
        raise ValueError('Approved source blend changed')
    if packet['geometry_revision']!=approval['geometry_revision']:
        raise ValueError('Packet names another geometry revision')
    if sha(packet_path.parent/'input.png')!=approval['input_sha256']:
        raise ValueError('Approved input changed')
    evidence=packet.get('source_mask_evidence',{})
    for path,expected in evidence.items():
        if sha(path)!=expected:raise ValueError('Source-mask evidence changed: '+path)
    names=packet.get('texture_receiver_object_names',packet['object_names'])
    if not names:raise ValueError('Empty approved mesh scope')
    bpy.ops.wm.open_mainfile(filepath=packet['source_blend'])
    before={name:_geometry(bpy.data.objects[name]) for name in names}
    bpy.ops.wm.open_mainfile(filepath=str(worker_path.resolve(strict=True)))
    after={name:_geometry(bpy.data.objects[name]) for name in names}
    if before!=after:raise ValueError('Baked geometry differs from approved model')
    report={'status':'PASS','approved_source_sha256':approval['geometry_revision'],
            'baked_worker_sha256':sha(worker_path),'meshes':before,'mask_evidence_files':len(evidence),
            'packet_sha256':sha(packet_path)}
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','meshes':len(names),'mask_evidence_files':len(evidence)}))


if __name__=='__main__':verify(*sys.argv[sys.argv.index('--')+1:])
