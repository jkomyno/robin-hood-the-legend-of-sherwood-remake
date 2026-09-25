"""Compare actual saved covered/revealed shared completion bytes exactly."""
import sys,io,json,hashlib
from pathlib import Path
import numpy as np
import bpy
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
from reconstruct_hall_generated_states import read,write,sha,image_binding

def load(folder):
    report=read(folder/'provenance.json');assert sha(folder/'model.blend')==report['model_sha256'];bpy.ops.wm.open_mainfile(filepath=str(folder/'model.blend'));result={}
    for row in report['objects']:
        p=row['texel_provenance'];assert sha(p['path'])==p['sha256'];image,uv=image_binding(bpy.data.objects[row['object']],row['material_slot']);assert hashlib.sha256(image.packed_file.data).hexdigest()==p['packed_image_sha256'];assert hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest()==p['uv_sha256'];arrays=np.load(p['path']);result[row['object']]=dict(pixels=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1].copy(),ownership=arrays['ownership'].copy(),donor=arrays['donor_state'].copy(),uv=p['uv_sha256'])
    return report,result

def main(covered,revealed):
    c,ca=load(covered);r,ra=load(revealed);rows=[]
    for name,a in ra.items():
        if name not in ca:continue
        b=ca[name];assert a['uv']==b['uv'];shared=(a['ownership']==2)&(a['donor']==1)&(b['ownership']==2);count=int(shared.sum());mismatch=int(np.any(a['pixels'][shared]!=b['pixels'][shared],axis=1).sum());assert mismatch==0;rows.append(dict(object=name,shared_completion_texels=count,mismatches=mismatch))
    report=dict(status='PASS',covered_model_sha256=c['model_sha256'],revealed_model_sha256=r['model_sha256'],covered_provenance_sha256=sha(covered/'provenance.json'),revealed_provenance_sha256=sha(revealed/'provenance.json'),objects=rows,shared_completion_texels=sum(row['shared_completion_texels'] for row in rows),mismatches=0);write(revealed/'shared-completion-audit.json',report);print(json.dumps({k:v for k,v in report.items() if k!='objects'}))
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(*(Path(p).resolve() for p in a))
