"""Reconstruct vertical canopy supports from measured artwork foot/eave spans."""
import json, math, sys
from pathlib import Path
import bpy, bmesh
import numpy as np
from mathutils import Vector
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/refinement/blender').exists())
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
sys.path.insert(0,str(ROOT/'level-editor/blender/leicester'))
from refinement_workspace import validate

def main(w):
    c=json.loads((w/'workspace.json').read_text());validate(w)
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    posts=[('left',3021.5,518.,596.),('right',3069.5,477.,557.)]
    corners=[(2983.,490.),(3033.,443.),(3078.,474.),(3023.,518.)]
    heights=[86.68,86.66,64.70,75.0]
    anchors=[(*p,z) for p,z in zip(corners,heights)]
    def plane(x,p):
        for tri in [(0,1,2),(0,2,3)]:
            matrix=np.array([[corners[i][0] for i in tri],[corners[i][1] for i in tri],[1,1,1]])
            weights=np.linalg.solve(matrix,[x,p,1.])
            if min(weights)>=-1e-5:break
        z=float(sum(weights[j]*heights[i] for j,i in enumerate(tri)))
        return x,(-p-z*cosine)/sine,z
    targets=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==c['asset_id']]
    roof=next(o for o in targets if o.get('source_node')=='building-010' and not o.get('projection_component'))
    archive=w/'history/before-vertical-porch-21f500d15e396441/model.blend'
    with bpy.data.libraries.load(str(archive),link=False) as (available,loaded):
        if roof.name not in available.objects:raise ValueError('Missing archived canopy')
        loaded.objects=[roof.name]
    original=loaded.objects[0];roof.data=original.data.copy();bpy.data.objects.remove(original,do_unlink=True)
    mesh=roof.data;roof_report={'restored_exactly_from':str(archive),'native_mask':121};reports=[]
    for label,x,top,foot in posts:
        obj=next(o for o in targets if o.get('projection_component')==f'canopy-{label}-post')
        _,y,h=plane(x,top);foot_z=h-(foot-top)/cosine
        # Vertical square timbers: raster irregularities are texture, not lean.
        verts=[(x+dx,y+dy,z) for z in [foot_z,h+1.5] for dx,dy in [(-2.5,-1.5),(2.5,-1.5),(2.5,1.5),(-2.5,1.5)]]
        m=bpy.data.meshes.new('Vertical Canopy '+label);m.from_pydata([obj.matrix_world.inverted()@Vector(v) for v in verts],[],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        m.uv_layers.new(name='UVMap');m.materials.append(mesh.materials[0]);obj.data=m
        bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);bm.to_mesh(m);bm.free()
        assert bad==0
        reports.append({'component':label,'source_top':[x,top],'source_foot':[x,foot],'height_to_roof':h-foot_z,'roof_height':h,'foot_elevation':foot_z,'horizontal_axis_drift':0,'nonmanifold_edges':bad,'width':5,'depth':3,'roof_contact_overlap':1.5})
    report={'asset_id':c['asset_id'],'supports':reports,'roof':roof_report,'roof_plane_height_anchors':anchors,'source_uncertainty_pixels':3,'inference':'Visible source crop shows porch footings on the lower ditch bank beneath the house foundation. Original canopy slope and source-native silhouette retained. Vertical posts follow constant horizontal position from roof contacts down to observed bank-foot pixels; negative foot elevations are relative to the house datum, not buried feet. Hidden timber depth3 is inferred. Native121 ownership unchanged.','changed_objects':[o.name for o in targets if o.get('projection_component') in {'canopy-left-post','canopy-right-post'}]}
    out=w/'inspection/vertical-porch';out.mkdir(exist_ok=True);(out/'geometry.json').write_text(json.dumps(report,indent=2)+'\n')
    validate(w);bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
if __name__=='__main__':main(Path(sys.argv[sys.argv.index('--')+1]).resolve())
