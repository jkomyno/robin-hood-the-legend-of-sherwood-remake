"""Stage selected forest and camp assets from the refined Sherwood workspace."""
import bpy,sys,argparse,json,struct
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'refinement'/'blender'))
from export_editor import export_asset_library
args=argparse.ArgumentParser()
args.add_argument('--output',required=True)
opts=args.parse_args(sys.argv[sys.argv.index('--')+1:])
# Freeze the animated canopy atlas to one frame and preserve its cutout alpha.
# The runtime material uses explicit UVs rather than Blender vector-node drivers.
bpy.context.scene.frame_set(1)
leaf_materials={}
def static_leaves(obj):
    if 'Source canvas' not in obj.data.uv_layers:return
    source=obj.data.materials[0]
    tex=next(n for n in source.node_tree.nodes if n.type=='TEX_IMAGE')
    transform=tex.inputs['Vector'].links[0].from_node
    scale=transform.inputs[0].links[0].from_node.inputs[1].default_value
    offset=transform.inputs[1].default_value
    atlas=tex.image;aw,ah=atlas.size
    w,h=round(scale[0]*aw),round(scale[1]*ah);x,y=round(offset[0]*aw),round(offset[1]*ah)
    if source.name not in leaf_materials:
        pixels=np.empty(aw*ah*4,dtype=np.float32);atlas.pixels.foreach_get(pixels)
        tile=np.zeros((h+2,w+2,4),dtype=np.float32)
        tile[1:-1,1:-1]=pixels.reshape(ah,aw,4)[y:y+h,x:x+w]
        image=bpy.data.images.new(source.name+' static',width=w+2,height=h+2,alpha=True)
        image.pixels.foreach_set(tile.ravel());image.pack()
        mat=bpy.data.materials.new(source.name+' runtime');mat.use_nodes=True
        nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
        uv=nodes.new('ShaderNodeUVMap');uv.uv_map='Static leaves'
        sample=nodes.new('ShaderNodeTexImage');sample.image=image;sample.extension='EXTEND'
        shader=nodes.new('ShaderNodeBsdfPrincipled');shader.inputs['Roughness'].default_value=1
        out=nodes.new('ShaderNodeOutputMaterial')
        links.new(uv.outputs[0],sample.inputs['Vector'])
        links.new(sample.outputs['Color'],shader.inputs['Base Color'])
        links.new(sample.outputs['Alpha'],shader.inputs['Alpha'])
        links.new(shader.outputs[0],out.inputs[0])
        mat.surface_render_method='DITHERED'
        leaf_materials[source.name]=mat
    uv=obj.data.uv_layers.new(name='Static leaves');original=obj.data.uv_layers['Source canvas']
    for i,loop in enumerate(original.data):uv.data[i].uv=((loop.uv.x*w+1)/(w+2),(loop.uv.y*h+1)/(h+2))
    for i in range(len(obj.data.materials)):obj.data.materials[i]=leaf_materials[source.name]

working=bpy.data.collections.new('Sherwood Working')
bpy.context.scene.collection.children.link(working)

def add(key,label,obstacle,select):
    sources=[o for o in list(bpy.data.objects) if o.type=='MESH' and not o.hide_render and select(o.name)]
    if not sources:raise ValueError('Missing '+key)
    for source in sources:
        obj=source.copy();obj.data=source.data.copy();working.objects.link(obj)
        static_leaves(obj)
        obj['asset_group']='sherwood-'+key;obj['asset_name']=label
        obj['source_node']=f'building-{obstacle:03d}';obj['source_obstacle']=obstacle;obj['part_name']=label
    print(key,len(sources))

for n,key,label in [(30,'forked-oak','Forked woodland oak'),(25,'river-oak','Irregular river oak'),(36,'broad-oak','Broad woodland oak'),(34,'leaning-tree','Leaning woodland tree'),(40,'spreading-oak','Spreading woodland oak')]:
    add(key,label,n,lambda s,n=n:s.startswith(f'Tree {n:03d} -') or (s.startswith('Sherwood -') and f'tree {n:03d} -' in s))
for n in [57,59,62,67,74,80]:
    add(f'rock-{n:03d}','Riverbank boulder '+str(n),n,lambda s,n=n:s.startswith(f'Rock {n:03d} -'))
for n in [11,12,14]:
    add(f'camp-table-{n:03d}','Timber market table '+str(n),n,lambda s,n=n:s.startswith(f'Camp {n:03d} -') or s==f'building-{n:03d}.001')
add('cooking-cauldron','Iron cooking cauldron',112,lambda s:s.startswith('Cooking cauldron -'))
add('round-stool','Round wooden stool',23,lambda s:s.startswith('Stool 23 '))
add('cooper-barrel','Coopered barrel',5,lambda s:s.startswith('Cooperage 005 '))
add('supply-barrel','Horizontal supply barrel',56,lambda s:s.startswith('Supply barrel'))
for n in [116,117,118]:
    add(f'logs-{n}','Cut timber '+str(n),n,lambda s,n=n:s.startswith(f'Log pile {n} '))
print(export_asset_library('Sherwood',opts.output,ROOT.parent/'datadirs/fullgame_gog_hackable/Data/Levels/Sherwood.rhp.json'))

# Keep baked colors unlit and canopy cutouts available to depth/shadow passes.
for file in Path(opts.output).glob('*/model.glb'):
    data=file.read_bytes();length,kind=struct.unpack_from('<II',data,12)
    doc=json.loads(data[20:20+length])
    for material in doc.get('materials',[]):
        material.setdefault('extensions',{})['KHR_materials_unlit']={}
        if 'runtime' in material.get('name',''):
            material['alphaMode']='MASK';material['alphaCutoff']=.35;material['doubleSided']=True
        elif 'emissiveTexture' in material:
            material['pbrMetallicRoughness']={'baseColorTexture':material.pop('emissiveTexture')}
            material.pop('emissiveFactor',None)
    doc['extensionsUsed']=list(set(doc.get('extensionsUsed',[])+['KHR_materials_unlit']))
    chunk=json.dumps(doc,separators=(',',':')).encode();chunk+=b' '*(-len(chunk)%4)
    binary=data[20+length:]
    file.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(chunk)+len(binary))+struct.pack('<II',len(chunk),kind)+chunk+binary)
