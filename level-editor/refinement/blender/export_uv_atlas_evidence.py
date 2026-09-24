"""Read-only evidence for a single opaque, directly UV-mapped saved atlas."""
import hashlib,json,sys
from pathlib import Path
import bpy
import numpy as np

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def export(workspace,output):
    workspace,output=Path(workspace).resolve(),Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    model=workspace/'model.blend'
    bpy.ops.wm.open_mainfile(filepath=str(model))
    config=json.loads((workspace/'workspace.json').read_text())
    objects=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==config['asset_id']]
    if len(objects)!=1:raise ValueError('UV atlas requires exactly one visible receiver')
    obj=objects[0]
    if obj.modifiers:raise ValueError('Apply modifiers in the approved geometry before UV atlas preparation')
    used={p.material_index for p in obj.data.polygons}
    if len(used)!=1:raise ValueError('UV atlas requires one used material')
    material=obj.data.materials[next(iter(used))]
    if not material or not material.use_nodes:raise ValueError('Expected explicit atlas material nodes')
    nodes=material.node_tree.nodes
    images=[n for n in nodes if n.type=='TEX_IMAGE' and n.image]
    if len(images)!=1:raise ValueError('Expected one atlas image')
    texture=images[0];image=texture.image
    links=list(material.node_tree.links)
    vector=[l for l in links if l.to_node==texture and l.to_socket.name=='Vector']
    if len(vector)!=1 or vector[0].from_node.type!='UVMAP':raise ValueError('Atlas coordinates must come directly from a named UV map')
    outputs=[n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output]
    if len(outputs)!=1:raise ValueError('Expected one active material output')
    surface=[l for l in links if l.to_node==outputs[0] and l.to_socket.name=='Surface']
    if len(surface)!=1 or surface[0].from_node!=texture or surface[0].from_socket.name!='Color':raise ValueError('Requires opaque direct image color; physical alpha or shader mixing is unsupported')
    if not image.packed_file:raise ValueError('Approved atlas must be packed')
    path=Path(bpy.path.abspath(image.filepath)).resolve(strict=True)
    reference=bpy.data.images.load(str(path),check_existing=False)
    reference.alpha_mode=image.alpha_mode;reference.reload()
    pixels=np.array(image.pixels[:],dtype=np.float32)
    try:
        if tuple(image.size)!=tuple(reference.size) or not np.array_equal(pixels,np.array(reference.pixels[:],dtype=np.float32)):
            raise ValueError('Packed atlas differs from referenced image')
    finally:bpy.data.images.remove(reference)
    uv_name=vector[0].from_node.uv_map;uv=obj.data.uv_layers.get(uv_name)
    if uv is None:raise ValueError('Named atlas UV map is absent')
    mesh=obj.data;mesh.calc_loop_triangles();matrix=obj.matrix_world.copy()
    triangles=[]
    for tri in mesh.loop_triangles:
        world=[matrix@mesh.vertices[i].co for i in tri.vertices]
        normal=(world[1]-world[0]).cross(world[2]-world[0])
        if normal.length<1e-10:raise ValueError('Degenerate world triangle')
        normal.normalize()
        if mesh.polygons[tri.polygon_index].use_smooth:raise ValueError('Flat face normals required for exact triangle atlas lighting')
        normal_matrix=matrix.to_3x3().inverted().transposed()
        if any(((normal_matrix@mesh.corner_normals[i].vector).normalized()-normal).length>1e-5 for i in tri.loops):
            raise ValueError('Custom corner normals differ from flat triangle lighting')
        triangles.append(dict(polygon=tri.polygon_index,vertices=list(tri.vertices),world=[list(p) for p in world],uv_top_left=[[uv.data[i].uv.x,1-uv.data[i].uv.y] for i in tri.loops],normal=list(normal)))
    geometry=dict(vertices=[list(v.co) for v in mesh.vertices],faces=[list(p.vertices) for p in mesh.polygons],matrix=[list(row) for row in matrix],uv={layer.name:[list(v.uv) for v in layer.data] for layer in mesh.uv_layers})
    report=dict(version=1,asset_id=config['asset_id'],workspace=str(workspace),model_sha256=sha(model),modified_views_sha256=sha(workspace/'modified/views.json'),receiver=obj.name,source_node=obj.get('source_node'),material=material.name,material_slot=next(iter(used)),physical_opacity='OPAQUE',direct_image_color=True,atlas_path=str(path),atlas_sha256=sha(path),packed_pixel_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),atlas_dimensions=list(image.size),alpha_mode=image.alpha_mode,interpolation=texture.interpolation,uv_layer=uv_name,geometry=geometry,geometry_uv_matrix_sha256=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(',',':')).encode()).hexdigest(),triangles=triangles)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    return dict(output=str(output),triangles=len(triangles),model_sha256=report['model_sha256'])

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if len(args)!=2:raise ValueError('Expected workspace new-evidence.json')
    print(json.dumps(export(*args)))
