"""Replace the grouped scene's ground mesh with a reviewed terrain workspace's ground.

blender --background --python-exit-code 1 --python swap_terrain.py -- SOURCE TERRAIN_MODEL OUTPUT
Only the object whose source_node is 'ground' changes (mesh data and materials); every
other object's world transform and vertices are checked unchanged.
"""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slots import acquire
acquire()
import bpy
source, terrain, output = map(Path, sys.argv[sys.argv.index('--') + 1:])
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
if output.exists():
    raise FileExistsError(output)
bpy.ops.wm.open_mainfile(filepath=str(source.resolve()))
working = bpy.data.collections['lincoln Working']
grounds = [o for o in working.all_objects if o.type == 'MESH' and o.get('source_node') == 'ground']
if len(grounds) != 1:
    raise ValueError('Expected one ground object in the source scene')
target = grounds[0]
before = {o.name: (o.matrix_world.copy(), [tuple(v.co) for v in o.data.vertices]) for o in working.all_objects
          if o.type == 'MESH' and o is not target}
with bpy.data.libraries.load(str(terrain.resolve()), link=False) as (src, dst):
    names = list(src.objects)
    dst.objects = list(names)
loaded = [o for o in dst.objects if o and o.type == 'MESH' and o.get('source_node') == 'ground']
if len(loaded) != 1:
    raise ValueError('Expected one ground object in the terrain model')
new = loaded[0]
# Unlinked library objects have no evaluated world matrix; compare local transform and parent identity.
base = lambda o: o.parent.name.rsplit('.', 1)[0] if o.parent and o.parent.name.rsplit('.', 1)[-1].isdigit() else (o.parent.name if o.parent else None)
if base(new) != base(target) or any(
        abs(new.matrix_basis[r][c] - target.matrix_basis[r][c]) > 1e-6 for r in range(4) for c in range(4)):
    raise ValueError('Terrain ground transform differs')
old_mesh = target.data
target.data = new.data
for obj in dst.objects:
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.data.meshes.remove(old_mesh)
bpy.data.orphans_purge(do_local_ids=True, do_recursive=True)
for o in working.all_objects:
    if o.type == 'MESH' and o is not target:
        m, v = before[o.name]
        if [tuple(x.co) for x in o.data.vertices] != v or any(abs(o.matrix_world[r][c] - m[r][c]) > 1e-6 for r in range(4) for c in range(4)):
            raise RuntimeError('Swap changed ' + o.name)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(output.resolve()))
report = {'version': 1, 'source': str(source), 'source_sha256': sha(source), 'terrain_model': str(terrain),
          'terrain_model_sha256': sha(terrain), 'output_sha256': sha(output), 'ground_vertices': len(target.data.vertices),
          'unchanged_objects': len(before)}
output.with_suffix('.swap.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
