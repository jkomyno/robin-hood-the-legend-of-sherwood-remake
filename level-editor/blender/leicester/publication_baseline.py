"""Group the exact live-map snapshot without introducing deferred geometry."""
import hashlib,json,shutil,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from group_assets import group_assets

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def mesh_state(collection):
    from bake_reviewed_asset import _materials
    result={}
    for obj in collection.all_objects:
        if obj.type!='MESH':continue
        key=obj['source_node']
        if key in result:raise ValueError('Baseline source has multiple components: '+key)
        result[key]={'vertices':[list(obj.matrix_world@v.co) for v in obj.data.vertices],
            'faces':[(list(f.vertices),f.material_index) for f in obj.data.polygons],
            'uv':{layer.name:[list(loop.uv) for loop in layer.data] for layer in obj.data.uv_layers},
            'materials':_materials(obj),'hidden':[obj.hide_render,obj.hide_viewport]}
    return result

def main():
    root=Path('level-editor/work/leicester-refinement').resolve()
    output=root/'publication-18/baseline';output.mkdir(parents=True,exist_ok=False)
    frozen=json.loads((root/'round-1/freeze-manifest.json').read_text())
    protected=[]
    for entry in frozen['sources']:
        if not entry['origin'].endswith(('.scene.glb','.scene.json')):continue
        if sha(entry['origin'])!=entry['sha256']:raise ValueError('Live map changed since frozen baseline')
        protected.append(entry)
    source=root/'round-1/baseline.blend'
    if sha(source)!=frozen['baseline_sha256']:raise ValueError('Frozen baseline changed')
    catalog_path=root/'catalog-v2/catalog.json';catalog=json.loads(catalog_path.read_text())
    deferred=[]
    for group in catalog['groups']:
        excluded=[part for part in group['parts'] if part['obstacle'] in (273,342)]
        if excluded:deferred.append({'asset_id':group['id'],'parts':excluded})
        group['parts']=[part for part in group['parts'] if part['obstacle'] not in (273,342)]
    (output/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.window.scene=bpy.data.scenes['Leicester Refinement']
    collection=bpy.data.collections['Leicester Working'];before=mesh_state(collection)
    if set(before)!={'ground'}|{f"building-{p['obstacle']:03}" for g in catalog['groups'] for p in g['parts']}:raise ValueError('Exact live coverage differs')
    if len(before)!=391:raise ValueError('Expected390 live parts plus ground')
    target=output/'leicester.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));group_assets(output/'catalog.json')
    after=mesh_state(collection)
    if before!=after:raise ValueError('Grouping altered live mesh geometry, UVs, material or visibility')
    report={'status':'PASS','live_sources':protected,'baseline':str(source),'baseline_sha256':sha(source),
        'grouped_baseline':str(target),'grouped_sha256':sha(target),'catalog_source':str(catalog_path),
        'catalog_source_sha256':sha(catalog_path),'catalog_sha256':sha(output/'catalog.json'),
        'mesh_count':len(before),'canonical_parts':390,'all_live_mesh_state_identical':True,
        'deferred_parts':deferred,'reason':'Parts273/342 are absent from the current live map. Their approved geometry is deferred because their assets are outside this18-texture publication.',
        'scene_name':bpy.context.scene.name,'collection_name':collection.name,'reference_camera':bpy.context.scene.camera.name}
    (output/'provenance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
