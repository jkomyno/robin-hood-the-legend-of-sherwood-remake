"""Prepare and validate explicit drawbridge endpoints from native sprite evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refinement_workspace import prepare,validate,modified
from bridges import object_mesh,world,COSINE
ROOT=Path('level-editor/work/leicester-refinement').resolve()
BRIDGES={'leicester-east-moat-drawbridge':(1,388,389,449,443),
         'leicester-east-village-drawbridge':(8,387,384,437,441),
         'leicester-south-drawbridge':(10,391,390,458,455)}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    if (ROOT/'bridge-evidence/pause-render').exists():
        print('Bridge render slot released at packet boundary',flush=True)
        raise SystemExit(0)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','refine']);parser.add_argument('asset',choices=BRIDGES)
    parser.add_argument('state',choices=['initial','applied']);args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    patch,initial,applied,oldmask,newmask=BRIDGES[args.asset]
    workspace=ROOT/'round-1/assets-v2'/args.asset
    if args.state=='applied':workspace=ROOT/'round-1/bridge-applied'/args.asset
    native=json.loads(Path('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json').read_text())
    statespath=ROOT/'bridge-evidence/native-states/states.json'
    states=json.loads(statespath.read_text());record=next(p for p in states['patches'] if p['id']==f'patch-{patch:03}')
    source=statespath.parent/f'patch-{patch:03}'/f'{args.state}-map.png'
    if args.mode=='prepare':
        jobs=json.loads((ROOT/'round-1/assets-v2/dispatch.json').read_text())['jobs']
        job=next(j for j in jobs if j['asset_id']==args.asset);argv=job['prepare_argv'];opts=argv[argv.index('--asset-id'):]
        kw={opts[i][2:].replace('-','_'):opts[i+1] for i in range(0,len(opts),2)}
        kw.pop('projection_manifest',None);kw['source_path']=str(source)
        maskpath=ROOT/'bridge-evidence/endpoint-ownership'/f'{args.asset}-{args.state}-masks.json'
        if not maskpath.is_file():raise RuntimeError('Run bridges_ownership.py to freeze reviewed endpoint masks first')
        kw['source_mask_manifest']=str(maskpath)
        bpy.ops.wm.open_mainfile(filepath=argv[2]);bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
        # Freeze an explicit endpoint before rendering input; canonical ownership
        # retains both alternatives, while projection membership is state-specific.
        for obj in bpy.data.collections['Leicester Working'].all_objects:
            if obj.type=='MESH' and obj.get('asset_group')==args.asset:
                visible=obj.get('source_node')==f'building-{initial if args.state=="initial" else applied:03}'
                obj.hide_render=not visible;obj.hide_viewport=not visible
        bpy.context.view_layer.update()
        prepare(workspace,**kw,framing_padding=1.65 if args.state=='initial' else 1.15)
        return
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise RuntimeError('Open the endpoint worker model')
    validate(workspace);config=json.loads((workspace/'workspace.json').read_text());collection=bpy.data.collections[config['collection_name']]
    target=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==args.asset]
    if {o['source_node'] for o in target}!={f'building-{initial:03}',f'building-{applied:03}'}:raise RuntimeError('Unexpected endpoint ownership')
    changes=[]
    hinge=min(p['z_top'] for p in native['sight_obstacles'][applied]['points'])
    for obj in target:
        index=int(obj['source_node'].split('-')[1]);points=[dict(point) for point in native['sight_obstacles'][index]['points']];n=len(points)
        if index==387:
            # The raised sight slab covers only part of the visible timber leaf.
            # Match its hinge width to the lowered leaf; the hidden upper extent
            # follows that same deck length, rather than a silhouette guess.
            deck=native['sight_obstacles'][384]['points']
            dx,dy=points[0]['x']-points[1]['x'],points[0]['y']-points[1]['y']
            anchors=[(deck[2]['x']+dx,deck[2]['y']+dy),(deck[2]['x'],deck[2]['y']),
                     (deck[3]['x'],deck[3]['y']),(deck[3]['x']+dx,deck[3]['y']+dy)]
            length=((world(deck[0])-world(deck[3])).length+(world(deck[1])-world(deck[2])).length)/2
            for point,(x,y) in zip(points,anchors):
                point.update(x=x,y=y,z_top=hinge+length*COSINE)
        bottom=[max(p['z_bottom'],hinge-6.5) if index==initial else p['z_bottom'] for p in points]
        vertices=[world(p,z) for p,z in zip(points,bottom)]+[world(p) for p in points]
        faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        replacement=object_mesh(obj.name+' restored leaf',vertices,faces,obj,collection)
        old=obj.data;obj.data=replacement.data;replacement.data=old;bpy.data.objects.remove(replacement,do_unlink=True)
        visible=index==(initial if args.state=='initial' else applied)
        obj.hide_render=not visible;obj.hide_viewport=not visible
        obj['drawbridge_state']= 'initial' if index==initial else 'applied'
        obj['endpoint_source_sha256']=sha(source)
        obj['native_patch']=f'patch-{patch:03}'
        obj['drawbridge_patch_id']=f'patch-{patch:03}'
        obj['drawbridge_endpoint_source_sha256']=sha(source)
        obj['drawbridge_endpoint_evidence_sha256']=sha(statespath)
        obj['drawbridge_initial_source_node']=f'building-{initial:03}'
        obj['drawbridge_applied_source_node']=f'building-{applied:03}'
        obj['drawbridge_default_state']='initial'
        changes.append({'source_node':obj['source_node'],'state':obj['drawbridge_state'],'visible':visible,'bottom_heights':bottom,'vertices':n*2,'faces':n+2})
    bpy.context.view_layer.update();validate(workspace)
    report={'asset_id':args.asset,'state':args.state,'recipe_sha256':sha(__file__),
       'endpoint_evidence_sha256':sha(statespath),'source_sha256':sha(source),'source_frame':record[args.state+'_graphic'],
       'changes':changes,'hinge_height':hinge,'exclusive_visible_leaf_count':sum(not o.hide_render for o in target),
       'status':'refinement in progress','source_supported':'Native endpoint images separately confirm raised initial and lowered applied leaves; the endpoint collision components identify their footprints. Lower raised leaf is trimmed to adjacent deck hinge height.',
       'limitations':['Chains, lifting beams and coupled mechanism geometry remain incomplete.','Endpoint composites apply this bridge independently; simultaneous coupled mechanism state not validated.','Native collision slab depth approximates timber thickness; all hidden faces remain neutral.', 'East village raised hinge width is reconciled with its lowered deck; upper extent uses the same physical leaf length and remains inferred behind the tower.','The two endpoint meshes are explicit states; no interpolated hinge animation has been approved.']}
    if report['exclusive_visible_leaf_count']!=1:raise RuntimeError('Mixed bridge endpoints')
    (workspace/'inspection').mkdir(exist_ok=True);(workspace/'inspection/bridge-state.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));modified(workspace)
    print(json.dumps(report))

if __name__=='__main__':main()
