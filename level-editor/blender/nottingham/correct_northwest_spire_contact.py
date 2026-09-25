"""Build the isolated northwest spire/roof contact correction for renewed review."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT/'level-editor/work/nottingham-refinement'
sys.path[:0] = [str(ROOT/'level-editor/refinement/blender'), str(Path(__file__).parent)]
from correct_spire_metal_ridges import apply_ridges, sha


def main():
    import bpy
    import refinement_workspace as rw
    from render_slots import acquire
    from northwest_spire_source_authority import prepare_authority
    from spire_roof_contact import apply
    from refine_village_secondary import replace
    new = Path(sys.argv[sys.argv.index('--')+1]).resolve()
    asset = 'nottingham-castle-northwest-spire'
    traces = Path(__file__).with_name('spire_metal_ridge_traces.json')
    spec = json.loads(traces.read_text())['assets'][asset]
    old = WORK/spec['approved_workspace']
    if new == old.resolve():
        raise ValueError('The paired correction must not overwrite the approved workspace')
    assert sha(old/'model.blend') == spec['approved_model_sha256']
    evidence = WORK/'texture-generation/projection-corrections/spire-ridges-v2'/asset/'inspection'
    proposal_path = evidence/'foreign-shingle-polygon-proposal.json'
    proposal = json.loads(proposal_path.read_text())
    # Keep exact boundary-center samples with the tower. A subpixel inset avoids
    # Boolean/ray roundoff arbitrarily assigning coplanar edge samples to a side.
    original_trace_sha256 = sha(proposal_path)
    clipped = []
    polygon = proposal['polygon']
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if a[0] <= 304:
            clipped.append(a)
        if (a[0] <= 304) != (b[0] <= 304):
            fraction = (304-a[0]) / (b[0]-a[0])
            clipped.append([304, a[1] + fraction*(b[1]-a[1])])
    proposal['polygon'] = clipped
    proposal['extent_policy'] = 'Clip at source x304: all 407 transferred tower pixels are at x268..302; retain existing stateful roof/wall ownership to the right.'
    center = [sum(p[i] for p in proposal['polygon']) / len(proposal['polygon']) for i in range(2)]
    proposal['polygon'] = [[center[i] + (p[i]-center[i]) * .9999 for i in range(2)]
                           for p in proposal['polygon']]
    proposal['boundary_policy'] = 'A 0.01 percent centroid inset retains ambiguous exact-edge source centers on the tower.'
    proposal['original_trace_sha256'] = original_trace_sha256
    proposal_path = new.parent / 'contact-trace-inset.json'
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    if proposal_path.exists():
        assert json.loads(proposal_path.read_text()) == proposal
    else:
        proposal_path.write_text(json.dumps(proposal, indent=2) + '\n')
    plane_path = evidence/'covered-hall-tower-plane-comparison.json'
    plane = next(row for row in json.loads(plane_path.read_text()) if row['model']=='approved-hall' and row['object']=='building-505__castle-hall-retained-roof')
    authority = new.parent/'northwest-contact-source-authority'
    if not authority.exists():
        prepare_authority(old, proposal_path, authority)
    acquire(slots=2)
    config = json.loads((old/'workspace.json').read_text())
    if not new.exists():
        bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
        body = next(o for o in bpy.context.scene.objects if o.get('source_node')=='building-519')
        original_mesh = body.data.copy()
        extension, _ = apply(body, plane['vertices'], plane['faces'], proposal['polygon'])
        body.data = original_mesh
        extension.name = 'building-505__castle-hall-northwest-contact'
        extension['source_node'] = 'building-505'
        extension['asset_group'] = 'nottingham-castle-main-hall'
        extension['component'] = 'castle-hall-northwest-contact'
        extension['projection_label'] = 'exterior'
        replace(extension, [extension.matrix_world @ v.co for v in extension.data.vertices],
                [tuple(p.vertices) for p in extension.data.polygons], 'Planar hall roof contact')
        collection = bpy.data.collections[config['collection_name']]
        if extension.name not in collection.objects:
            collection.objects.link(extension)
        rw.prepare(new, asset_id=asset, scene_name=config['scene_name'], collection_name=config['collection_name'],
                   source_path=old/'reference/source.png', grouping_manifest=old/'reference/grouping.json',
                   inventory_path=old/'reference/inventory.json', review_path=old/'reference/grouping-review.json',
                   source_mask_manifest=authority/'assignments.json', width=320,height=384,context_padding=25,framing_padding=1.12,
                   lighting=json.loads((WORK/'lighting-calibration/map-lighting.json').read_text())['lighting'])
    bpy.ops.wm.open_mainfile(filepath=str(new/'baseline.blend'))
    report = apply_ridges(asset, spec)
    body = next(o for o in bpy.context.scene.objects if o.get('source_node')=='building-519')
    temporary, contact = apply(body, plane['vertices'], plane['faces'], proposal['polygon'])
    bpy.data.objects.remove(temporary, do_unlink=True)
    vertices = [body.matrix_world @ v.co for v in body.data.vertices]
    faces = [tuple(p.vertices) for p in body.data.polygons]
    replace(body, vertices, faces, 'Tower with concealed hall roof attachment recess')
    report['changed_objects'].append(body.name)
    report['unchanged_objects'] -= 1
    report.update(asset_id=asset, source_masks_changed=True, contact=contact,
                  original_model_sha256=spec['approved_model_sha256'], source_trace_sha256=sha(traces),
                  roof_plane_evidence_sha256=sha(plane_path), source_contact_trace_sha256=sha(proposal_path),
                  limitations=spec['limitations']+[contact['limitation']], approval_status='pending-new-user-review')
    (new/'source-trace.json').write_bytes(traces.read_bytes())
    (new/'contact-trace.json').write_bytes(proposal_path.read_bytes())
    (new/'roof-plane-evidence.json').write_bytes(plane_path.read_bytes())
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'))
    rw.modified(new)
    inspection=new/'inspection';inspection.mkdir(exist_ok=True)
    from restore_foreign_uv_schema import restore_foreign_uv_schema
    restore_foreign_uv_schema(new, apply=True)
    from audit_stored_materials import run
    run(new,inspection/'stored-materials',render=True,export=False)
    report.update(model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'))
    (new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
    (new/'candidate.json').write_text(json.dumps(dict(asset_id=asset,status='refinement-in-progress',approval_status='pending',model_sha256=report['model_sha256'],modified_views_sha256=report['modified_views_sha256'],limitations=report['limitations'],recipe=str(Path(__file__).resolve())),indent=2)+'\n')


if __name__=='__main__':main()
