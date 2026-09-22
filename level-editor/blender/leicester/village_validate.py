"""Read-only geometry, UV, transform and topology comparison for a worker packet."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
import bmesh

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def record(o):
    bm=bmesh.new();bm.from_mesh(o.data)
    r={'source_node':o['source_node'],'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'boundary_world_edges':[[list(o.matrix_world@v.co) for v in e.verts] for e in bm.edges if e.is_boundary],'degenerate_faces':sum(f.calc_area()<1e-6 for f in bm.faces),'geometry_sha256':digest([[list(v.co) for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons]]),'uv_sha256':digest({uv.name:[list(d.uv) for d in uv.data] for uv in o.data.uv_layers}),'matrix_world':[list(row) for row in o.matrix_world]};bm.free();return r

def main():
    p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);w=a.workspace.resolve();c=json.loads((w/'workspace.json').read_text())
    sys.path.insert(0,str(next(p/'level-editor/blender' for p in Path(__file__).resolve().parents if (p/'level-editor/blender/refinement_workspace.py').exists())));from refinement_workspace import validate
    if Path(bpy.data.filepath).resolve()!=w/'model.blend':raise ValueError('Open worker model')
    protected=validate(w)
    def records():return {o.name:record(o) for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==c['asset_id']}
    after=records();bpy.ops.wm.open_mainfile(filepath=str(w/'baseline.blend'),load_ui=False);before=records()
    shared=before.keys()&after.keys();drift=[n for n in shared if before[n]['matrix_world']!=after[n]['matrix_world']]
    report={'status':'PASS' if not drift and all(not x['nonmanifold_edges'] and not x['degenerate_faces'] for x in after.values()) else 'FIX_NEEDED','asset_id':c['asset_id'],'baseline':before,'modified':after,'new_objects':sorted(after.keys()-before.keys()),'removed_objects':sorted(before.keys()-after.keys()),'transform_drift_objects':drift,'geometry_changed_objects':[n for n in shared if before[n]['geometry_sha256']!=after[n]['geometry_sha256']],'uv_changed_objects':[n for n in shared if before[n]['uv_sha256']!=after[n]['uv_sha256']],'outside_object_validation':protected,'limitations':['Manifold checks apply per component; intentional supports contact the roof, and inter-component intersections are not automatically classified.','Source RGB and pixel ownership evidence is provided separately by projection reports.']}
    (w/'inspection'/'geometry-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'asset_id':c['asset_id'],'new_objects':report['new_objects'],'transform_drift_objects':drift}))
if __name__=='__main__':main()
