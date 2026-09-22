"""Align forest forms to verified native bark, cut-end and timber silhouettes."""
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def point(x,y,h):return Vector((x,-(y+h)/S,h/C))

def refine(obj):
    node=obj['source_node'];vs=[];fs=[];measure={};notes=[]
    def rings(rows):
        off=len(vs);n=len(rows[0]);vs.extend(v for row in rows for v in row);fs.append(tuple(off+i for i in reversed(range(n))))
        for j in range(len(rows)-1):
            for i in range(n):a=off+j*n+i;b=off+j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
        fs.append(tuple(off+(len(rows)-1)*n+i for i in range(n)))
    def ellipse(cx,ground_y,h,rx,ry,angles):return [point(cx+rx*math.cos(a),ground_y+ry*math.sin(a)-h,h)for a in angles]
    def stem(cx,ground_y,foot,profile):
        ordered=sorted((math.atan2(y-ground_y,x-cx),x,y)for x,y in foot)
        unique=[]
        for a,x,y in ordered:
            if unique and abs(a-unique[-1][0])<.001:
                if (x-cx)**2+(y-ground_y)**2>(unique[-1][1]-cx)**2+(unique[-1][2]-ground_y)**2:unique[-1]=(a,x,y)
            else:unique.append((a,x,y))
        angles=[p[0]for p in unique];foot=[(p[1],p[2])for p in unique];rows=[[point(x,y,0)for x,y in foot]]
        for h,center,rx,ry in profile:rows.append(ellipse(center,ground_y,h,rx,ry,angles))
        rings(rows)
    def pole(base,tip,height,radius):
        a=point(*base,0);b=point(*tip,height);axis=(b-a).normalized();side=axis.cross(Vector((0,0,1)))
        if side.length<1e-5:side=Vector((1,0,0))
        side.normalize();up=axis.cross(side).normalized();rings([[p+radius*(side*math.cos(i*math.tau/12)+up*math.sin(i*math.tau/12))for i in range(12)]for p in [a,b]])
    angles=[i*math.tau/24 for i in range(24)]
    if node=='building-545':
        foot=[(1645,129),(1647,126),(1669,124),(1675,132),(1682,140),(1682,143),(1672,144),(1669,141),(1667,149),(1658,149),(1652,141),(1647,139)]
        stem(1656.5,136.4,foot,[(8,1656.5,10.5,6.5),(24.4,1656.5,12.5,7.0)])
        measure={'cut_end_center_source':[1656.5,112],'cut_end_radii_source':[12.5,7],'ground_center_source':[1656.5,136.4],'root_outline_source':foot}
        notes=['Shift cut end left to its painted center and recover visible asymmetric root flare.','Back root closure and cut-end depth inferred from the observed ellipse.']
    elif node=='building-543':
        rings([ellipse(1867.5,153.3,h,rx,ry,angles)for h,rx,ry in [(0,9.6,5),(5,10,4.7),(13.8,10.5,4.8)]])
        measure={'cut_end_center_source':[1867.5,139.5],'cut_end_radii_source':[10.5,4.8],'ground_center_source':[1867.5,153.3],'source_height':13.8}
        notes=['Match painted cut-end ellipse and shorten the source-facing base to native stump silhouette474.','Rear bark follows the observed rounded section.']
    elif node=='building-544':
        foot=[(1570,43),(1572,38),(1582,35),(1606,35),(1610,42),(1624,55),(1621,58),(1608,55),(1604,86),(1595,87),(1590,73),(1587,63),(1565,61),(1563,56)]
        stem(1593,55,foot,[(12,1593,17,8),(40,1592,17,9),(84.445,1591.5,17.5,9)])
        measure={'root_outline_source':foot,'profile_source_height_center_radii':[[12,1593,17,8],[40,1592,17,9],[84.445,1591.5,17.5,9]]}
        notes=['Widen and shift bole to actual bark silhouette484 and trace long visible front root.','Trunk continues beyond source-image top; closed top and hidden root backs are inferred.']
    elif node=='building-541':
        rings([ellipse(cx,128,h,rx,ry,angles)for h,cx,rx,ry in [(0,1844,16,9),(15,1844,13.5,7),(55,1844,11.5,7),(105,1844,11.5,7),(140.251,1845,18,10)]])
        # Upper-left branch continues beyond the source image; observed lower edge anchors its sweep.
        a=point(1844,8,120);b=point(1800,-13,128);axis=(b-a).normalized();side=axis.cross(Vector((0,1,0))).normalized();up=axis.cross(side).normalized()
        rings([[p+r*(side*math.cos(i*math.tau/16)+up*math.sin(i*math.tau/16))for i in range(16)]for p,r in [(a,12),(b,13)]])
        poles=[((1852,135),(1848,76),48,1.0),((1857,137),(1852,80),49,1.1),((1862,135),(1857,91),35,1.1),((1868,131),(1863,84),38,1.0)]
        for a,b,h,r in poles:pole(a,b,h,r)
        measure={'trunk_ground_center_source':[1844,128],'trunk_bole_radii_source':[11.5,7],'leaning_poles':poles,'branch_source_centers':[[1844,8],[1800,-13]]}
        notes=['Shift main bole seven source pixels left to native473 bark; model separate right-hand leaning poles.','Upper-left branch crosses the image boundary; concealed branch depth and pole rear sections are inferred.']
    elif node=='building-542':
        poles=[((1817,144),(1824,120),24,1.3),((1821,148),(1828,117),25,1.6),((1825,147),(1831,121),24,2),((1830,145),(1833,125),21,1.7),((1835,145),(1835,120),24,1.8),((1840,144),(1839,120),23,1.8),((1848,141),(1843,123),20,2.1)]
        rear=[((1827,137),(1831,111),22,1.8),((1835,138),(1836,109),23,1.8),((1842,136),(1840,115),17,1.7)]
        for a,b,h,r in rear+poles:pole(a,b,h,r)
        measure={'seven_front_poles':poles,'three_visible_upper_cluster_poles':rear}
        notes=['Replace generic15-pole circle with seven measured foreground timbers and three visible upper-cluster pieces.','Separate heights follow source end clusters; concealed pole thickness and rear contacts are inferred.']
    else:raise ValueError(node)
    inverse=obj.matrix_world.inverted();mesh=bpy.data.meshes.new(node+' / measured native source form');mesh.from_pydata([inverse@v for v in vs],[],fs);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.dissolve_degenerate(bm,dist=1e-6,edges=list(bm.edges));bad={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(bad.values()):raise ValueError(bad)
    bm.to_mesh(mesh);bm.free();uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        v=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(v.x/2304,1-(-v.y*S-v.z*C)/3520)
    for mat in obj.data.materials:mesh.materials.append(mat)
    obj.data=mesh
    return {'source_node':node,'measurements':measure,'changes_and_inferences':notes,'topology':bad}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--tooling-dir',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);from render_slots import acquire
    acquire();tooling=select_tooling(a.tooling_dir);from refinement_workspace import modified
    w=a.workspace.resolve();before=sha(w/'model.blend');archive=w/'source-form-reference'/before[:12];
    if archive.exists():
        if sha(archive/'model.blend')!=before:raise ValueError('Reference archive differs')
    else:
        archive.mkdir(parents=True)
        for name in ['model.blend','source-visibility-correction.json']:shutil.copy2(w/name,archive/name)
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));config=json.loads((w/'workspace.json').read_text());obj=next(o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH'and o.get('asset_group')==config['asset_id']);report=refine(obj);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));validation=modified(w)
    report.update(status='PASS',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),before_model_sha256=before,validation=validation,tooling=tooling,recipe_sha256=sha(__file__))
    (w/'source-form-correction.json').write_text(json.dumps(report,indent=2)+'\n');prior=json.loads((w/'source-visibility-correction.json').read_text());prior['status']='superseded-by-source-form-correction';(w/'source-visibility-correction.json').write_text(json.dumps(prior,indent=2)+'\n');print('PASS',config['asset_id'],report['model_sha256'],flush=True)
if __name__=='__main__':main()
