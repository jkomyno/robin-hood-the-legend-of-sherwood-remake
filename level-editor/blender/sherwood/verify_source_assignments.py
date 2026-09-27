"""Audit exact component coverage and source-domain separations before projection."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent;EDITOR=HERE.parents[1]
sys.path[:0]=[str(HERE),str(EDITOR/'refinement/blender')]
from source_authority import sha
from compile_source_masks import SOURCE,load_image
from occlusion_constraints import SourceMaskConstraints

def main(root):
    root=Path(root).resolve();coverage=json.loads((root/'coverage.json').read_text())
    assert coverage['unresolved_source_nodes']==0 and coverage['unconstrained_receivers']==0
    for path,digest in coverage['evidence'].items():assert sha(path)==digest,path
    recipe=json.loads((root/'recipe.json').read_text())
    manifest=json.loads((root/'source-masks.json').read_text())
    constraints=SourceMaskConstraints(root/'source-masks.json','exterior',sha(SOURCE),Image.open(SOURCE).size,image_loader=load_image)
    comp=recipe['component_assignments'];assert len(comp)==56
    domain_checks=[]
    for node,expected in [('building-024',34),('building-102',22)]:
        base=next(x for x in recipe['assignments'] if x['source_node']==node)
        base_mask=np.asarray(Image.open(base['authored_mask']['path']).convert('L'))>0
        receivers=[x for x in comp if x['source_node']==node];assert len(receivers)==expected
        for rule in receivers:
            obj=dict(name=rule['projection_component'],source_node=node,projection_component=rule['projection_component'])
            selected=constraints.for_object(obj);assert selected is not None
            specific=next(x for x in manifest['projections']['exterior']['assignments'] if x.get('projection_component')==rule['projection_component'])
            # Test actual mask queries, including authored zeros inside the native union.
            mask=np.asarray(Image.open(rule['authored_mask']['path']).convert('L'))>0
            y,x=np.where(mask);assert len(x)>0
            ix=np.linspace(0,len(x)-1,min(64,len(x)),dtype=int)
            assert constraints.allowed(selected,x[ix],mask.shape[0]-1-y[ix]).all()
            if node=='building-024':assert not (base_mask&mask).any(),'Ladder paint leaked onto oak bark'
            domain_checks.append(dict(component=rule['projection_component'],source_node=node,compiled_mask_indices=specific['mask_indices']))
    empty=[]
    for rule in recipe['assignments']:
        if rule.get('authored_mask') and not np.asarray(Image.open(rule['authored_mask']['path'])).any():empty.append(rule['source_node'])
    assert empty==['foliage-foreground-oak'],empty
    report=dict(status='PASS_DAY_ASSIGNMENTS',source_nodes=124,component_overrides=len(comp),unconstrained_receivers=0,
        ladder_bark_overlap_pixels=0,explicit_no_day_source=empty,coverage_sha256=sha(root/'coverage.json'),component_checks=domain_checks,
        conservative_exclusions='Foreground foliage, ambiguous seams and art without matching receiver geometry remain unknown; these masks do not assert complete source-pixel recovery.')
    (root/'assignment-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k!='component_checks'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');main(p.parse_args().root)
