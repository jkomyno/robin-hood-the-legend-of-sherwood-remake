"""Re-apply the native-order supersession rule to an existing revealed bake (properties only).

    blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/revealed_state_bake_order_fix.py -- <bake dir> <new dir>

states-bake-v1 resolved two-state overlaps by texel count; the reviewed rule is native patch
order (the later patch is composited on top). Only reveal_hide_when_applied on appearance
copies changes; geometry, UVs, materials and images are checked byte-identical.
"""
import hashlib, json, sys
from pathlib import Path
import bpy
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_slots
import revealed_state_bake as B

src, dst = map(Path, sys.argv[sys.argv.index('--') + 1:])
dst = dst.resolve()
if dst.exists():
    raise FileExistsError(dst)
render_slots.acquire()
report = json.loads((src / 'revealed-bake.json').read_text())
worker = src / 'worker.blend'
if B.sha(worker) != report['worker_sha256']:
    raise ValueError('Bake worker changed')
bpy.ops.wm.open_mainfile(filepath=str(worker.resolve()))
sources = json.loads((B.REVIEW / 'sources/manifest.json').read_text())['states']
geometry = {o.name: B.RG.fingerprint(o) for o in B.working_meshes()}
changes = []
for row in report['conflicts']:
    loser_patch = sources[row['loser']]['applied_patches'][-1]
    winner_patch = sources[row['winner']]['applied_patches'][-1]
    if B.native_order(winner_patch) > B.native_order(loser_patch):
        continue  # already native order
    loser = bpy.data.objects[f"{row['object']} :: revealed {row['loser']}"]
    winner = bpy.data.objects[f"{row['object']} :: revealed {row['winner']}"]
    loser['reveal_hide_when_applied'] = sorted(set(loser.get('reveal_hide_when_applied', [])) - {winner_patch})
    if not loser['reveal_hide_when_applied']:
        del loser['reveal_hide_when_applied']
    winner['reveal_hide_when_applied'] = sorted(set(winner.get('reveal_hide_when_applied', [])) | {loser_patch})
    changes.append({'object': row['object'], 'now_on_top': row['loser'], 'now_hidden_when_both': row['winner']})
if any(B.RG.fingerprint(o) != geometry[o.name] for o in B.working_meshes()):
    raise RuntimeError('Geometry/UV/material slots changed')
dst.mkdir(parents=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(dst / 'worker.blend'), compress=False)
report.update(order_fix={'from_worker_sha256': report['worker_sha256'], 'changes': changes,
                         'rule': 'later native patch on top when both are applied'},
              worker_sha256=B.sha(dst / 'worker.blend'))
(dst / 'revealed-bake.json').write_text(json.dumps(report, indent=2) + '\n')
print('ORDER-FIX', json.dumps(changes), report['worker_sha256'])
