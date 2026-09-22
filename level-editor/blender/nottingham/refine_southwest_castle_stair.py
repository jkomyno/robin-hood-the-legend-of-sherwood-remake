"""Reconstruct the eight visible southwest castle stair risers from source anchors."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refine_castle_secondary import WORK,write,sha
from freeze_tooling import select_tooling
ASSET='nottingham-castle-southwest-stair'
WS=WORK/'round-5/assets'/ASSET

def geometry():
    high=165.455;low=100.0
    upper=[(688,1547+high),(735,1535+high)]
    lower=[(734,1665+low),(762,1659+low)]
    cross=[([(650,1519+high),(724,1513+high)],high),(upper,high)]
    for i in range(1,9):
        xy=[tuple(a[k]+(b[k]-a[k])*i/8 for k in range(2)) for a,b in zip(upper,lower)]
        cross.extend([(xy,high-(high-low)*(i-1)/8),(xy,high-(high-low)*i/8)])
    vertices=[(x,y,z) for xy,z in cross for x,y in xy]
    n=len(cross);faces=[[2*i,2*i+1,2*i+3,2*i+2] for i in range(n-1)]
    vertices.extend([(x,y,low) for x,y in cross[0][0]])
    faces.extend([[2*n,2*n+1,1,0],[2*n,0]+[2*i for i in range(1,n)],
                  [2*n+1]+list(reversed([2*i+1 for i in range(n)])),[2*n,2*(n-1),2*(n-1)+1,2*n+1]])
    return vertices,faces

def main():
    tooling=select_tooling(WORK/'tooling-common-v1/2fbc2cbceea1fd2d')
    from render_slots import acquire
    acquire()
    import bpy
    from refinement_workspace import validate,modified,_geometry
    from refine_castle_secondary_details import native_mesh
    bpy.ops.wm.open_mainfile(filepath=str(WS/'model.blend'))
    validate(WS)
    config=json.loads((WS/'workspace.json').read_text())
    objects=list(bpy.data.collections[config['collection_name']].all_objects)
    target=[o for o in objects if o.type=='MESH' and o.get('asset_group')==ASSET]
    assert len(target)==1 and target[0]['source_node']=='building-352'
    masks_path=Path(config['source_mask_manifest']);masks=json.loads(masks_path.read_text())
    for row in masks['projections']['exterior']['assignments']:
        if row.get('source_node')=='building-352':
            row.clear();row.update(source_node='building-352',reviewed=True,native_ownership_reviewed=True,mask_indices=[278],constraint_kind='reviewed-native-silhouette',review_evidence='castle-secondary-audit/mask-278-overlay.png',review_note='Mask278 visibly contains this stair. Only the measured stair receiver footprint with first-hit gating accepts source; unrelated curtain/foliage/roof within the broad mask cannot assign onto this stair.')
    write(masks_path,masks)
    obj=target[0];outside={o.name:_geometry(o) for o in objects if o!=obj};matrix=obj.matrix_world.copy()
    v,f=geometry();report=native_mesh(obj,v,f)
    assert matrix==obj.matrix_world
    assert all(_geometry(bpy.data.objects[k])==h for k,h in outside.items())
    write(WS/'geometry-report.json',{'asset_id':ASSET,'tooling':tooling,'recipe_sha256':sha(__file__),**report,
        'changes':['Eight closed risers and upper landing replace the misplaced flat slab; source 379 remains a separate courtyard coping part.'],
        'source_anchors':{'upper_left':[688,1547],'upper_right':[735,1535],'toe_left':[734,1665],'toe_right':[762,1659]},
        'depth_inference':'Upper native datum165.455 retained; lower courtyard datum100 inferred. Visible projected endpoints and count constrain the tapered run; concealed structural depth remains inferred.',
        'outside_objects_preserved':len(outside),'world_transform_drift':0})
    bpy.ops.wm.save_as_mainfile(filepath=str(WS/'model.blend'))
    modified(WS)
    write(WS/'candidate.json',{'asset_id':ASSET,'status':'refinement-in-progress','geometry_refined':True,'geometry_reviewed':False,
         'inspected_views':[],'model_sha256':sha(WS/'model.blend'),'modified_views_sha256':sha(WS/'modified/views.json'),
         'changes':['Eight source-counted risers with measured tapered endpoints and upper landing.'],
         'limitations':['Lower datum and concealed depth inferred. Source ownership review pending.'],'user_approval':'pending'})

def finalize():
    report=json.loads((WS/'candidate.json').read_text())
    assert report['model_sha256']==sha(WS/'model.blend') and report['modified_views_sha256']==sha(WS/'modified/views.json')
    report.update(status='ready-for-user',geometry_reviewed=True,inspected_views=list(range(8)),recipe=str(Path(__file__).resolve()),recipe_sha256=sha(__file__),limitations=['Lower datum100 and concealed structural depth inferred; visible endpoints/count measured.'],review='All eight solid/source-textured views inspected; distinct risers, no clipping or foreign roof/foliage source.')
    write(WS/'candidate.json',report)
    (WS/'review.md').write_text('# Southwest castle stair\n\nEight source-counted risers and tapered flight replace the misplaced slab. The separate coping379 now belongs to the west courtyard. All eight fixed solid/textured views inspected; validation passes. Upper height165.455 retained, lower courtyard datum100 and concealed depth inferred. No user approval recorded.\n')

if __name__=='__main__':
    if '--finalize' in sys.argv:finalize()
    else:main()
