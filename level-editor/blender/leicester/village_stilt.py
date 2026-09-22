"""Source-constrained platform and open timber frame for the south stilt shed.

Call refine(workspace, config, by_node) inside a prepared worker copy. The
native silhouette constrains visible joinery; hidden depth remains a hypothesis.
"""
import json
import math
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector

try:
    from .village_details import silhouette_prism, stilt_ladder
except ImportError:
    from village_details import silhouette_prism, stilt_ladder


SINE = math.sin(math.radians(35))
COSINE = math.cos(math.radians(35))


def point(px, py, z):
    return Vector((px, (-py-z*COSINE)/SINE, z))


def platform(obj):
    # The final low corner replaces the oversized foreground collision tip.
    # Native185's straight cutoff is an ownership boundary, not a measured
    # geological edge. The hidden closure follows that conservative boundary.
    anchors = [(1814.4,1836.,73.2),(1848.9,1792.3,73.2),
               (1885.,1759.,70.),(1974.,1748.7,44.2),
               (2078.5,1791.1,.5),(1960.,1843.,.5)]
    top = [point(*p) for p in anchors]
    bottom = [Vector((p.x,p.y,-.5)) for p in top]
    center = sum(top,Vector())/len(top)
    vertices = top+bottom+[center]
    n=len(top)
    faces=[(i,(i+1)%n,2*n) for i in range(n)]
    faces += [(i,n+i,n+(i+1)%n,(i+1)%n) for i in range(n)]
    faces += [tuple(reversed(range(n,2*n)))]
    mesh=bpy.data.meshes.new('Leicester Stilt Source Platform')
    mesh.from_pydata([obj.matrix_world.inverted()@p for p in vertices],[],faces)
    mesh.uv_layers.new(name='UVMap')
    for material in obj.data.materials:mesh.materials.append(material)
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bad=sum(not e.is_manifold for e in bm.edges)
    deg=sum(f.calc_area()<1e-8 for f in bm.faces)
    bm.to_mesh(mesh);bm.free()
    if bad or deg:raise ValueError(f'Platform topology invalid: {bad}/{deg}')
    obj.data=mesh
    return {'source_anchors_xyz':anchors,'nonmanifold_edges':bad,
            'degenerate_faces':deg,'inference':'Retained inherited rear heights; '
            'foreground low corner constrained to native185 cutoff. This is '
            'an ownership boundary and a conservative hidden closure, not a '
            'fully observed rock footprint. Closed underside is inferred.'}


def frame(workspace,config,update_masks=True):
    anchors=[(1983.,1805.,72.),(2008.,1937.,0.),(2078.,1916.,0.)]
    inverse=np.linalg.inv(np.array([[p[0],p[1],1.] for p in anchors]))
    weights=inverse@np.array([p[2] for p in anchors])
    def ramp(px,py):return point(px,py,float(np.dot([px,py,1.],weights)))
    # Keep the two upright tips physically upright instead of folding them
    # into the sloping rails. Pixel cuts follow the separately visible posts.
    def left(px,py):return 2010<=px<=2017 and 1894<=py<=1930
    def right(px,py):return 2059<=px<=2066 and 1878<=py<=1915
    def upright(foot):
        def plane(px,py):return point(px,py,(foot-py)/COSINE)
        return plane
    components=[('inclined-frame',ramp,lambda x,y:not(left(x,y) or right(x,y))),
                ('left-upright',upright(1930.),left),
                ('right-upright',upright(1915.),right)]
    reports=[];assignments=[]
    for component,plane,clip in components:
        mesh,report=silhouette_prism(workspace,179,plane,3.,clip)
        name='Leicester Stilt '+component.replace('-',' ').title()
        obj=bpy.data.objects.get(name)
        if obj is None:
            obj=bpy.data.objects.new(name,mesh)
            bpy.data.collections[config['collection_name']].objects.link(obj)
        else:obj.data=mesh
        obj['source_node']='building-126';obj['asset_group']=config['asset_id']
        obj['projection_component']=component;obj['part_name']=component.replace('-',' ')
        reports.append({'component':component,**report})
        assignments.append({'source_node':'building-126','projection_component':component,
                            'mask_indices':[179],'reviewed':True,
                            'evidence':'stilt-frame-grid.png: two inclined rails, '
                            'two crossbraces and two upright tips. Native179 '
                            'silhouette retained; inferred thickness3 and topheight72.'})
    if update_masks:
        path=Path(config['source_mask_manifest']);contract=json.loads(path.read_text())
        rows=contract['projections']['exterior']['assignments']
        names={c[0] for c in components}
        rows[:]=[r for r in rows if not(r.get('source_node')=='building-126' and r.get('projection_component') in names)]
        rows.extend(assignments);path.write_text(json.dumps(contract,indent=2)+'\n')
    return {'components':reports,'source_plane_anchors_xyz':anchors,
            'inclined_rails':2,'crossbraces':2,'upright_tips':2,
            'inference':'Topheight72 follows shed floor; footheight0, hidden '
            'thickness3 and front-post depth are inferred. Native183/184 repeat '
            'native179 and are not additional timbers. Intercomponent contacts '
            'and platform support require eight-view visual review.'}


def refine(workspace,config,by_node,update_masks=True):
    return {'platform':platform(by_node['building-126']),
            'frame':frame(workspace,config,update_masks),
            'ladder':stilt_ladder(workspace,by_node['building-129'])}


def main():
    import argparse
    import sys
    parser=argparse.ArgumentParser()
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--reproject',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    workspace=args.workspace.resolve()
    config=json.loads((workspace/'workspace.json').read_text())
    if config['asset_id']!='leicester-south-stilt-shed':
        raise ValueError('Stilt recipe requires its own prepared asset workspace')
    helpers=next(p/'level-editor/blender' for p in Path(__file__).resolve().parents
                 if (p/'level-editor/blender/refinement_workspace.py').exists())
    sys.path.insert(0,str(helpers))
    from refinement_workspace import validate,modified
    from leicester.village_shells import repair
    validate(workspace)
    objects=[o for o in bpy.data.collections[config['collection_name']].all_objects
             if o.type=='MESH' and o.get('asset_group')==config['asset_id']
             and not o.get('projection_component')]
    by_node={o['source_node']:o for o in objects}
    if set(by_node)!={f'building-{i:03}' for i in range(126,137)}:
        raise ValueError('Stilt canonical membership differs from nodes126–136')
    shell_reports=[repair(o) for o in objects]
    report=refine(workspace,config,by_node)
    report.update(asset_id=config['asset_id'],shell_repairs=shell_reports,
                  world_transform_drift=0,projection_status='STALE')
    (workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection/stilt-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    validate(workspace)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    if args.reproject:print(json.dumps(modified(workspace)))


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    main()
