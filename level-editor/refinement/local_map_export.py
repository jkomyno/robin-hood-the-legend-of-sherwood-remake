"""Create one local catalog used by both map placements and library insertion."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unify_map_assets import stage
from hybrid_library import stage_hybrid


def export_local_map(gltf, output, document):
    from scene_manifest import _splitter
    output = Path(output)
    library = output.parent / 'map-assets'
    if library.exists(): raise FileExistsError(library)
    source_assets = output.parent / 'assets'
    selected = json.loads((source_assets/'index.json').read_text()) if source_assets.exists() else {'version':1,'assets':[]}
    with tempfile.TemporaryDirectory(prefix='local-map-export-', dir=output.parent) as temporary:
        root = Path(temporary); source = root/'input'
        report = _splitter.split_gltf(gltf, source)
        document['sceneAssets'] = report['sceneAssets']
        (source/'scenes').mkdir()
        (source/'scenes'/output.name).write_text(json.dumps(document))
        (source/'3d-assets').mkdir(exist_ok=True)
        (source/'3d-assets/index.json').write_text(json.dumps(selected))
        for entry in selected['assets']:
            folder = Path(entry['descriptor']).parent
            shutil.copytree(source_assets/folder, source/'3d-assets'/folder, copy_function=os.link)
        placement_file = source_assets.with_name(source_assets.name+'-placements.json')
        legacy_placements = json.loads(placement_file.read_text()) if placement_file.exists() else {}
        for entry in selected['assets']:
            path = source/'3d-assets'/entry['descriptor']
            descriptor = json.loads(path.read_text())
            if 'source_origin_scene' not in descriptor:
                if entry['id'] not in legacy_placements:
                    raise ValueError('Asset revision lacks export origin: '+entry['id'])
                descriptor['source_origin_scene'] = legacy_placements[entry['id']]
                # A legacy conversion must not modify the hardlinked source descriptor.
                path.unlink(); path.write_text(json.dumps(descriptor))
        destination = root/'converted'/'library'
        conversion = stage(source, destination)
        subprocess.run(['node',str(Path(__file__).resolve().parents[1]/'pipeline/src/place-canonical-assets.ts'),
                        str(destination.parent/'plan.json')], check=True)
        hybrid = root/'hybrid'/'library'
        packing = stage_hybrid(destination, hybrid)
        shutil.move(str(hybrid), library)
        result = json.loads((library/'scenes'/output.name).read_text())
        output.write_text(json.dumps(result,indent=2)+'\n')
        receipt = json.loads((root/'converted/plan.json').read_text())
        # Source paths in the receipt are temporary. Preserve verifiable content
        # signatures and the placement proof instead of dangling file references.
        (output.parent/'local-assets-verification.json').write_text(json.dumps({
            'status':'PASS', 'assets':conversion['assets'], 'scenes':receipt['proofs'], 'packing':packing,
            'placements':json.loads((root/'converted/placement-proof.json').read_text())},indent=2)+'\n')
    if selected['assets']:
        backup = output.parent/'backups'/'asset-export'
        backup.parent.mkdir(exist_ok=True)
        shutil.move(str(source_assets), backup)
        source_assets.mkdir()
        index = json.loads((library/'3d-assets/index.json').read_text())
        selected_ids = {entry['id'] for entry in selected['assets']}
        selected['assets'] = [entry for entry in index['assets'] if entry['id'] in selected_ids]
        for entry in selected['assets']:
            folder = Path(entry['descriptor']).parent
            shutil.copytree(library/'3d-assets'/folder, source_assets/folder, copy_function=os.link)
        (source_assets/'blobs').symlink_to(Path('../map-assets/3d-assets/blobs'),target_is_directory=True)
        (source_assets/'index.json').write_text(json.dumps(selected,indent=2)+'\n')
    return {'library':str(library), 'document':result,
            'report':{'verified_assets':conversion['assets']}}
