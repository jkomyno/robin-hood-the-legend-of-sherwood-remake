"""Verify a saved camera repair changes only its explicit formerly unfilled taps."""
import sys,io,json,hashlib
from pathlib import Path
import numpy as np
import bpy
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
from reconstruct_hall_generated_states import read,write,sha,image_binding

def pixels(path,name,slot):
    bpy.ops.wm.open_mainfile(filepath=str(path));image,_=image_binding(bpy.data.objects[name],slot)
    return np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1].copy(),hashlib.sha256(image.packed_file.data).hexdigest()

def main(before,after):
    old=read(before/'provenance.json');new=read(after/'provenance.json');repair=read(after/'camera-repair.json');assert sha(before/'model.blend')==old['model_sha256'];assert sha(after/'model.blend')==new['model_sha256']==repair['model_sha256'];name=next(iter(repair['scope']));row=next(r for r in old['objects'] if r['object']==name);other=next(r for r in new['objects'] if r['object']==name);a,ah=pixels(before/'model.blend',name,row['material_slot']);b,bh=pixels(after/'model.blend',name,other['material_slot']);flags=np.load(row['texel_provenance']['path'])['ownership'];allowed=np.zeros(flags.shape,bool)
    for r in repair['repairs']:
        x,y=r['atlas'];assert flags[y,x]==0;allowed[y,x]=True;assert np.array_equal(b[y,x,:3],r['rgb8'])
    assert np.array_equal(a[~allowed],b[~allowed]) and np.array_equal(a[:,:,3],b[:,:,3]);out=dict(status='PASS',before_model_sha256=old['model_sha256'],model_sha256=new['model_sha256'],before_image_sha256=ah,image_sha256=bh,repair_report_sha256=sha(after/'camera-repair.json'),exact_repair_texels=int(allowed.sum()),all_other_rgba_exact=True,all_alpha_exact=True,old_nonrepair_rgba_sha256=hashlib.sha256(a[~allowed].tobytes()).hexdigest());write(after/'camera-repair-preservation.json',out);print(json.dumps(out))
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(*(Path(p).resolve() for p in a))
