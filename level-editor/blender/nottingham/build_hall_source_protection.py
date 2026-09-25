"""Bind final approved hall atlas protection to exact historical source replay."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import bpy
sys.path.insert(0,str(Path(__file__).parent))
from reconstruct_hall_generated_states import image_binding,sha,read,write
CAP='building-505__castle-hall-northwest-contact'

def main(workspace,state,replay,out):
    verification=read(replay/'verification.json')
    rows=read(replay/'replay.json')['objects'];old={r['object']:r['texel_provenance'] for r in rows if 'texel_provenance' in r}
    recovery=verification.get('historical_source_recovery',{})
    if '--replay-supplement' in sys.argv:
        supplement=Path(sys.argv[sys.argv.index('--replay-supplement')+1]).resolve();extra=read(supplement/'verification.json')
        assert extra['original_model_sha256']==verification['original_model_sha256'] and extra['status'] in ('PASS','PASS-PRESERVED-HISTORICAL-SOURCE')
        recovery.update(extra.get('historical_source_recovery',{}))
    assert all(n in recovery and recovery[n]['count']==recovery[n]['source_rgb_exact'] for n in verification['mismatches'])
    binding=next(s for s in read(workspace/'inspection/state-models/manifest.json')['states'] if s['state']==state)
    assert sha(binding['model'])==binding['model_sha256'];proof=read(binding['preservation_report'])
    wall=proof['wall_source_restoration'];assert sha(wall['report'])==wall['report_sha256'];repair=read(wall['report'])
    cap_report=read(workspace/'inspection/state-models/covered/inspection/cap-provenance/replay.json')['objects'][0]['texel_provenance']
    bpy.ops.wm.open_mainfile(filepath=binding['model']);bpy.context.view_layer.update();out.mkdir(parents=True,exist_ok=False);result=[]
    for name in binding['object_names']:
        obj=bpy.data.objects[name]
        slots={f.material_index for f in obj.data.polygons}
        if not slots:continue
        assert len(slots)==1,'Multiple source atlas bindings need explicit per-face replay: '+name
        slot=next(iter(slots));image,uv=image_binding(obj,slot);packed=hashlib.sha256(image.packed_file.data).hexdigest();uvhash=hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest()
        entry=cap_report if name==CAP else old[name];assert sha(entry['path'])==entry['sha256'];assert uvhash==entry['uv_sha256'];flags=np.load(entry['path'])['ownership'].copy()
        recovered=recovery.get(name)
        original_hash=entry['packed_image_sha256']
        if recovered:
            assert sha(recovered['path'])==recovered['sha256'];flags[np.load(recovered['path'])['protected']]=1
            original_hash=recovered['original_packed_image_sha256']
        padding=[]
        if obj.get('source_node')=='building-504' and not obj.get('projection_component'):
            assert packed==wall['packed_image_sha256'] and original_hash==wall['original_packed_image_sha256']
            assert len(repair['changes'])==3162 and len(repair['edge_padding'])==24
            for row in repair['changes']:
                x,y=row['atlas'];flags[y,x]=1
            for row in repair['edge_padding']:
                x,y=row['target'];flags[y,x]=1;padding.append([x,y])
        else:assert packed==original_hash,name
        path=out/f'{len(result):03}.npz';np.savez_compressed(path,ownership=flags)
        result.append(dict(object=name,slot=slot,path=str(path),sha256=sha(path),packed_image_sha256=packed,uv_sha256=uvhash,
            source_replay_path=str(replay/'verification.json'),source_replay_sha256=sha(replay/'verification.json'),approved_source_padding=padding,historical_source_recovery=recovered))
    write(out/'protection.json',dict(status='PASS',state=state,model_sha256=binding['model_sha256'],objects=result,wall_restoration=wall))
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(Path(a[0]).resolve(),a[1],Path(a[2]).resolve(),Path(a[3]).resolve())
