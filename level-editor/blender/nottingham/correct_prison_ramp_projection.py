"""Restore reviewed exterior source ownership without altering accepted geometry."""
import copy,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from freeze_tooling import select_tooling
from render_slots import acquire
from correct_source_projection import geometry,geometry_sha

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')

def clone_workspace(old, new):
    """Retain immutable inputs, baseline and source hashes in a separate worker."""
    if new.exists():return
    shutil.copytree(old,new,ignore=shutil.ignore_patterns('history','projection-correction-reference','*.blend1'))
    candidate=json.loads((new/'candidate.json').read_text())
    candidate['status']='refinement-in-progress'
    write(new/'candidate.json',candidate)
    config=json.loads((new/'workspace.json').read_text())
    for key,value in config.items():
        if key=='source_path' and not config.get('projection_manifest'):
            continue
        if isinstance(value,str) and value.startswith(str(old)+'/'):
            config[key]=str(new)+value[len(str(old)):]
    config['cloned_mask_origin']=dict(workspace=str(old),workspace_sha256=sha(old/'workspace.json'),
                                    manifest=json.loads((old/'workspace.json').read_text())['source_mask_manifest'])
    write(new/'workspace.json',config)
    layers=new/'projection-layers.json'
    if layers.exists():layers.write_text(layers.read_text().replace(str(old)+'/',str(new)+'/'))

def prison_review(review):
    review=copy.deepcopy(review)
    review['receiver_nodes'].remove('building-452')
    review['evidence']+=' Review correction: full-height turret support452 also carries the source-visible exterior left turret wall. It is an exterior receiver, retained in both states; native silhouette373 gates its eligible pixels.'
    return review

def pixel_witnesses(w, old, config, node):
    """Audit added native pixels through the complete immutable source scene."""
    import collections,math
    import bpy
    from mathutils import Vector
    from PIL import Image
    from refinement_review import _tree
    from occlusion_constraints import SourceMaskConstraints
    angle=math.radians(config['elevation_degrees']);s,c=math.sin(angle),math.cos(angle)
    direction=Vector((0,-c,s))
    objects=[o for o in bpy.data.collections[config['collection_name']].all_objects
             if o.type=='MESH' and not o.hide_render]
    targets=[o for o in objects if o.get('source_node')==node]
    tree,owners,points=_tree(objects);own,own_owners,vertices=_tree(targets)
    depth=max(p.dot(direction) for p in points)+10
    source=Image.open(config['source_path']).convert('RGB');width,height=source.size
    source_hash=sha(config['source_path'])
    before=SourceMaskConstraints(old/'source-masks.json','exterior',source_hash,source.size)
    after=SourceMaskConstraints(w/'source-masks.json','exterior',source_hash,source.size)
    projected=[(v.x,-v.y*s-v.z*c) for v in vertices]
    box=(max(0,int(min(p[0] for p in projected))),max(0,int(min(p[1] for p in projected))),min(width,math.ceil(max(p[0] for p in projected))),min(height,math.ceil(max(p[1] for p in projected))))
    accepted=[];blocked=collections.Counter();overlay=source.copy()
    for y in range(box[1],box[3]):
        for x in range(box[0],box[2]):
            p=Vector((x+.5,-(y+.5)/s,0));origin=p+direction*(depth-p.dot(direction))
            hit,normal,i,_=own.ray_cast(origin,-direction)
            if i is None:continue
            obj=own_owners[i]
            if before.allowed_pixel(obj,x,y) or not after.allowed_pixel(obj,x,y):continue
            full_hit,full_normal,j,_=tree.ray_cast(origin,-direction)
            if j is None or owners[j]!=obj:
                blocked[str(owners[j].get('source_node')) if j is not None else 'no-hit']+=1
                continue
            if full_normal.dot(direction)<float(obj.get('projection_min_cosine',.05)):
                blocked['facing']+=1;continue
            accepted.append([x,y]);rgb=source.getpixel((x,y));overlay.putpixel((x,y),tuple(round(a*.6+b*.4) for a,b in zip(rgb,(0,255,0))))
    overlay.crop(box).save(w/'added-source-pixels.png')
    write(w/'added-source-pixels.json',dict(source_sha256=source_hash,node=node,model_sha256=sha(w/'model.blend'),accepted_pixels=accepted,accepted_count=len(accepted),blocked_by=dict(blocked),crop=list(box),method='Native mask difference plus full-scene first hit and facing; highlighted green accepted source pixels.'))

