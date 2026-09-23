"""Trace endpoint-owned east bridge chains with explicitly inferred depth."""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from bridges import COSINE, SINE, FACES, object_mesh

ROOT = Path('level-editor/work/leicester-refinement').resolve()
TAG = 'leicester-east-chain-v2'

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
        if obj.get('bridge_east_hardware') and obj.get('asset_group')==asset_id:
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
        # Retain the measured chain envelope, including visible link gaps.
        # A subpixel centerline loses most of the painted chain's source area.
        cells = set()
        for x in range(w):
            for y in range(h):
                ax, ay = mx+x-graphic['bbox'][0], my+y-graphic['bbox'][1]
                if (bitmap[((h-1-y)*w+x)*4] > .5 and 0 <= ax < aw
                        and 0 <= ay < ah and alpha[((ah-1-ay)*aw+ax)*4] > .5):
                    cells.add((mx+x, my+y))
        if not cells:
            raise ValueError('Missing chain silhouette')
        ends = [(2,3),(1,0)] if patch==1 else [(3,0),(2,1)]
        a,b=(native[i] for i in ends[side])
        toward=Vector((0,-COSINE,SINE))
        vertices=[]; faces=[]; lookup={}
        def vertex(x, y, layer):
            key=(x,y,layer)
            if key not in lookup:
                native_y=a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])
                point=Vector((x,-native_y/SINE,(native_y-y)/COSINE))
                lookup[key]=len(vertices)
                vertices.append(point+toward*(.7 if layer else -.7))
            return lookup[key]
        for x,y in sorted(cells):
            corners=[(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
            faces.append(tuple(vertex(u,v,0) for u,v in reversed(corners)))
            faces.append(tuple(vertex(u,v,1) for u,v in corners))
            neighbors=[(x,y-1),(x+1,y),(x,y+1),(x-1,y)]
            for i,neighbor in enumerate(neighbors):
                if neighbor not in cells:
                    u,v=corners[i]; q,r=corners[(i+1)%4]
                    faces.append((vertex(u,v,0),vertex(q,r,0),vertex(q,r,1),vertex(u,v,1)))
        label=f'east chain {side+1} {state}'
        obj=object_mesh(template.get('asset_name',asset_id)+' / '+label,vertices,faces,template,collection)
        obj['bridge_east_hardware']=TAG;obj.hide_render=False;obj.hide_viewport=False
        entries.append({'source_node':template['source_node'],'projection_component':label,'mask_indices':[index],'reviewed':True,
                        'review_reason':'Exact native chain silhouette for this endpoint; closed measured silhouette envelope follows native-mask pixels inside endpoint alpha. Duplicate runtime masks omitted.'})
        report.append({'component':obj.name,'native_mask':index,'owned_source_pixels':len(cells),'vertices':len(vertices),'faces':len(faces),'source_envelope':'exact native pixel cells intersected with exact endpoint alpha'})
    maskpath.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'endpoint_alpha_sha256':hashlib.sha256(alpha_path.read_bytes()).hexdigest(),
            'components':report,'source_supported':'Two chain silhouettes per visible endpoint; initial village chains are not visible in native artwork.',
            'inference':'Depth follows the corresponding native lowered deck edge extended to the winch; source vertical coordinates constrain height. The exact pixel-cell envelope retains painted link gaps; its 1.4-unit camera-ray depth, concealed link cross-sections and attachment depths remain inferred.'}
