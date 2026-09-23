"""Run in background Blender; long atlas labels must resolve after repeated bakes."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from source_projection_bake import bind_uv_layer
mesh=bpy.data.meshes.new('Long UV label regression')
mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
mat=bpy.data.materials.new('Long UV label regression');mat.use_nodes=True
node=mat.node_tree.nodes.new('ShaderNodeUVMap')
for label in ['Owned source / '+('interior-state-'*12), 'Owned source / '+('屋根é'*24)]:
 first=bind_uv_layer(mesh,node,label)
 first.data[0].uv=(0.25,0.75)
 assert len(first.name.encode('utf-8'))<=63
 assert mesh.uv_layers.get(node.uv_map)==first
 second=bind_uv_layer(mesh,node,label)
 assert second==first and tuple(second.data[0].uv)==(0.25,0.75)
 other=bind_uv_layer(mesh,node,label+'other')
 assert other!=first and mesh.uv_layers.get(node.uv_map)==other
assert len(mesh.uv_layers)==4
print('PASS repeated long ASCII/Unicode UV bindings preserve layers and distinguish common prefixes')
