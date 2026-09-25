"""Hash-bound, scoped physical surface verification for atlas triangulation."""
import json
from collections import Counter
from pathlib import Path
from review_evidence import sha


def receipt(handoff):
    root = Path(handoff['blend_path']).parent
    path = root/'triangle-partition-proof.json'
    if not path.exists():
        return None
    chain_path = root/'final-review-chain.json'
    proof = json.loads(path.read_text()); chain = json.loads(chain_path.read_text())
    if (proof.get('status') != 'PASS' or chain.get('status') != 'PASS' or
            chain.get('model_sha256') != handoff['blend_sha256'] or
            proof.get('approved_worker_sha256') != sha(Path(handoff['approved_source_blend'])) or
            not all(chain.get(k) is True for k in ['physical_surface_unchanged',
                'source_geometry_receiver_facing_unchanged', 'source_material_comparison_visually_inspected',
                'source_and_untouched_rgba_exact', 'all_eight_actual_views_owner_and_root_pass',
                'zero_visible_unfilled_all_eight'])):
        raise ValueError('Partition source/model/source-retention chain mismatch')
    bound = {}
    for name, digest in chain['review_chain'].items():
        p = Path(name).resolve()
        if sha(p) != digest: raise ValueError('Partition review chain changed: '+name)
        bound[str(p)] = digest
    if bound.get(str(path.resolve())) != sha(path):
        raise ValueError('Partition proof is not bound by final review chain')
    bound[str(chain_path.resolve())] = sha(chain_path)
    handoff['protected_files'].update(bound)
    return proof


def snapshot(obj, uv_names=None):
    mesh = obj.data
    if obj.modifiers or mesh.shape_keys or mesh.has_custom_normals:
        raise ValueError('Partition with modifiers/shape keys/custom normals needs separate proof')
    # This pipeline rebuilds the owned source atlas after partitioning; the
    # reviewed source-retention chain and exact final model bind that atlas.
    # Keep every original non-atlas map, including the native projection UVs.
    uv_names = list(uv_names) if uv_names is not None else [n for n in mesh.uv_layers.keys() if n != 'Owned source / exterior']
    if any(n not in mesh.uv_layers for n in uv_names): raise ValueError('Original UV layer missing')
    mesh.calc_loop_triangles()
    return dict(invariants=dict(vertices=[tuple(v.co) for v in mesh.vertices],
        matrix=[tuple(r) for r in obj.matrix_world], parent=obj.parent.name if obj.parent else None,
        hide_render=obj.hide_render, hide_viewport=obj.hide_viewport, source_node=obj.get('source_node'),
        asset_group=obj.get('asset_group'), uv_names=uv_names),
        edges=[tuple(sorted(e.vertices)) for e in mesh.edges],
        polygons=[dict(polygon=tuple(p.vertices), triangles=[dict(material=p.use_smooth,
            corners=[dict(position=tuple(mesh.vertices[v].co),uv={n:tuple(mesh.uv_layers[n].data[l].uv) for n in uv_names})
                     for v,l in zip(t.vertices,t.loops)]) for t in mesh.loop_triangles if t.polygon_index==p.index]) for p in mesh.polygons])


def verify(before, after, proof):
    import sys
    sys.path.insert(0, str(Path(__file__).parent/'blender'))
    from triangle_equivalence import verify_equivalence
    names = proof['scoped_oriented_triangles']
    if len(names) != 1 or set(before) != set(names) or set(after) != set(names):
        raise ValueError('Partition requires exact explicit single-object scope')
    name = next(iter(names)); old=before[name]; new=after[name]
    mapping = proof['original_polygon_by_new_polygon']
    if len(mapping) != len(new['polygons']) or set(mapping) != set(range(len(old['polygons']))):
        raise ValueError('Partition original face mapping mismatch')
    scopes = [i for i,n in Counter(mapping).items() if n>1]
    old_records={i:p for i,p in enumerate(old['polygons'])}
    new_records={i:dict(polygon=[],triangles=[]) for i in old_records}
    for p,i in zip(new['polygons'],mapping):
        new_records[i]['polygon'].append(p['polygon']);new_records[i]['triangles'].extend(p['triangles'])
    old_records={i:dict(polygon=[p['polygon']],triangles=p['triangles']) for i,p in old_records.items()}
    result=verify_equivalence({name:dict(invariants=old['invariants'],polygons=old_records)},
        {name:dict(invariants=new['invariants'],polygons=new_records)},{name:scopes})
    if result['scoped_oriented_triangles'] != names: raise ValueError('Partition scope triangle count changed')
    expected=set(old['edges'])
    for p,i in zip(new['polygons'],mapping):
        if i in scopes:
            vertices=p['polygon']
            expected.update(tuple(sorted((v,vertices[(j+1)%len(vertices)]))) for j,v in enumerate(vertices))
    if set(new['edges']) != expected: raise ValueError('Partition edge topology changed outside scoped triangles')
    return result
