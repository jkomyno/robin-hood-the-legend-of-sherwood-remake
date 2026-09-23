"""Thin timber mechanism canopy retaining its measured source-facing roof."""
import json,math,sys
from pathlib import Path
import bpy,bmesh
sys.path.insert(0,str(Path(__file__).resolve().parent))
from towers import write_mesh,diagnostics


def refine(obj):
    if obj.get('source_node')!='building-221':raise ValueError(obj.name)
    p=Path(__file__).resolve().parents[3]/'datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json'
    points=json.loads(p.read_text())['sight_obstacles'][221]['points']
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    top=[(v['x'],-v['y']/sine,v['z_top']/cosine) for v in points]
    vertices=top+[(x,y,z-3) for x,y,z in top]
    faces=[(0,1,2,3),(7,6,5,4)]+[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)]
    before=diagnostics(obj);write_mesh(obj,vertices,faces,'Measured mechanism canopy with thin timber underside')
    bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    after=diagnostics(obj)
    if after['nonmanifold_edges'] or after['degenerate_faces']:raise RuntimeError(str(after))
    return dict(source_node='building-221',before=before,after=after,thickness=3,evidence='node221-source-overlay.png confirms native top polygon matches four roof boards. Source edge shows a thin canopy; the imported flat-bottom wedge is replaced by a parallel underside.',limitations=['Three-unit board thickness inferred from visible edge; hidden support connection remains unknown.'])


if __name__=='__main__':
    w=Path(sys.argv[sys.argv.index('--')+1]).resolve();c=json.loads((w/'workspace.json').read_text())
    if c['asset_id']!='leicester-church-side-tower':raise ValueError(c['asset_id'])
    obj=next(o for o in bpy.data.collections[c['collection_name']].all_objects if o.get('source_node')=='building-221' and o.get('asset_group')==c['asset_id'])
    (w/'inspection/canopy221.json').write_text(json.dumps(refine(obj),indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
