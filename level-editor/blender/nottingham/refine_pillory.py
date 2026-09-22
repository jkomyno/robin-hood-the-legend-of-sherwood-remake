"""Source-measured pillory stocks and individual stage planks for Nottingham."""
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor').is_dir())
WORK=ROOT/'level-editor/work/nottingham-refinement'
SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))
TAG='nottingham_pillory_stocks_v2'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def refine():
    objs={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')=='nottingham-southeast-road-props'}
    if set(objs)!={'building-057','building-058'}:raise ValueError('Pillory canonical parts changed')
    obj=objs['building-058']
    if TAG in obj:return json.loads(obj[TAG])
    native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][58]['points']
    top=[Vector((p['x'],-p['y']/SIN,p['z_top']/COS)) for p in native]
    vertices=[];faces=[]
    def extrude(profile,depth):
        start=len(vertices);n=len(profile);vertices.extend(profile);vertices.extend(p+depth for p in profile)
        faces.extend([tuple(start+i for i in reversed(range(n))),tuple(start+n+i for i in range(n))])
        faces.extend((start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n) for i in range(n))
    def beam(a,b,width):
        axis=(b-a).normalized();side=axis.cross(Vector((0,0,1)))
        if side.length<.01:side=axis.cross(Vector((1,0,0)))
        side.normalize();up=axis.cross(side).normalized()
        ring=[a+side*x*width/2+up*y*width/2 for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        extrude(ring,b-a)
    # Seven source-visible longitudinal planks run from the back edge to the
    # front edge; narrow joints retain their observed direction and spacing.
    joints=[0,.14,.27,.39,.58,.71,.89,1]
    for lo,hi in zip(joints,joints[1:]):
        lo+=.006 if lo else 0;hi-=.006 if hi<1 else 0
        quad=[top[3].lerp(top[0],lo),top[3].lerp(top[0],hi),top[2].lerp(top[1],hi),top[2].lerp(top[1],lo)]
        extrude(quad,Vector((0,0,-3.6/COS)))
    left=Vector((1671.2,-1697/SIN,0));right=Vector((1717,-1684/SIN,0))
    beam(left,left+Vector((0,0,97/COS)),3.8);beam(right,right+Vector((0,0,90/COS)),3.8)
    for p in [top[0],top[3]]:beam(Vector((p.x,p.y,0)),p-Vector((0,0,3.6/COS)),3.6)
    for i in range(4):beam(top[i]-Vector((0,0,5)),top[(i+1)%4]-Vector((0,0,5)),3)
    def source_point(x,y):
        ground_y=1697+(1684-1697)*(x-1671.2)/(1717-1671.2)
        return Vector((x,-ground_y/SIN,(ground_y-y)/COS))
    x0,x1=1674.0,1714.5
    def seam(x):return 1622.0-11.4*(x-x0)/(x1-x0)
    holes=[(1681.5,1.8,2.1),(1694.5,3.2,3.5),(1707.0,1.8,2.1)]
    outlines=[]
    # Two adjoining stock halves share the three apertures; separate thin
    # rails cannot reproduce a pillory. Semicircular cutouts are true openings.
    for upper in (True,False):
        edge=[(x0,seam(x0))]
        for cx,rx,ry in holes:
            edge.append((cx-rx,seam(cx-rx)))
            for j in range(1,13):
                angle=math.pi*(1-j/12);x=cx+rx*math.cos(angle)
                edge.append((x,seam(x)+(-1 if upper else 1)*ry*math.sin(angle)))
        edge.append((x1,seam(x1)))
        far=-8 if upper else 8
        outline=edge+[(x1,seam(x1)+far),(x0,seam(x0)+far)]
        outlines.append(outline);extrude([source_point(x,y) for x,y in outline],Vector((0,2.2,0)))
    mesh=bpy.data.meshes.new('Pillory / split stocks and seven deck planks');inverse=obj.matrix_world.inverted();mesh.from_pydata([inverse@v for v in vertices],[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
    defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(defects.values()):raise ValueError(defects)
    bm.to_mesh(mesh);bm.free();uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        p=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(p.x/2304,1-(-p.y*SIN-p.z*COS)/3520)
    for mat in obj.data.materials:mesh.materials.append(mat)
    obj.data=mesh
    report={'status':'refined-pillory','asset_id':'nottingham-southeast-road-props','source_node':'building-058','topology':defects,
            'stock_board_count':2,'deck_plank_count':7,'stock_top_edge_source':[[x0,seam(x0)-8],[x1,seam(x1)-8]],'stock_bottom_edge_source':[[x0,seam(x0)+8],[x1,seam(x1)+8]],
            'stock_holes_source':[{'center':[x,seam(x)],'radius_xy':[rx,ry]} for x,rx,ry in holes],
            'deck_source_corners':[[p['x'],p['y']-p['z_top']] for p in native],'deck_joint_fractions':joints,'deck_seam_evidence':{'method':'Six distinct dark longitudinal joints measured across the central exposed deck, excluding grain-only secondary minima.','fractions':[.14,.27,.39,.58,.71,.89],'mean_source_luminance':[41,50,44,50,38,47]},
            'changes':['Replaced three generic separated cross rails with two adjoining stock boards and three actual head/hand openings.','Replaced the unbroken deck slab with seven longitudinal timber planks following the artwork direction.','Retained the visible stair part057, tall uprights and stage supports; added no railing.'],
            'inference':['Aperture boundaries are estimated within one to two native pixels from low-resolution artwork.','Stock depth2.2 world units, narrow deck joints and concealed support sections are conservative estimates.','Two adjoining stock halves and seven deck strips simplify irregular wood edges; tiny grain remains source texture.'],
            'approval':'pending','texture_generation':'not started'}
    obj[TAG]=json.dumps(report,sort_keys=True);return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',required=True,type=Path);parser.add_argument('--tooling-dir',required=True,type=Path);a=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    from render_slots import acquire
    acquire();tooling=select_tooling(a.tooling_dir);from refinement_workspace import modified
    w=a.workspace.resolve();archive=w/'pillory-reference'/sha(w/'model.blend')[:12];archive.mkdir(parents=True,exist_ok=False)
    for name in ['model.blend','candidate.json','review.md','recipe.py','pillory-correction.json','pillory-source-anchors.png']:
        if (w/name).is_file():shutil.copy2(w/name,archive/name)
    shutil.copytree(w/'modified',archive/'modified')
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.window.scene=bpy.data.scenes['nottingham Refinement'];report=refine();bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
    validation=modified(w);report.update(validation=validation,tooling=tooling,model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),archive=str(archive),recipe_sha256=sha(__file__))
    (w/'pillory-correction.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','stock_board_count','deck_plank_count','model_sha256']}))
if __name__=='__main__':main()
