"""Build compact castle rock masses from explicit source crests, seams and feet."""
import json,sys,hashlib,shutil
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-castle-west-rocks'
sys.path.insert(0,str(Path(__file__).parent))
from refine_forest_outcrop_lobes import lobe,SIN,COS
# Original full-image coordinates. Hidden foliage-covered crests are inferred;
# exposed stone corners and feet are observed with about 2-3 pixel uncertainty.
SHAPES={
478:[('southwest sloping face',0,[(94,2226),(118,2214),(149,2225),(151,2255),(137,2270),(116,2297),(100,2291),(82,2278)]),('south central crest and face',0,[(143,2238),(161,2215),(181,2207),(205,2217),(226,2208),(244,2220),(255,2251),(247,2274),(218,2283),(195,2315),(172,2321),(159,2304)]),('south eastern rock face',0,[(242,2246),(261,2236),(285,2245),(288,2257),(308,2257),(339,2271),(353,2288),(330,2292),(308,2310),(282,2319),(264,2302),(250,2289)])],
479:[('western upper slab',0,[(0,2060),(19,2077),(32,2070),(47,2082),(45,2110),(25,2157),(4,2174),(0,2158)]),('western middle slab',0,[(31,2145),(63,2140),(81,2158),(81,2184),(68,2218),(49,2230),(24,2213),(10,2197)]),('western lower slab',0,[(71,2190),(99,2198),(119,2218),(125,2244),(102,2272),(91,2285),(73,2275),(61,2255),(57,2229)])],
480:[('upper ridge left stone',5,[(100,2074),(116,2049),(133,2036),(146,2038),(172,2071),(180,2097),(168,2110),(145,2107),(125,2092),(100,2090)]),('upper ridge crest stone',10,[(140,2035),(158,2020),(177,2007),(191,2000),(207,2017),(220,2041),(222,2060),(211,2077),(199,2093),(180,2102),(173,2070)])],
481:[('upper ridge right return',3,[(219,2055),(240,2050),(240,2076),(226,2092),(210,2100),(196,2101),(212,2080)]),('upper ridge lower return',0,[(224,2088),(240,2077),(239,2116),(232,2130),(222,2117),(213,2103)])],
484:[('eastern rounded ledge',0,[(647,2083),(662,2074),(680,2083),(693,2094),(711,2092),(733,2102),(744,2118),(737,2134),(718,2146),(689,2146),(664,2138),(648,2124)]),('eastern central sloping stone',0,[(734,2110),(751,2089),(771,2096),(786,2114),(776,2139),(756,2147),(741,2163),(730,2153),(724,2138)]),('eastern wall foot stone',0,[(779,2112),(800,2100),(813,2112),(829,2133),(844,2137),(858,2154),(846,2167),(826,2156),(812,2153),(791,2162),(777,2142)])]
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def geometry():return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons],tuple(tuple(r)for r in o.matrix_world))for o in bpy.data.objects if o.type=='MESH'}
def refine():
    reports=[]
    for o in bpy.data.collections['nottingham Working'].all_objects:
        if o.type!='MESH' or o.get('asset_group')!=ASSET:continue
        n=int(o['source_node'][-3:]);vertices=[];faces=[]
        for label,height,outline in SHAPES[n]:
            v,f=lobe(outline,height);start=len(vertices);vertices+=v;faces +=[tuple(start+i for i in face)for face in f]
        m=bpy.data.meshes.new(f'Castle rock {n} / measured contour lobes');inv=o.matrix_world.inverted();m.from_pydata([inv@v for v in vertices],[],faces);m.update();bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-7 for f in bm.faces);assert bad==0 and deg==0;(bm.to_mesh(m));bm.free();m.uv_layers.new(name='Source projection')
        for mat in o.data.materials:m.materials.append(mat)
        o.data=m
        reports.append({'node':n,'vertices':len(m.vertices),'triangles':len(m.polygons),'nonmanifold_edges':bad,'degenerate_faces':deg,'source_lobes':[{'name':name,'elevation':e,'outline':p,'visibility':'Mixed: exposed crests, seams and feet observed; foliage-covered perimeter inferred.','uncertainty_native_pixels':[2,3]}for name,e,p in SHAPES[n]],'source_xy':[[v.x,-v.y*SIN-v.z*COS]for v in vertices],'edges':[list(e.vertices)for e in m.edges]})
    return reports

def main():
    from render_slots import acquire
    from freeze_tooling import select_tooling
    acquire();tooling=select_tooling(W/'tooling/94116d984f92dbae');from refinement_workspace import prepare,modified
    import refinement_review
    old=W/'round-14/assets'/ASSET;out=W/'round-15/assets'/ASSET;before=sha(old/'model.blend');bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
    if not out.exists():
        planned=[v for shapes in SHAPES.values()for name,e,p in shapes for v in lobe(p,e)[0]];fit=refinement_review.fit_camera
        def fitting(*a,**k):k['points']=list(k['points'])+planned;k['padding']=1.12;return fit(*a,**k)
        refinement_review.fit_camera=fitting
        prepare(out,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=320,height=320,context_padding=30)
        refinement_review.fit_camera=fit
    else:bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
    outside={k:v for k,v in geometry().items()if bpy.data.objects[k].get('asset_group')!=ASSET};r=refine();first=geometry();refine();assert geometry()==first;assert outside=={k:v for k,v in geometry().items()if bpy.data.objects[k].get('asset_group')!=ASSET};bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));valid=modified(out);assert sha(old/'model.blend')==before
    (out/'inspection').mkdir(exist_ok=True);(out/'geometry-report.json').write_text(json.dumps({'status':'PASS','asset_id':ASSET,'objects':r,'idempotence':'PASS','outside_preservation':'PASS','previous_model_unchanged':True,'model_sha256':sha(out/'model.blend'),'tooling':tooling['snapshot_id'],'validation':valid,'limitations':['Measured stone crests, seams and feet constrain exposed profiles to about 2-3 source pixels; bush-covered crests are inferred compact continuations.','Hidden rear depth, inter-lobe overlap and underside ground contacts are inferred.','Preserve native foreground exclusions416/417/420/423 for478-481 and412/414 for484; those source-hidden rock areas remain gray. No high foliage canopy is inferred as rock geometry.']},indent=2)+'\n');shutil.copy2(__file__,out/'recipe.py');print('PASS',sha(out/'model.blend'))
if __name__=='__main__':main()
