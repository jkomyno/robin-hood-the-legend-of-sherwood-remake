"""Neutral forest crowns constrained by regional native foliage fringes.

Regional occlusion masks do not identify an individual tree. Their leaf-edge
coverage constrains visible portions; lateral allocation and off-map completion
remain explicit hypotheses. No regional artwork RGB acquires source ownership.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parent))
import foliage_trees as foliage
from props_trees import GROUND

VERSION='leicester-neutral-regional-fringe-v1'
SPECS={
 90:dict(mask=25,box=(230,-95,450,270),center=338,seeds=[(282,35),(354,35),(414,65),(268,123),(332,121),(413,144),(363,181),(410,205)],wood=[107,108,109,110,111],roof=[420,429]),
 91:dict(mask=25,box=(435,-115,668,313),center=559,seeds=[(481,27),(566,35),(636,52),(476,143),(549,144),(636,166),(580,223),(639,257)],wood=[107,108,109,110,111],roof=[420,429]),
 92:dict(mask=28,box=(1148,-95,1342,200),center=1241,seeds=[(1180,22),(1240,15),(1310,30),(1172,85),(1230,85),(1294,78),(1226,145),(1290,133)],wood=[112,113],roof=[246,249]),
}


def paste_mask(record,box):
    left,top,right,bottom=box;out=np.zeros((bottom-top,right-left),dtype=bool)
    x,y=record['box_top_left'];im=np.asarray(Image.open(record['png']).convert('L'));h,w=im.shape
    a,b=max(left,x),max(top,y);c,d=min(right,x+w),min(bottom,y+h)
    if c>a and d>b:out[b-top:d-top,a-left:c-left]=im[b-y:d-y,a-x:c-x]>0
    return out


def evidence(workspace,node,output):
    spec=SPECS[node];config=json.loads((workspace/'workspace.json').read_text())
    manifest_path=Path(config['source_mask_manifest']);manifest=json.loads(manifest_path.read_text())
    inventory_path=(manifest_path.parent/manifest['mask_inventory']).resolve();inventory=json.loads(inventory_path.read_text())
    masks={r['index']:r for r in inventory['masks']};record=masks[spec['mask']]
    box=spec['box'];left,top,right,bottom=box;yy,xx=np.mgrid[top:bottom,left:right]
    native=paste_mask(record,box);coverage=native.copy()
    excluded=np.zeros_like(native)
    for index in spec['wood']+spec['roof']:excluded|=paste_mask(masks[index],box)
    coverage&=~excluded
    # Allocation between touching trees is inferred. A wavy side boundary
    # avoids presenting a rectangular crop edge as a measured leaf contour.
    lateral=(xx>left+5+5*np.sin(yy*.055))&(xx<right-5+5*np.sin(yy*.047+1))
    coverage&=lateral
    for row,y in enumerate(range(top,0)):
        # Outside the artwork, neutral rounded completion is an explicit
        # hypothesis. Do not reflect source rows: their branch exclusions
        # would become unsupported tall slits in the hidden crown.
        width_fraction=np.sqrt(max(0.,1.-(y/(-top))**2))
        halfwidth=(right-left)*.5*width_fraction
        leaf_pattern=(np.sin(xx[row]*12.9898+y*78.233)*43758.5453)%1
        coverage[row]=(leaf_pattern>.065)&(np.abs(xx[row]-spec['center'])<halfwidth)&lateral[row]
    coverage&=~excluded
    seeds=np.array(spec['seeds']);distance=(xx[:,:,None]-seeds[:,0])**2+(yy[:,:,None]-seeds[:,1])**2
    labels=distance.argmin(axis=2);supports=[]
    for i,(cx,cy) in enumerate(seeds):
        nearest=coverage&(labels==i)
        if not nearest.any():raise ValueError('Empty source-fringe lobe')
        radius=np.sqrt(distance[:,:,i][nearest].max())*1.25
        angle=np.arctan2(yy-cy,xx-cx)
        supports.append(np.sqrt(distance[:,:,i])<radius*(.94+.035*np.sin(angle*11+i)+.025*np.cos(angle*17-i)))
    output.mkdir(parents=True,exist_ok=True);lobes=[];union=np.zeros_like(coverage)
    for i,support in enumerate(supports):
        owned=coverage&support;ys,xs=np.nonzero(owned);x0,x1=max(0,int(xs.min())-2),min(right-left,int(xs.max())+3);y0,y1=max(0,int(ys.min())-2),min(bottom-top,int(ys.max())+3)
        rgba=np.full((y1-y0,x1-x0,4),105,dtype=np.uint8);rgba[:,:,3]=owned[y0:y1,x0:x1]*255
        path=output/f'lobe-{i:02}-neutral.png';Image.fromarray(rgba).save(path)
        lobes.append(dict(index=i,bbox_source=[left+x0,top+y0,left+x1,top+y1],source=str(path),unknown=str(path),observed=False,native_pixels=0))
        union|=owned
    if not np.array_equal(union,coverage):raise ValueError('Lobe union lost measured fringe coverage')
    if np.any(coverage&(yy>=0)&~native):raise ValueError('Visible coverage exceeds regional native alpha')
    if np.any(coverage&excluded):raise ValueError('Coverage includes excluded roof or wood')
    points=[]
    for x in range(left+10,right-10,8):
        col=x-left;rows=np.flatnonzero(coverage[:,col]&(yy[:,col]>=0))
        if not len(rows):continue
        y=int(rows.max()+top)
        # Only a transition already present in the regional native mask is
        # measured; exclusion edges and allocation cuts stay inferred.
        r=y-top;native_edge=r+1<len(native) and native[r,col] and not native[r+1,col]
        points.append(dict(source_xy=[x,y],role='visible lower foliage fringe',confidence='regional boundary measured; individual tree attribution inferred' if native_edge else 'exclusion/allocation constrained; inferred',regional_native_edge=bool(native_edge)))
    Image.fromarray(coverage.astype(np.uint8)*255).save(output/'derived-neutral-coverage.png')
    source=Image.open(config['source_path']).convert('RGB');crop=Image.new('RGB',(right-left,bottom-top));crop.paste(source.crop((left,0,right,bottom)),(0,-top))
    marked=crop.copy();draw=ImageDraw.Draw(marked)
    for i,p in enumerate(points):
        x,y=p['source_xy'];color=(0,255,255) if p['regional_native_edge'] else (255,0,255)
        draw.ellipse((x-left-2,y-top-2,x-left+2,y-top+2),fill=color);draw.text((x-left+3,y-top),str(i),fill=color)
    crop.save(output/'source-crop.png');marked.save(output/'numbered-fringe.png')
    report=dict(source_node=f'building-{node:03d}',source_rgb_sha256=foliage.sha(config['source_path']),native_alpha_sha256=foliage.sha(record['png']),
        regional_mask_index=spec['mask'],native_mask=None,lobes=lobes,source_box=list(box),source_rgb_projected=False,
        physical_opacity_authority='Derived neutral coverage; regional native fringe plus explicit tree allocation and off-map inference, not authoritative individual-tree alpha.',
        source_mask_manifest_sha256=foliage.sha(manifest_path),exclusions=spec['wood']+spec['roof'],
        measured_visible_pixels=int((coverage&(yy>=0)).sum()),inferred_offmap_pixels=int((coverage&(yy<0)).sum()),
        points=points,segments={'lower_fringe':'Measured only where the regional native alpha transitions to zero; labels identify other edges.',
        'lateral':'Inferred allocation between overlapping neighboring crowns; no source RGB ownership.',
        'upper':'Off-map rounded continuation with procedural neutral leaf gaps; wholly inferred.'},
        native_inventory_sha256=foliage.sha(inventory_path))
    (output/'source-partition.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(workspace):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open isolated fringe worker')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import validate
    validate(workspace)
    objects=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    crown=next(o for o in objects if o.get('projection_component')=='crown');node=int(crown['source_node'][9:])
    unchanged={o.name:foliage.geometry_hash(o) for o in objects if o!=crown}
    source_masks=foliage.sha(config['source_mask_manifest']);foliage.CONFIG[node]=dict(ground=GROUND[node])
    packet=evidence(workspace,node,workspace/'inspection/regional-fringe')
    report=foliage.refine_crown(crown,node,packet);fingerprint=foliage.geometry_hash(crown);foliage.refine_crown(crown,node,packet)
    if fingerprint!=foliage.geometry_hash(crown):raise ValueError('Non-idempotent fringe recipe')
    if unchanged!={o.name:foliage.geometry_hash(o) for o in objects if o!=crown}:raise ValueError('Wood changed')
    if source_masks!=foliage.sha(config['source_mask_manifest']):raise ValueError('Native ownership mutated')
    validate(workspace);crown['leicester_geometry_recipe']=VERSION
    report.update(recipe=VERSION,idempotence='PASS',source_ownership_unchanged=True,wood_geometry_unchanged=True,texture_generation='not-started',
        limitations=['Regional native alpha constrains visible lower fringe only; it does not identify a complete individual tree.',
        'All crown RGB and ownership remain neutral/zero. Adjacent-tree allocation and off-map completion are explicit inferences.',
        'Wood and roof exclusions are exact native-mask exclusions; no architecture is treated as foliage.',
        'Rounded and transverse hidden surfaces remain an inferred volumetric completion requiring user review.'])
    (workspace/'inspection/foliage-recipe.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
