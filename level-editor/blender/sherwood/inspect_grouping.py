"""Extract actual world bounds and source-view hulls for a grouping audit."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from scipy.spatial import ConvexHull, QhullError

EDITOR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(EDITOR/'refinement'))
from render_slots import acquire


def main(worker,output):
    acquire();bpy.ops.wm.open_mainfile(filepath=str(Path(worker).resolve()))
    records=[]
    for obj in bpy.data.collections['Sherwood Working'].objects:
        if obj.type!='MESH':continue
        a=np.empty(len(obj.data.vertices)*3);obj.data.vertices.foreach_get('co',a);a=a.reshape(-1,3)
        m=np.array(obj.matrix_world);a=a@m[:3,:3].T+m[:3,3]
        uv=np.column_stack([a[:,0],-a[:,1]*math.sin(math.radians(35))-a[:,2]*math.cos(math.radians(35))])
        try:hull=uv[ConvexHull(uv).vertices].tolist()
        except QhullError:hull=uv[:3].tolist()
        records.append(dict(name=obj.name,source=obj.get('source_node'),asset=obj.get('asset_group'),
            min=a.min(0).tolist(),max=a.max(0).tolist(),hull=hull,vertices=len(a)))
    Path(output).write_text(json.dumps(records)+'\n')
    print('AUDITED',len(records),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',required=True);p.add_argument('--output',required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);main(a.worker,a.output)
