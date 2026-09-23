"""Source-profiled south drawbridge hardware with native wall/deck contacts.

Timber and chain silhouettes are measured; reverse thickness remains inferred.
Only generated drawbridge objects change. Gate geometry is never modified.
"""
import hashlib
import json
import math
from pathlib import Path

TAG = 'south-lifting-hardware-v2'
ASSET = 'leicester-south-drawbridge'
SINE, COSINE = math.sin(math.radians(35)), math.cos(math.radians(35))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bitmap(path):
    import bpy
    image=bpy.data.images.load(str(path),check_existing=False)
    try:
        w,h=image.size
        return w,h,list(image.pixels)
    finally:
        bpy.data.images.remove(image)


def profile(rows):
    """Closed pixel envelope; fill only internal link holes, retain the outline."""
    if len(rows)<2:raise ValueError('Insufficient hardware silhouette')
    left=[(lo,y+.5) for y,lo,hi in rows]
    right=[(hi+1,y+.5) for y,lo,hi in rows]
    points=[(rows[0][1],rows[0][0])]+left+[(rows[-1][1],rows[-1][0]+1),
        (rows[-1][2]+1,rows[-1][0]+1)]+list(reversed(right))+[(rows[0][2]+1,rows[0][0])]
    # Remove exactly collinear grid steps; never approximate the measured edge.
    changed=True
    while changed:
        changed=False;clean=[]
        for i,p in enumerate(points):
            a,b=points[i-1],points[(i+1)%len(points)]
            if abs((p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0]))<1e-10:
                changed=True
            else:clean.append(p)
        points=clean
    return points


