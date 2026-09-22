"""Correct central turret notch phase from individually traced source corners."""
from pathlib import Path
import runpy
import bpy

# Every tuple is a distinct source observation, not a generated period. The
# rear-right endpoint is roof-occluded; retain its inherited termination.
RUNS = {
 153: [(4,0,10,2,[(774,788)],29), (4,0,10,2,[(804,818)],29),
       (4,0,10,2,[(834,850)],29)],
 158: [(0,7,20,16,[(770,778)],27), (0,7,20,16,[(788,798)],27),
       (0,2,20,24,[(761.2,762.7)],27),
       (7,11,16,12,[(817,830)],27), (7,11,16,12,[(846,866)],27)],
}
TRACES = {
 'front': [[764,386],[774,389],[774,413],[788,418],[788,394],
           [804,400],[804,424],[818,429],[818,405],[834,411],
           [834,435],[850,441],[850,417],[863,422]],
 'rear_left': [[760,340],[770,331],[770,353],[778,346],[778,324],
               [788,315],[788,337],[798,328],[798,306],[805,300]],
 'rear_right': [[805,300],[817,304],[817,326],[830,331],[830,309],
                [846,315],[846,337],[866,344]],
}

def refine():
    from derby_round3_keep_central_gallery import refine as close_shells
    cut=runpy.run_path(str(Path(__file__).with_name('derby_asset_east_hall.py')))['_refine']
    rows=[]
    for number,recipe in RUNS.items():
        node=f'building-{number:03}'
        visible=[o for o in bpy.data.objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render]
        assert len(visible)==1, node
        old=visible[0]
        if old.get('central_trace_revision')==1: continue
        originals=[o for o in bpy.data.objects if o.type=='MESH' and o.get('source_node')==node and len(o.data.vertices)==(16 if number==153 else 40)]
        assert len(originals)==1,node
        source=originals[0]
        report=cut(source,recipe)
        new=bpy.data.objects[source['replaced_by']]
        old.hide_render=True; old.hide_viewport=True
        if 'central_shell_revision' in new: del new['central_shell_revision']
        new['central_trace_revision']=1
        rows.append(report)
    closed=close_shells()
    return {'cuts':rows,'closed':closed,'traces':TRACES,
            'uncertainty':'Rear-right final endpoint is hidden by North Tower roof. Its inherited termination is retained; side run below 2 source pixels is not independently measurable.',
            'bridge':'Unchanged pending independent source-supported height measurement; image diagonal alone does not determine world slope.'}
