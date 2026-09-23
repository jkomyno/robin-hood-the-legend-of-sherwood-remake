"""Strict plans for importing independently reviewed drawbridge endpoints.

This adapter does not grant approval. The caller must first validate the current
paired asset revision with the ordinary private-staging approval gate.
"""
import json
import math
from pathlib import Path
from endpoint_review import load_endpoint_mapping, endpoint_evidence
from review_evidence import sha


def _names(value, label):
    if (not isinstance(value, list) or not value or
            any(not isinstance(x, str) or not x for x in value) or len(set(value)) != len(value)):
        raise ValueError('Expected unique nonempty '+label)
    return value


def validate_endpoint_plan(path, item, map_name, *, evidence_base=None):
    path=Path(path).resolve(strict=True);data=json.loads(path.read_text())
    groups=data.get('groups',[])
    records=load_endpoint_mapping(path,{g.get('asset_id') for g in groups})
    asset=item['id']
    if asset not in records:raise ValueError('Missing endpoint staging asset')
    group=next(g for g in groups if g['asset_id']==asset)
    endpoints,files,errors=endpoint_evidence(records[asset],asset,map_name)
    if errors:raise ValueError('Endpoint evidence is incomplete: '+'; '.join(errors))
    # Every current endpoint artifact must belong to the approved paired revision,
    # including the applied model, config and material audit. A ready label alone
    # never permits importing another worker.
    base=Path(evidence_base).resolve() if evidence_base is not None else Path.cwd()
    bound={(base/Path(e['path'])).resolve():e['sha256'] for e in item['revision']['evidence'].values()}
    for file in files.values():
        if bound.get(file.resolve()) != sha(file):
            raise ValueError('Endpoint evidence is not bound to approved revision: '+str(file))
    plan={'asset_id':asset,'mapping':str(path),'mapping_sha256':sha(path),'states':{}}
    all_names=[];all_nodes=[]
    for record,endpoint in zip(records[asset],endpoints):
        state=record['id'];spec=group['states'][state];workspace=record['workspace']
        if spec.get('model_sha256')!=endpoint['model_sha256']:
            raise ValueError('Endpoint mapping requires exact current model hash')
        names=_names(spec.get('active_component_names'),'active component names')
        nodes=_names(spec.get('source_nodes'),'source nodes')
        config=json.loads((workspace/'workspace.json').read_text())
        if config.get('collection_name')!=map_name+' Working':raise ValueError('Endpoint working collection differs from map')
        if set(nodes)-set(config['part_ids']):raise ValueError('Endpoint nodes escape worker ownership')
        audit=json.loads((workspace/'inspection/stored-materials/audit.json').read_text())
        audited={obj['object']:obj['source_node'] for obj in audit['objects']}
        if len(audited)!=len(audit['objects']) or set(names)!=set(audited):
            raise ValueError('Active names differ from independently audited endpoint objects')
        if set(nodes)!=set(audited.values()):raise ValueError('Endpoint source nodes differ from material audit')
        if spec.get('default_hidden') is not (state=='applied'):
            raise ValueError('Only the applied endpoint may be default-hidden')
        if set(names)&set(all_names) or set(nodes)&set(all_nodes):
            raise ValueError('Endpoint names and canonical nodes must be disjoint')
        all_names.extend(names);all_nodes.extend(nodes)
        plan['states'][state]={'worker':str(workspace),'model_sha256':endpoint['model_sha256'],
            'active_component_names':names,'source_nodes':nodes,'default_hidden':state=='applied',
            'collection_name':config['collection_name']}
    applied=plan['states']['applied']['active_component_names']
    if sorted(_names(group.get('include_hidden_objects'),'hidden whitelist'))!=sorted(applied):
        raise ValueError('Hidden whitelist must exactly match reviewed applied components')
    states={'active':'initial',**{s:plan['states'][s]['source_nodes'] for s in ('initial','applied')}}
    if group.get('descriptor_states')!=states:raise ValueError('Descriptor states differ from reviewed endpoints')
    pivot=group.get('standalone_pivot')
    if (not isinstance(pivot,list) or len(pivot)!=3 or any(isinstance(v,bool) or
            not isinstance(v,(float,int)) or not math.isfinite(v) for v in pivot)):
        raise ValueError('Endpoint pivot requires three finite coordinates')
    plan.update(standalone_pivot=pivot,include_hidden_objects=applied,descriptor_states=states)
    plan['protected_files']={str(p.resolve()):sha(p) for p in files.values()}
    plan['protected_files'][str(path)]=sha(path)
    return plan


def import_endpoint_objects(plan,map_name):
    """Import exact active objects into a fresh in-memory scene; save no worker."""
    import bpy
    for filename,digest in plan['protected_files'].items():
        if sha(Path(filename))!=digest:raise ValueError('Endpoint evidence changed before import: '+filename)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    working=bpy.data.collections.new(map_name+' Working');bpy.context.scene.collection.children.link(working)
    imported=[]
    for state in ('initial','applied'):
        spec=plan['states'][state];model=Path(spec['worker'])/'model.blend'
        if sha(model)!=spec['model_sha256']:raise ValueError('Endpoint model changed before import')
        names=_names(spec['active_component_names'],'active component names')
        with bpy.data.libraries.load(str(model),link=False) as (available,selected):
            if set(names)-set(available.objects):raise ValueError('Reviewed component missing from endpoint model')
            selected.objects=list(names)
        for obj in selected.objects:
            if (obj is None or obj.name not in names or obj.type!='MESH' or obj.hide_render or
                    obj.get('asset_group')!=plan['asset_id'] or obj.get('source_node') not in spec['source_nodes']):
                raise ValueError('Imported endpoint object is not the exact reviewed active component')
            working.objects.link(obj)
        # Appended parent transforms are not evaluated until their hierarchy is
        # linked. Evaluate it temporarily, then retain only the selected meshes.
        parents=set()
        for obj in selected.objects:
            parent=obj.parent
            while parent is not None:
                if parent.name not in working.objects:
                    working.objects.link(parent);parents.add(parent)
                parent=parent.parent
        bpy.context.view_layer.update()
        matrices={obj:obj.matrix_world.copy() for obj in selected.objects}
        for obj in selected.objects:
            obj.parent=None;obj.matrix_world=matrices[obj]
            obj.hide_render=spec['default_hidden'];obj.hide_set(False)
            imported.append(obj)
        for parent in parents:
            if parent not in imported:working.objects.unlink(parent)
        bpy.context.view_layer.update()
    points=[obj.matrix_world@v.co for obj in imported for v in obj.data.vertices]
    if not points:raise ValueError('Empty endpoint geometry')
    low=[min(p[i] for p in points) for i in range(3)];high=[max(p[i] for p in points) for i in range(3)]
    measured=[(a+b)/2 for a,b in zip(low,high)]
    if any(abs(a-b)>1e-4 for a,b in zip(measured,plan['standalone_pivot'])):
        raise ValueError('Endpoint pivot differs from reviewed union geometry bounds')
    return {'object_names':[o.name for o in imported],'minimum':low,'maximum':high,'pivot':measured}
