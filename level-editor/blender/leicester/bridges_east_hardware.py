"""Trace endpoint-owned east bridge chains with explicitly inferred depth."""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from bridges import COSINE, SINE, FACES, object_mesh

ROOT = Path('level-editor/work/leicester-refinement').resolve()
TAG = 'leicester-east-chain-v1'

def pixels(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    w,h = image.size
    values = list(image.pixels)
    bpy.data.images.remove(image)
    return w,h,values

def refine_hardware(workspace, asset_id, state):
    if asset_id == 'leicester-south-drawbridge':
        return None
    patch,initial,applied = (1,388,389) if asset_id == 'leicester-east-moat-drawbridge' else (8,387,384)
    indices = ([451,450] if state=='initial' else [444,445]) if patch==1 else ([] if state=='initial' else [440,439])
    config=json.loads((workspace/'workspace.json').read_text())
    collection=bpy.data.collections[config['collection_name']]
    for obj in list(collection.all_objects):
        if obj.get('bridge_east_hardware')==TAG and obj.get('asset_group')==asset_id:
            bpy.data.objects.remove(obj,do_unlink=True)
    active=initial if state=='initial' else applied
    template=next(o for o in collection.all_objects if o.type=='MESH' and o.get('source_node')==f'building-{active:03}' and o.get('asset_group')==asset_id)
    nativepath=Path('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json')
    native=json.loads(nativepath.read_text())['sight_obstacles'][applied]['points']
    maskpath=Path(config['source_mask_manifest']);manifest=json.loads(maskpath.read_text())
    inventory=json.loads(Path(manifest['mask_inventory']).read_text())
    masks={m['index']:m for m in inventory['masks']}
    statespath=ROOT/'bridge-evidence/native-states/states.json'
    record=next(r for r in json.loads(statespath.read_text())['patches'] if r['id']==f'patch-{patch:03}')
    graphic=record[state+'_graphic'];alpha_path=statespath.parent/f'patch-{patch:03}'/graphic['alpha']
    aw,ah,alpha=pixels(alpha_path)
    entries=manifest['projections']['exterior']['assignments']
    entries[:]=[e for e in entries if not str(e.get('projection_component','')).startswith('east chain ')]
    report=[]
    for side,index in enumerate(indices):
        mask=masks[index];w,h,bitmap=pixels(mask['png']);mx,my=mask['box_top_left']
        samples=[]
        for x in range(1,w-1,4):
            ys=[]
            for y in range(h):
                ax,ay=mx+x-graphic['bbox'][0],my+y-graphic['bbox'][1]
                if bitmap[((h-1-y)*w+x)*4]>.5 and 0<=ax<aw and 0<=ay<ah and alpha[((ah-1-ay)*aw+ax)*4]>.5:
                    ys.append(y)
            if ys:samples.append((mx+x,my+sum(ys)/len(ys)))
        if len(samples)<2:raise ValueError('Missing chain silhouette')
        ends = [(2,3),(1,0)] if patch==1 else [(3,0),(2,1)]
        a,b=(native[i] for i in ends[side]);points=[]
        for x,image_y in samples:
            native_y=a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])
            points.append(Vector((x,-native_y/SINE,(native_y-image_y)/COSINE)))
        vertices=[];faces=[]
        toward=Vector((0,-COSINE,SINE))
        for start,end in zip(points,points[1:]):
            direction=(end-start).normalized();across=direction.cross(toward).normalized()*.30
            depth=toward*.7;offset=len(vertices)
            vertices.extend(p+r*across+s*depth for p in (start,end) for r,s in [(-1,-1),(1,-1),(1,1),(-1,1)])
            faces.extend(tuple(offset+i for i in face) for face in FACES)
        label=f'east chain {side+1} {state}'
        obj=object_mesh(template.get('asset_name',asset_id)+' / '+label,vertices,faces,template,collection)
        obj['bridge_east_hardware']=TAG;obj.hide_render=False;obj.hide_viewport=False
        entries.append({'source_node':template['source_node'],'projection_component':label,'mask_indices':[index],'reviewed':True,
                        'review_reason':'Exact native chain silhouette for this endpoint; thin centerline geometry follows only native-mask pixels inside endpoint alpha. Duplicate runtime masks omitted.'})
        report.append({'component':obj.name,'native_mask':index,'source_samples':samples,'vertices':len(vertices),'segments':len(points)-1})
    maskpath.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'endpoint_alpha_sha256':hashlib.sha256(alpha_path.read_bytes()).hexdigest(),
            'components':report,'source_supported':'Two chain silhouettes per visible endpoint; initial village chains are not visible in native artwork.',
            'inference':'Depth follows the corresponding native lowered deck edge extended to the winch; source vertical coordinates constrain height. Narrow closed rods represent chain centerlines; individual link thickness and hidden attachment depths are inferred.'}
