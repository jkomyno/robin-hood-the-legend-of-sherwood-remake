"""Reusable exact-byte preflight; only fresh complete validation creates receipts."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_evidence import sha


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def code_files():
    root=Path(__file__).resolve().parent
    # All shared review/approval validators, plus the geometry snapshot helpers.
    return sorted([*root.glob('*.py'), *(root/'blender'/name for name in
        ['refinement_workspace.py','workspace_components.py','triangle_equivalence.py','stage_reviewed_publication.py'])])


def inventory(plan):
    result=[]
    for item in plan['imports']:
        result.append((item['asset_id']+'/primary',item))
        result.extend((item['asset_id']+'/state/'+child['id'],child) for child in item.get('texture_states',[]))
    if len({key for key,_ in result}) != len(result): raise ValueError('Duplicate preflight check identity')
    return result


def evidence(plan):
    files={}
    def add(path,value):
        path=str(Path(path).resolve())
        if path in files and files[path]!=value: raise ValueError('Conflicting protected file hashes')
        files[path]=value
    for _,item in inventory(plan):
        for path,value in item['protected_files'].items():add(path,value)
        add(item['blend_path'],item['blend_sha256'])
    for path,value in plan.get('protected_live_files',{}).items():add(path,value)
    for key in ['baseline','catalog','hackable_map']:
        if key in plan:add(plan[key],plan.get(key+'_sha256') or sha(Path(plan[key])))
    return files


def check_files(files):
    for index,(path,value) in enumerate(files.items(),1):
        if sha(Path(path))!=value:raise ValueError('Preflight immutable input changed: '+path)
        if index%1000==0:print('PREFLIGHT_HASHED '+str(index)+'/'+str(len(files)),flush=True)


def check_results(plan,checks):
    expected=inventory(plan)
    if len(checks)!=len(expected):raise ValueError('Preflight missing geometry check')
    for (key,item),record in zip(expected,checks):
        check=record['result']
        if (record.get('key')!=key or check.get('geometry_verified') is not True or
            check.get('model_sha256')!=item['blend_sha256'] or check.get('object_names')!=item['object_names']):
            raise ValueError('Preflight incomplete or mismatched geometry check: '+key)


def run(plan,path,validate,verify,*,runtime,validator_files=None):
    path=Path(path)
    code={str(p.resolve()):sha(p) for p in (validator_files if validator_files is not None else code_files())}
    inputs=evidence(plan)
    identity=dict(version=1,plan_sha256=digest(plan),validator_sha256=code,runtime=runtime)
    if path.exists():
        saved=json.loads(path.read_text())
        if saved.get('identity')!=identity:raise ValueError('Preflight plan, runtime or validator changed; fresh preflight required')
        if saved.get('status')!='PASS' or saved.get('evidence_sha256')!=inputs:
            raise ValueError('Preflight protected evidence inventory changed')
        check_files(inputs);check_files(code)
        check_results(plan,saved.get('checks',[]))
        print('PREFLIGHT_REUSED '+str(len(saved['checks']))+' exact checks',flush=True)
        return [record['result'] for record in saved['checks']]
    print('PREFLIGHT_INPUTS '+str(len(inputs)),flush=True)
    check_files(inputs)
    checks=[]
    for item in plan['imports']:
        validated=validate(item['geometry_manifest'],item['asset_id'],item['texture_decisions'],item['geometry_decisions'])
        for key in ('blend_path','blend_sha256','object_names','source_nodes','geometry_revision_sha256','texture_states','render_object_names'):
            if item.get(key)!=validated[key]:raise ValueError('Approved texture plan changed: '+item['asset_id']+' '+key)
        # The reusable receipt must bind every file discovered by validation.
        if any(inputs.get(str(Path(p).resolve()))!=h for p,h in validated['protected_files'].items()):
            raise ValueError('Preflight plan omits validated evidence: '+item['asset_id'])
        for key,child in inventory({'imports':[validated]}):
            checks.append(dict(key=key,result=verify(child)))
            print('PREFLIGHT_CHECK '+key,flush=True)
    check_results(plan,checks)
    check_files(inputs);check_files(code)
    saved=dict(identity=identity,status='PASS',evidence_sha256=inputs,checks=checks)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(saved,indent=2)+'\n');temporary.replace(path)
    return [record['result'] for record in checks]


def run_blender(plan,plan_path):
    import bpy
    from texture_staging import validate_texture_handoff,verify_baked_geometry
    return run(plan,Path(plan_path).with_suffix('.preflight.json'),validate_texture_handoff,verify_baked_geometry,
        runtime=dict(blender=bpy.app.version_string,build_hash=bpy.app.build_hash.decode()))


if __name__=='__main__':
    import sys
    plan_path=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
    run_blender(json.loads(plan_path.read_text()),plan_path)
