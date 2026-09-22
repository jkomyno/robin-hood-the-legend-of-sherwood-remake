"""Correct the dormer-stem source constraint without changing approved geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from refinement_workspace import modified


def geometry():
    record=[]
    for obj in sorted(bpy.data.objects,key=lambda o:o.name):
        if obj.type!='MESH':continue
        record.append({'name':obj.name,'matrix':[list(row) for row in obj.matrix_world],
                       'vertices':[list(v.co) for v in obj.data.vertices],
                       'faces':[list(f.vertices) for f in obj.data.polygons],
                       'hidden':obj.hide_render})
    return hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace',type=Path)
    workspace=parser.parse_args(sys.argv[sys.argv.index('--')+1:]).workspace.resolve()
    revision=json.loads((workspace/'source-revision.json').read_text())
    model=workspace/'model.blend'
    if hashlib.sha256(model.read_bytes()).hexdigest()!=revision['approved_model_sha256']:
        raise RuntimeError('Start this source revision from the exact approved model')
    bpy.ops.wm.open_mainfile(filepath=str(model),load_ui=False);before=geometry()
    path=workspace/'source-masks.json';masks=json.loads(path.read_text())
    for assignment in masks['projections']['exterior']['assignments']:
        if assignment['source_node'] not in ['building-106','building-107']:continue
        assignment['mask_indices']=[207,208]
        assignment['evidence']='Native208 stops above the visible stone dormer stem; source1063,1343 contains stem masonry and native207 permits it. Shared hall207 silhouette remains constrained by first-hit geometry and independent occluders. See inspection/source-mask-comparison.png.'
    path.write_text(json.dumps(masks,indent=2)+'\n')
    modified(workspace)
    bpy.ops.wm.open_mainfile(filepath=str(model),load_ui=False);after=geometry()
    if before!=after:raise RuntimeError('Source correction changed approved geometry')
    revision.update(geometry_sha256_before=before,geometry_sha256_after=after,
                    corrected_nodes=['building-106','building-107'],native_masks=[207,208],
                    source_pixel_evidence=[1063,1343],geometry_unchanged=True,
                    source_review='pending',texture_generation='blocked pending corrected source review')
    (workspace/'source-revision.json').write_text(json.dumps(revision,indent=2)+'\n')


if __name__=='__main__':main()