def main():
    asset=sys.argv[sys.argv.index('--')+1]
    assert asset in ['nottingham-upper-prison','nottingham-castle-approach-ramp']
    tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9');acquire()
    import bpy,refinement_workspace as rw
    w=WORK/('round-24/assets' if asset.endswith('prison') else 'round-23/assets')/asset
    old=WORK/('round-1/prison-final-assets' if asset.endswith('prison') else 'round-1/assets')/asset
    clone_workspace(old,w)
    c=json.loads((w/'workspace.json').read_text());source_hash=sha(old/'model.blend')
    bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update();before=geometry()
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.window.scene=bpy.data.scenes[c['scene_name']];bpy.context.view_layer.update();assert before==geometry()
    masks=json.loads((w/'source-masks.json').read_text());entries=masks['projections']['exterior']['assignments'];node='building-452' if asset.endswith('prison') else 'building-343';entry=next(e for e in entries if e.get('source_node')==node)
    original=next(e for e in json.loads((old/'source-masks.json').read_text())['projections']['exterior']['assignments'] if e.get('source_node')==node)
    if asset.endswith('prison'):
        entry.clear();entry.update(source_node=node,mask_indices=[373],reviewed=True,constraint_kind='reviewed-native-silhouette',review_note='The retained full-height turret envelope shares the source-visible left masonry with444. Native373 isolates the exterior roof and turret from the lower prison body; source-scene visibility still excludes other architecture and the hidden foundation.',review_evidence=str(WORK/'review4-prison-ramp/prison-diagnostic.png'))
    else:
        entry.clear();entry.update(copy.deepcopy(original))
        entry['mask_indices']=sorted(set(entry['mask_indices']+[277]));entry['review_note']+=' Native277 includes the source-visible upper western ramp parapet absent from275. Foreign houses and gate remain scene occluders.';entry['review_evidence']=str(WORK/'review4-prison-ramp/ramp-diagnostic.png')
    write(w/'source-masks.json',masks)
    bpy.context.preferences.filepaths.save_version=0
    if asset.endswith('prison'):
        from refine_prison_packets import execute
        execute(w,refine_geometry=False,projection_review_transform=prison_review)
    else:rw.modified(w)
    pixel_witnesses(w,old,c,node)
    bpy.context.view_layer.update();after=geometry();assert before==after,'Geometry or transforms changed'
    report=dict(version=1,asset_id=asset,status='awaiting-independent-review',previous_workspace=str(old),previous_model_sha256=source_hash,model_sha256=sha(w/'model.blend'),geometry_before_sha256=geometry_sha(before),geometry_after_sha256=geometry_sha(after),geometry_identical=True,mesh_count=len(before),changes=[dict(before=original,after=entry)],tooling=tooling,recipe_sha256=sha(__file__))
    write(w/'projection-correction.json',report)
    candidate=json.loads((w/'candidate.json').read_text());candidate.update(status='refinement-in-progress',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),recipe=str(Path(__file__).resolve()),geometry_refined=False,no_change_reason='Projection ownership correction only; actual vertices, polygon indices and world transforms match the reviewed model exactly.',changes=[entry['review_note']]);write(w/'candidate.json',candidate)
    candidate.update(projection_correction='projection-correction.json',source_comparison='added-source-pixels.png')
    # The frozen input predates the already-reviewed geometry recipe. Keep its
    # refinement declaration while explicitly recording zero edits this revision.
    candidate['geometry_refined']=json.loads((old/'candidate.json').read_text())['geometry_refined']
    candidate['geometry_changed_in_this_revision']=False
    write(w/'candidate.json',candidate)
    print('GEOMETRY IDENTICAL',asset,flush=True)
if __name__=='__main__':main()