def refine_hardware(workspace, asset_id, state):
    import bpy
    from mathutils import Vector
    from bridges import object_mesh
    if asset_id!=ASSET or state not in ('initial','applied'):
        raise ValueError('South hardware requires its explicit endpoint')
    workspace=Path(workspace).resolve()
    root=next(p for p in workspace.parents if p.name=='leicester-refinement')
    config=json.loads((workspace/'workspace.json').read_text())
    if config['asset_id']!=ASSET:raise ValueError('Wrong hardware workspace')
    collection=bpy.data.collections[config['collection_name']]
    node='building-391' if state=='initial' else 'building-390'
    templates=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==ASSET
               and o.get('source_node')==node and not o.get('bridge_hardware_generated')]
    if len(templates)!=1:raise ValueError('Expected one canonical leaf template')
    template=templates[0]
    native_file=root/'source-audit/Leicester.rhp.json'
    native=json.loads(native_file.read_text())['sight_obstacles']
    states_file=root/'bridge-evidence/native-states/states.json'
    record=next(p for p in json.loads(states_file.read_text())['patches'] if p['id']=='patch-010')
    graphic=record[state+'_graphic'];aw,ah,alpha=bitmap(states_file.parent/'patch-010'/graphic['alpha'])
    source_manifest=json.loads(Path(config['source_mask_manifest']).read_text())
    inventory_file=Path(source_manifest['mask_inventory']);inventory=json.loads(inventory_file.read_text())
    masks={m['index']:m for m in inventory['masks']}
    indices=[459,460] if state=='initial' else [453,454]
    def line(points,a,b,x):
        p,q=points[a],points[b]
        return p['y']+(x-p['x'])*(q['y']-p['y'])/(q['x']-p['x'])
    # Native front facade139 is the measured wall contact. The previous150game
    # hinge hypothesis put the timber behind this facade at the same source ray.
    facade=native[139]['points'];deck=native[391 if state=='initial' else 390]['points']
    additions=[];specifications=[];toward=Vector((0,-COSINE,SINE))
    old=[o for o in collection.all_objects if o.get('asset_group')==ASSET and o.get('bridge_hardware_generated')]
    for side,index in enumerate(indices):
        mask=masks[index];path=Path(mask['png'])
        if not path.is_absolute():path=inventory_file.parent/path
        w,h,pixels=bitmap(path);mx,my=mask['box_top_left'];oy=side*20
        beam_rows=[];chain_rows=[]
        for row in range(h):
            y=my+row;xs=[]
            for col in range(w):
                x=mx+col;ax=x-graphic['bbox'][0];ay=y-graphic['bbox'][1]
                if pixels[((h-1-row)*w+col)*4]>.5 and 0<=ax<aw and 0<=ay<ah and alpha[((ah-1-ay)*aw+ax)*4]>.5:xs.append(x)
            if not xs:continue
            if state=='applied':
                target=beam_rows if y<=1348+oy else chain_rows
                target.append((y,min(xs),max(xs)));continue
            if y<1241+oy:
                beam_rows.append((y,min(xs),max(xs)));continue
            runs=[]
            for x in xs:
                if not runs or x>runs[-1][-1]+1:runs.append([x])
                else:runs[-1].append(x)
            if len(runs)>1:
                chain_rows.append((y,runs[0][0],runs[0][-1]));beam_rows.append((y,runs[-1][0],runs[-1][-1]))
            elif y<=1241+oy:
                chain_rows.append((y,min(xs),min(xs)+3));beam_rows.append((y,min(xs)+4,max(xs)))
            else:chain_rows.append((y,min(xs),max(xs)))
        # The wall-end outer edge, not the old centerline, is the contact.
        # Otherwise the broad timber section would pass behind the facade.
        hinge_x=max(row[2]+1 for row in beam_rows);hinge_y=1283.+oy
        contact_y=line(facade,1,2,hinge_x)
        def timber_depth(x):return contact_y+2.+(hinge_x-x)*55./53.
        first,last=chain_rows[0],chain_rows[-1]
        top_x=(first[1]+first[2]+1)/2;bottom_x=(last[1]+last[2]+1)/2
        top_depth=timber_depth(top_x)
        bottom_depth=line(deck,2,1,bottom_x) if state=='initial' else line(deck,1,0,bottom_x)
        bottom_depth+=3.
        for kind,rows,thickness in [('lifting beam',beam_rows,8.),('chain',chain_rows,2.6)]:
            contour=profile(rows);front=[]
            for x,y in contour:
                fraction=max(0.,min(1.,(y-first[0])/(last[0]+1-first[0])))
                depth=timber_depth(x) if kind=='lifting beam' else top_depth*(1-fraction)+bottom_depth*fraction
                front.append(Vector((x,-depth/SINE,(depth-y)/COSINE)))
            count=len(front);vertices=front+[p-toward*thickness for p in front]
            faces=[tuple(range(count)),tuple(reversed(range(count,2*count)))]+[
                (i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
            component=f'south {state} {kind} {side+1}'
            obj=object_mesh(f'South Drawbridge / {component}',vertices,faces,template,collection)
            obj['projection_component']=component;obj['bridge_hardware_generated']=TAG
            obj['drawbridge_state']=state;obj['drawbridge_patch_id']='patch-010'
            obj.hide_render=False;obj.hide_viewport=False;additions.append(obj)
            specifications.append({'source_node':node,'projection_component':component,'mask_indices':[index],
                'reviewed':True,'evidence':'Exact native endpoint-mask silhouette intersected with endpoint sprite alpha; native139 facade and native leaf edge establish depth contacts.',
                'source_outline':contour,'inferred_reverse_thickness_world':thickness,
                'hinge_contact_native_y':contact_y,'hinge_game_height':contact_y-hinge_y,
                'front_clearance_native_units':{'facade':2.,'leaf':3.},
                'chain_native_depth_endpoints':[top_depth,bottom_depth]})
    for obj in old:bpy.data.objects.remove(obj,do_unlink=True)
    for obj in additions:obj.name='South Drawbridge / '+obj['projection_component']
    bpy.context.view_layer.update()
    return {'recipe':TAG,'reused':False,'asset_id':ASSET,'state':state,'source_node':node,
        'components':[o.name for o in additions],'measured_components':specifications,
        'assignments':[{k:v for k,v in s.items() if k in ('source_node','projection_component','mask_indices','reviewed','evidence')} for s in specifications],
        'native_mask_indices':indices,'recipe_sha256':sha(__file__),'endpoint_evidence_sha256':sha(states_file),
        'endpoint_frame_sha256':graphic['sha256'],'endpoint_frame_source_sha256':graphic['source_sha256'],
        'endpoint_source_sha256':sha(root/f'bridge-evidence/native-states/patch-010/{state}-map.png'),
        'native_level_sha256':sha(native_file),
        'limitations':['Reverse timber thickness8world, chain2.6world and facade/leaf clearances2/3native units are inferred.',
            'Chain envelopes retain source silhouette and bow; individual link holes are not reconstructed.',
            'Endpoint geometry does not establish intermediate articulation.',
            'Three initial left-chain pixels at the native139 lower edge remain depth-occluded by less than one native unit; no gate exclusion or extra clearance was invented.',
            'Gatehouse geometry and projection occluders remain unchanged.'],
        'status':'geometry candidate; requires source-ray, topology, fixed-view and stored-material validation'}
