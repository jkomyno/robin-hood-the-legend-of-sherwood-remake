"""Blender export regression for physical leaf opacity and separate ownership."""
import json
from pathlib import Path
import struct
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from export_editor import export_editor, enforce_foliage_contract

collection = bpy.data.collections.new('FoliageFixture Working')
bpy.context.scene.collection.children.link(collection)
mesh = bpy.data.meshes.new('foliage card')
mesh.from_pydata([(-1,0,-1),(1,0,-1),(1,0,1),(-1,0,1)], [], [(0,1,2,3)])
uv = mesh.uv_layers.new(name='UVMap')
for loop, xy in zip(uv.data, [(0,0),(1,0),(1,1),(0,1)]): loop.uv=xy
colors = mesh.color_attributes.new(name='source_ownership', type='FLOAT_COLOR', domain='CORNER')
for loop in colors.data: loop.color=(0,1,1,1)
mesh.color_attributes.active_color=colors
obj=bpy.data.objects.new('source card',mesh);collection.objects.link(obj)
for key,value in {'source_node':'building-001','asset_group':'foliage','asset_name':'Foliage','part_name':'Card'}.items(): obj[key]=value
material=bpy.data.materials.new('Physical foliage');material.use_nodes=True
for key,value in {'foliage_physical_opacity':True,'opacity_semantics':'physical-coverage','source_ownership_semantics':'separate-mask','source_ownership_channel':'vertex-color-r','source_ownership_backface':'inferred','foliage_backface_fill':'neutral','foliage_unlit':True}.items():material[key]=value
image=bpy.data.images.new('leaf cutout',width=2,height=2,alpha=True)
image.pixels=[0,1,0,1, 0,1,0,0, 0,1,0,0, 0,1,0,1];image.pack()
texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=image
principled=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
material.node_tree.links.new(texture.outputs['Color'],principled.inputs['Base Color'])
material.node_tree.links.new(texture.outputs['Alpha'],principled.inputs['Alpha'])
mesh.materials.append(material)
# Cycles uses an explicit shader discard; export must normalize its temporary
# clone without changing this authored output connection.
nodes=material.node_tree.nodes
backfacing=nodes.new('ShaderNodeNewGeometry')
transparent=nodes.new('ShaderNodeBsdfTransparent')
mix=nodes.new('ShaderNodeMixShader')
output_node=next(node for node in nodes if node.type=='OUTPUT_MATERIAL')
material.node_tree.links.new(backfacing.outputs['Backfacing'],mix.inputs[0])
material.node_tree.links.new(principled.outputs['BSDF'],mix.inputs[1])
material.node_tree.links.new(transparent.outputs[0],mix.inputs[2])
material.node_tree.links.new(mix.outputs[0],output_node.inputs['Surface'])
paired='--paired' in sys.argv
if paired:
    material['foliage_card_sides']='paired-one-sided'
    reverse=obj.copy();reverse.data=mesh.copy();reverse.name='neutral reverse';collection.objects.link(reverse)
    reverse.data.flip_normals();reverse.location.y=0.001
    back=material.copy();back.name='Neutral reverse';reverse.data.materials[0]=back
    gray=image.copy();gray.name='neutral cutout';gray.pixels=[.24,.24,.24,1, .24,.24,.24,0, .24,.24,.24,0, .24,.24,.24,1];gray.pack()
    next(node for node in back.node_tree.nodes if node.type=='TEX_IMAGE').image=gray

output=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else Path(tempfile.mkdtemp())/'foliage.glb'
export_editor('FoliageFixture',output,asset_id='foliage')
data=output.read_bytes();length=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+length])
exported=doc['materials'][0]
assert exported['alphaMode']=='MASK' and exported['alphaCutoff']==0.5 and exported['doubleSided'] is (not paired)
assert exported['extras']['source_ownership_channel']=='vertex-color-r'
attributes=doc['meshes'][0]['primitives'][0]['attributes']
assert 'COLOR_0' in attributes
accessor=doc['accessors'][attributes['COLOR_0']]
view=doc['bufferViews'][accessor['bufferView']]
offset=20+length+8+view.get('byteOffset',0)+accessor.get('byteOffset',0)
component=accessor['componentType']
red=struct.unpack_from({5126:'<f',5123:'<H',5121:'<B'}[component],data,offset)[0]
assert red==0, ('Ownership red was not exported as COLOR_0',red,attributes)
assert 'KHR_materials_unlit' in exported['extensions']
assert mesh.materials[0] is material
assert principled.inputs['Base Color'].links[0].from_node == texture
assert output_node.inputs['Surface'].links[0].from_node == mix
bad={'materials':[exported],'meshes':[{'primitives':[{'material':0,'attributes':{}}]}]}
try: enforce_foliage_contract(bad)
except ValueError: pass
else: raise AssertionError('missing ownership accepted')
opaque={'materials':[{'alphaMode':'OPAQUE','extras':{'source_ownership_fill':'synthesized'}}]}
before=json.dumps(opaque);enforce_foliage_contract(opaque);assert json.dumps(opaque)==before
print('FOLIAGE EXPORT PASS',output)
