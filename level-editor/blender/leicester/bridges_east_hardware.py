"""Trace endpoint-owned east bridge chains with explicitly inferred depth."""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
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
        down=Vector((0,-SINE,-COSINE))
        leaf_vertices=[template.matrix_world@v.co for v in template.data.vertices]
        leaf_tree=BVHTree.FromPolygons(leaf_vertices,[tuple(f.vertices) for f in template.data.polygons])
        xmin=min(x for x,y in cells)+.5;xmax=max(x for x,y in cells)+.5
        contact=[]
        for x,y in cells:
            if x+.5 < xmax-(xmax-xmin)*.2:continue
            hit,_,face,_=leaf_tree.ray_cast(Vector((x+.5,0,0))+down*(y+.5)+toward*10000,-toward)
            if face is not None:contact.append((x+.5,y+.5,hit))
        if not contact:raise ValueError('No source-supported chain/leaf contact: '+str(index))
        contact.sort(key=lambda item:item[0],reverse=True)
        end_x,_,end_hit=contact[0]
        end_native_y=-(end_hit.y+toward.y*.25)*SINE
        base_native_y=lambda x:a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])
        # The rear chain leaves the high mounting region of the timber canopy.
        # Extrapolating a lowered deck edge incorrectly moves this fixed winch
        # down between endpoint states. The front chain is below that canopy.
        mount_height=190 if patch==1 and side==0 else None
        mount_source_y=sum(y+.5 for x,y in cells if x+.5==xmin)/sum(x+.5==xmin for x,y in cells)
        start_native_y=mount_source_y+mount_height if mount_height is not None else base_native_y(xmin)
        # Fit the visible attachment ring against the named leaf surface,
        # without moving it behind an already valid native side-plane anchor.
        end_x=xmax
        end_native_y=base_native_y(end_x)
        contact_delta=0
        for x,y,hit in contact:
            t=(x-xmin)/(end_x-xmin)
            baseline=start_native_y+(end_native_y-start_native_y)*t
            contact_delta=max(contact_delta,(-(hit.y+toward.y*.25)*SINE-baseline)/t)
        end_native_y+=contact_delta
        native_depth=lambda x:start_native_y+(end_native_y-start_native_y)*(x-xmin)/(end_x-xmin)
        vertices=[]; faces=[]; lookup={}
        def vertex(x, y, layer, owner_cell):
            incident={(x-1,y-1),(x,y-1),(x,y),(x-1,y)} & cells
            diagonal=False
            if len(incident)==2:
                first,last=tuple(incident)
                diagonal=first[0]!=last[0] and first[1]!=last[1]
            # Two links touching only at a raster corner are separate closed
            # shells; welding their depth edge creates a four-face junction.
            key=(x,y,layer,owner_cell if diagonal else None)
            if key not in lookup:
                native_y=native_depth(x)
                point=Vector((x,-native_y/SINE,(native_y-y)/COSINE))
                lookup[key]=len(vertices)
                vertices.append(point+toward*(.7 if layer else -.7))
            return lookup[key]
        for x,y in sorted(cells):
            corners=[(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
            faces.append(tuple(vertex(u,v,0,(x,y)) for u,v in reversed(corners)))
            faces.append(tuple(vertex(u,v,1,(x,y)) for u,v in corners))
            neighbors=[(x,y-1),(x+1,y),(x,y+1),(x-1,y)]
            for i,neighbor in enumerate(neighbors):
                if neighbor not in cells:
                    u,v=corners[i]; q,r=corners[(i+1)%4]
                    faces.append((vertex(u,v,0,(x,y)),vertex(q,r,0,(x,y)),vertex(q,r,1,(x,y)),vertex(u,v,1,(x,y))))
        label=f'east chain {side+1} {state}'
        obj=object_mesh(template.get('asset_name',asset_id)+' / '+label,vertices,faces,template,collection)
        obj['bridge_east_hardware']=TAG;obj.hide_render=False;obj.hide_viewport=False
        entries.append({'source_node':template['source_node'],'projection_component':label,'mask_indices':[index],'reviewed':True,
                        'review_reason':'Exact native chain silhouette for this endpoint; closed measured silhouette envelope follows native-mask pixels inside endpoint alpha. Duplicate runtime masks omitted.'})
        report.append({'component':obj.name,'native_mask':index,'owned_source_pixels':len(cells),'vertices':len(vertices),'faces':len(faces),'source_envelope':'exact native pixel cells intersected with exact endpoint alpha','mount_height_game':mount_height,'mount_source':[xmin,mount_source_y],'leaf_contact_world':list(end_hit),'leaf_contact_x':end_x,'clearance_world':.25,'leaf_contact_end_native_y_adjustment':contact_delta})
    maskpath.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'endpoint_alpha_sha256':hashlib.sha256(alpha_path.read_bytes()).hexdigest(),
            'components':report,'source_supported':'Two chain silhouettes per visible endpoint; initial village chains are not visible in native artwork.',
            'inference':'Depth joins a measured leaf-face contact to the canopy mounting region (rear moat chain190game) or the native deck-side extension (other chains); source vertical coordinates constrain height. The exact pixel-cell envelope retains painted link gaps; its 1.4-unit camera-ray depth, concealed link cross-sections and attachment depths remain inferred.'}
