"""Rebake the paired west tower from cached sheets with coherent color sampling.

Run with -- COVERED_EXPERIMENT REVEALED_EXPERIMENT [covered|revealed|both].
Each endpoint starts from the same frozen source, never from the other endpoint
bake: shared geometry can have different generated surface colors in each state.
Existing evidence is immutable.
"""
import sys, json
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from architecture_texture_packets import original_layers, digest
from tower_texture_scope import capture, verify
from bake_reviewed_asset import stage
from project_reviewed_texture import _read, _reconcile


def run(covered, revealed, state="both"):
    if state not in ("covered", "revealed", "both"):
        raise ValueError("Unknown review state: " + state)
    c,e=map(lambda p:Path(p).resolve(),(covered,revealed))
    source=e/'bake-openrouter-gray-v4/worker.blend'
    diagnostics=[]
    for index,experiment in enumerate((c,e)):
        if state not in ('both', ('covered','revealed')[index]):continue
        bpy.ops.wm.open_mainfile(filepath=str(source))
        m=json.loads((experiment/'views-scoped.json').read_text())
        generation=experiment/('generation-short-no-mask-with-lighting' if index==0 else 'generation-short-no-mask-with-lighting-openrouter')
        generated=_read(generation/'generated-preserved.png')
        corrected=_reconcile(generated,m,_read(generation/'generated-raw.png'))
        editable=_read(experiment/'mask.png')[:,:,3]<.5
        changes=np.abs(corrected[:,:,:3]-generated[:,:,:3]).mean(axis=2)
        diagnostics.append({'experiment':str(experiment),'editable_pixels':int(editable.sum()),
            'raw_reconciliation_mean_absolute_rgb_change':float(changes[editable].mean()),
            'raw_reconciliation_pixels_changed_over_0_05':int((editable & (changes>.05)).sum()),
            'direct_preserved_reconciliation_max_change':float(np.abs(_reconcile(generated,m)-generated).max())})
        displayed=m.get('render_object_names') or m['object_names']
        scope={name:list(range(len(bpy.data.objects[name].data.polygons))) for name in displayed}
        m.update(texture_receiver_face_indices=scope,texture_receiver_object_names=sorted(scope),
                 texture_projection_labels=[x['projection_label'] for x in m['projection_layers']])
        two=set()
        for f in ('views-openrouter-gray-v2.json','views-openrouter-gray-v3.json'):
            old=json.loads((e/f).read_text());two.update(old['texture_receiver_object_names'])
        m['texture_two_sided_object_names']=sorted(two & set(scope))
        scope=m['texture_receiver_face_indices']
        _,protected=capture(m,labels=['__no_selected_label__'])
        for name,faces in scope.items():
            for face in faces:del protected[name][str(face)]
        original=original_layers(m)
        m.update(texture_view_selection='best-facing-single',texture_material_suffix='west-state-direct-single-v2-'+str(index))
        manifest=experiment/'views-state-direct-single-v2.json'
        if manifest.exists():raise FileExistsError(manifest)
        manifest.write_text(json.dumps(m,indent=2)+'\n')
        output=experiment/'bake-state-direct-single-v2'
        stage(manifest,generation/'generated-preserved.png',output,texels_per_unit=2)
        proof=verify(m,protected)
        if original!=original_layers(m,original):raise ValueError('Original layers or packed images changed')
        proof.update(status='PASS',source_model=str(source),source_model_sha256=digest(source),
                     baked_model_sha256=digest(output/'worker.blend'),original_uv_and_packed_atlases_preserved=True,
                     selected_faces=scope)
        (output/'protected-materials.json').write_text(json.dumps(proof,indent=2)+'\n')
        (output/'sampling-diagnosis.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
        print('PASS guarded cached bake',index,flush=True)



def restore_audited_floor_faces(revealed):
    """Keep correct interior-side assignments exposed by the frozen-camera audit."""
    from verify_staged_handoffs import snapshot
    from east_tower_texture_retry import validate_covered_state
    e=Path(revealed).resolve(); old=e/'bake-openrouter-gray-v4/worker.blend'
    current=e/'bake-state-direct-single-v2/worker.blend';out=e/'bake-state-direct-single-v5'
    if out.exists():raise FileExistsError(out)
    m=json.loads((e/'views.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(old))
    scope={f'West Moat Tower / West Moat Tower component {i}':
           list(range(len(bpy.data.objects[f'West Moat Tower / West Moat Tower component {i}'].data.polygons)))
           for i in (248,253,255)}
    assignments={name:{i:bpy.data.objects[name].data.materials[bpy.data.objects[name].data.polygons[i].material_index].name for i in faces} for name,faces in scope.items()}
    bpy.ops.wm.open_mainfile(filepath=str(current))
    _,protected=capture(m,labels=['__no_selected_label__'])
    original=original_layers(m)
    for name,faces in assignments.items():
        obj=bpy.data.objects[name]
        for index,material in faces.items():
            slots=[slot.name if slot else None for slot in obj.data.materials]
            if material not in slots:raise ValueError('Original material absent: '+material)
            obj.data.polygons[index].material_index=slots.index(material)
            del protected[name][str(index)]
    preservation=verify(m,protected)
    if original!=original_layers(m,original):raise ValueError('UVs/images changed')
    out.mkdir();bpy.ops.wm.save_as_mainfile(filepath=str(out/'worker.blend'))
    validate_covered_state(out/'worker.blend',e/'views.json',out/'reopen')
    import shutil
    shutil.copytree(out/'reopen/actual',out/'actual')
    validation=json.loads((current.parent/'validation.json').read_text())
    validation.update(final_model_sha256=digest(out/'worker.blend'),
        audited_face_restore={'old':str(old),'old_sha256':digest(old),'assignments':assignments,
        'new_base':str(current),'new_base_sha256':digest(current),'preservation':preservation,
        'reopen_validation':str(out/'reopen/validation.json'),'reopen_validation_sha256':digest(out/'reopen/validation.json')})
    (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    (out/'protected-materials.json').write_text(json.dumps(preservation,indent=2)+'\n')
    shutil.copy2(current.parent/'report.json',out/'report.json')
    print('PASS audited face restoration',flush=True)

if __name__ == '__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if args[0]=='restore':
        restore_audited_floor_faces(args[1])
    else:
        run(*args)
        if len(args)<3 or args[2]!='covered':restore_audited_floor_faces(args[1])
