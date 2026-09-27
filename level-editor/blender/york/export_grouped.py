"""Export the named York grouping to an isolated map and reusable asset library."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'level-editor/work/york-refinement'


def main():
    import bpy
    sys.path.insert(0,str(ROOT/'level-editor/refinement'))
    from render_slots import acquire
    acquire()
    sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
    from export_editor import export_editor
    source=OUT/'grouped/york-grouped.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.window.scene=bpy.data.scenes['york Refinement']
    catalog=json.loads((ROOT/'level-editor/refinement/catalogs/york.json').read_text())
    level=json.loads((OUT/'baseline/york.rhp.json').read_text())
    current=json.loads((OUT/'baseline/published-map.json').read_text())
    report=export_editor('york',OUT/'stage/york.rhlos-map.json',catalog=catalog,level=level,
                         map_settings={'size':current['size'],'camera':current['camera']})
    output=OUT/'stage/york.rhlos-map.json'
    document=json.loads(output.read_text())
    # Keep native map metadata available for later gameplay/state refinement.
    if 'sceneMetadata' in current:
        document['sceneMetadata']=current['sceneMetadata']
    document['notes']='Named grouping review stage. Geometry refinement, texture completion and state-only sprite models are separate work.'
    output.write_text(json.dumps(document,indent=2)+'\n')
    (OUT/'stage/map-assets/scenes/york.rhlos-map.json').write_text(output.read_text())
    report.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  map_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  publication_status='staged for grouping review; not installed in the live library')
    (OUT/'stage/export-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
