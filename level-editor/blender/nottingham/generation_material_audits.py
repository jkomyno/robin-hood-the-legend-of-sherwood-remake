"""Inventory and audit exact approved saved materials without modifying workers."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from build_gallery import sha, read, require


def matches(path, row):
    try:
        audit=read(path)
        require(audit.get('status')=='STRUCTURAL-PASS' and not audit.get('problems'), 'Material problems')
        require(audit.get('asset_id')==row['asset_id'], 'Material asset differs')
        require(audit.get('model_sha256')==row.get('saved_state_model_sha256'), 'Material model differs')
        require(audit.get('frame_manifest_sha256')==row['frame_manifest_sha256'], 'Material frame differs')
        names=read(row['frame_manifest'])['object_names']
        require(set(audit.get('render_object_names',[]))==set(names), 'Material scope differs')
        artifacts=audit['artifact_sha256']
        require({'materials.png',*[f'view-{i}.png' for i in range(8)]}<=set(artifacts), 'Missing actual material views')
        for name,digest in artifacts.items():
            require(sha(Path(path).parent/name)==digest, 'Material render changed')
        return True
    except (ValueError,KeyError,OSError):
        return False


def output_for(row):
    # Frame digest prevents collisions between covered/revealed camera packets.
    return WORK/'texture-generation/material-audits'/row['asset_id']/row['frame_manifest_sha256'][:16]


def existing(row):
    candidates=list(Path(row['workspace']).glob('inspection/**/audit.json'))
    candidates += list((WORK/'texture-generation/state-proof'/row['asset_id']).glob('**/audit.json'))
    generated=output_for(row)/'audit.json'
    if generated.exists():candidates.insert(0,generated)
    return next((p for p in candidates if matches(p,row)),None)


def run_loaded(row):
    """Run after the caller opens the exact model, before lighting mutates state."""
    import bpy
    frame=Path(row['frame_manifest']);model=Path(row['saved_state_model'])
    require(sha(model)==row['saved_state_model_sha256'], 'Approved model changed')
    require(sha(frame)==row['frame_manifest_sha256'], 'Approved frame changed')
    require(Path(bpy.data.filepath).resolve()==model.resolve(), 'Wrong model loaded for material audit')
    prior=existing(row)
    if prior:return str(prior)
    destination=output_for(row)
    require(not destination.exists(), 'Incomplete audit exists; inspect it before retrying')
    sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
    from audit_stored_materials import run
    scene=bpy.context.window.scene
    try:
        report=run(row['workspace'],destination,render=True,export=False,
                   render_object_names=read(frame)['object_names'],frame_manifest=frame,
                   model_path=model,use_loaded=True)
    finally:
        bpy.context.window.scene=scene
    require(report['status']=='STRUCTURAL-PASS', 'Saved material audit failed')
    require(matches(destination/'audit.json',row), 'Material audit binding failed')
    return str(destination/'audit.json')


def inventory(output):
    data=read(WORK/'texture-generation/lighting-audit/audit.json')
    rows=[r for r in data['packets'] if any(k!='primary' and not k.endswith('-full-height') for k in r['roles'])]
    jobs=[]
    for row in rows:
        job=dict(row)
        prior=existing(row) if row.get('saved_state_model') else None
        job.update(material_audit=str(prior) if prior else None,
                   material_audit_status='PASS' if prior else 'awaiting-state-proof' if not row.get('saved_state_model') else 'missing',
                   material_audit_output=str(output_for(row)))
        jobs.append(job)
    report={'version':1,'jobs':jobs,'missing_frames':sum(r['material_audit_status']=='missing' for r in jobs),
            'missing_assets':len({r['asset_id'] for r in jobs if r['material_audit_status']=='missing'}),
            'waiting_state_frames':sum(r['material_audit_status']=='awaiting-state-proof' for r in jobs)}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='jobs'}))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    parser.add_argument('--run',action='store_true',help='Run missing audits inside Blender')
    parser.add_argument('--asset',action='append')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
    jobs=inventory(args.output)
    if args.run:
        import bpy
        from render_slots import acquire
        acquire()
        for row in jobs['jobs']:
            if row['material_audit_status']!='missing' or (args.asset and row['asset_id'] not in args.asset):continue
            bpy.ops.wm.open_mainfile(filepath=row['saved_state_model'])
            print('MATERIAL-AUDIT',row['asset_id'],run_loaded(row),flush=True)
        inventory(args.output)
