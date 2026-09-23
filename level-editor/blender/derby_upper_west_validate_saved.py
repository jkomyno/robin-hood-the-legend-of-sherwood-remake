"""Independently reopen and verify the Upper West candidate and source targets."""
import sys,json,hashlib,math
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(Path(__file__).parent)]
import bpy,bmesh
from refinement_workspace import _geometry

def main():
    packet=Path(bpy.data.filepath).parent
    proof=json.loads((packet/'geometry.json').read_text())
    actual={o.name:_geometry(o) for o in bpy.data.collections['Derby Working'].objects}
    assert actual==proof['after'],'Saved model differs from recorded geometry'
    changed=[n for n in actual if proof['before'][n]!=actual[n]]
    assert changed==proof['changed'] and len(changed)==1
    assert bpy.data.objects[changed[0]].get('source_node')=='building-117'
    stats=[]
    for o in bpy.data.collections['Derby Working'].all_objects:
        if o.type!='MESH' or o.hide_render or o.get('asset_group')!='derby-upper-west-curtain':continue
        bm=bmesh.new();bm.from_mesh(o.data)
        s=dict(node=o.get('source_node'),vertices=len(bm.verts),faces=len(bm.faces),
            boundary_edges=sum(e.is_boundary for e in bm.edges),
            nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
            degenerate_faces=sum(f.calc_area()<1e-8 for f in bm.faces),volume=bm.calc_volume(signed=True))
        assert not(s['boundary_edges'] or s['nonmanifold_edges'] or s['degenerate_faces']),s
        assert s['volume']>0,s
        bm.free();stats.append(s)
    assert len(stats)==7
    result=dict(model=str(packet/'model.blend'),model_sha256=hashlib.sha256((packet/'model.blend').read_bytes()).hexdigest(),
        all_seven_owned_meshes_closed=True,changed_objects=changed,
        unchanged_objects=len(actual)-len(changed),saved_geometry_matches_report=True,meshes=stats)
    (packet/'saved-model-verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
