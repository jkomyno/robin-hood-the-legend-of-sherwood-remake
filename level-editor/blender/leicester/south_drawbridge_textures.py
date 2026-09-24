"""Bake and reopen independently approved drawbridge endpoint texture packets.

Run with Blender --background --threads 2 --python this_file -- experiment ... .
Each experiment must already contain its approved packet and cached generation.
"""
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "refinement/blender"))
from audit_stored_materials import run
from bake_reviewed_asset import stage


def bake(experiment):
    experiment = Path(experiment).resolve(strict=True)
    frames = json.loads((experiment / "views.json").read_text())
    generation = experiment / "generation-short-no-mask-with-lighting-openrouter"
    output = experiment / "bake-v1"
    bpy.ops.wm.open_mainfile(filepath=str(experiment / "approved-model.blend"))
    stage(experiment / "views.json", generation / "generated-preserved.png",
          output, reconciliation_reference=generation / "generated-raw.png")
    workspace = output / "audit-workspace"
    workspace.mkdir()
    (workspace / "model.blend").symlink_to(output / "worker.blend")
    (workspace / "workspace.json").write_text(json.dumps({
        key: frames[key] for key in ("asset_id", "scene_name", "collection_name")
    }))
    report = run(workspace, output / "export-audit", render=True, export=True,
                 render_object_names=frames.get("render_object_names") or frames["object_names"],
                 frame_manifest=experiment / "views.json")
    if report["problems"]:
        raise RuntimeError(report["problems"])
    print("DRAWBRIDGE_ENDPOINT_COMPLETE", experiment.name, flush=True)


if __name__ == "__main__":
    for argument in sys.argv[sys.argv.index("--") + 1:]:
        bake(argument)
