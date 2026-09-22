"""Intersect native bridge masks with exact endpoint sprite alpha authority.

This removes neighboring tower pixels retained by broad runtime occlusion masks.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops

ROOT=Path('level-editor/work/leicester-refinement').resolve()
NATIVE=Path('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.d/masks/manifest.json').resolve()
PAIRS={'leicester-east-moat-drawbridge':(1,388,389,449,443),
       'leicester-east-village-drawbridge':(8,387,384,437,441),
       'leicester-south-drawbridge':(10,391,390,458,455)}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    native=json.loads(NATIVE.read_text());statespath=ROOT/'bridge-evidence/native-states/states.json';states=json.loads(statespath.read_text())
    out=ROOT/'bridge-evidence/endpoint-ownership';out.mkdir(exist_ok=True)
    evidence=[]
    for asset,(patch,initial,applied,old,new) in PAIRS.items():
        record=next(p for p in states['patches'] if p['id']==f'patch-{patch:03}')
        for state,index,node in [('initial',old,initial),('applied',new,applied)]:
            entry=native['masks'][index];graphic=record[state+'_graphic'];framebase=statespath.parent/f'patch-{patch:03}'
            native_png=NATIVE.parent/entry['png'];alpha_png=framebase/graphic['alpha']
            mask=Image.open(native_png).convert('L');alpha=Image.open(alpha_png).convert('L')
            offset=(graphic['bbox'][0]-entry['box_top_left'][0],graphic['bbox'][1]-entry['box_top_left'][1])
            local=Image.new('L',mask.size);local.paste(alpha,offset)
            protected=ImageChops.multiply(mask,local)
            bitmap=out/f'{asset}-{state}.png';protected.save(bitmap)
            derived_index=20000+patch*2+(state=='applied')
            records=[dict(r,png=str(NATIVE.parent/r['png'])) if r.get('png') else r for r in native['masks']]
            derivation={'native_mask_index':index,'native_mask_sha256':sha(native_png),'endpoint_alpha':str(alpha_png),
                        'endpoint_alpha_sha256':sha(alpha_png),'endpoint_frame':graphic,'operation':'native opacity AND endpoint sprite opacity',
                        'native_pixels':sum(v>0 for v in mask.getdata()),'accepted_pixels':sum(v>0 for v in protected.getdata())}
            records.append(dict(entry,index=derived_index,png=str(bitmap),ownership_derivation=derivation))
            inv=out/f'{asset}-{state}-inventory.json';inv.write_text(json.dumps({'version':1,'source':str(NATIVE),'source_sha256':sha(NATIVE),'masks':records},indent=2)+'\n')
            source=framebase/f'{state}-map.png'
            manifest={'version':1,'mask_inventory':str(inv),'projections':{'exterior':{'source_sha256':sha(source),
              'state':f'patch-{patch:03} {state} independently composed native endpoint',
              'assignments':[{'source_node':f'building-{node:03}','mask_indices':[derived_index],'reviewed':True,
                 'review_reason':'Native leaf mask intersected with the selected endpoint sprite alpha; neighboring tower pixels outside the sprite are rejected.'}]}}}
            target=out/f'{asset}-{state}-masks.json';target.write_text(json.dumps(manifest,indent=2)+'\n')
            evidence.append({'asset':asset,'state':state,'manifest':str(target),'source_sha256':sha(source),'derived_mask_sha256':sha(bitmap),**derivation})
    (out/'validation.json').write_text(json.dumps({'status':'PASS','endpoint_manifest_sha256':sha(statespath),'records':evidence},indent=2)+'\n')
    print(json.dumps([{'asset':r['asset'],'state':r['state'],'accepted':r['accepted_pixels'],'rejected':r['native_pixels']-r['accepted_pixels']} for r in evidence]))

if __name__=='__main__':main()
