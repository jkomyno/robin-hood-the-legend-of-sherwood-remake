"""Explicit physical surface identity across covered/revealed source reprojections."""


def validate(policy, *, asset_id, geometry_revision, model_hashes, states,
             originals, identities, material_records):
    if (policy.get('version') != 1
            or policy.get('kind') != 'covered-revealed-source-reprojection'
            or policy.get('asset_id') != asset_id
            or policy.get('geometry_revision') != geometry_revision
            or policy.get('approved_model_sha256') != model_hashes
            or states != ['covered', 'revealed']):
        raise ValueError('Shared surface policy identity/state binding differs')
    names = policy.get('objects')
    if (not isinstance(names, list) or not names
            or any(not isinstance(name, str) or not name for name in names)
            or len(names) != len(set(names))):
        raise ValueError('Shared surface policy requires unique named objects')
    records = {row['object']: row for row in material_records}
    if len(records) != len(material_records):
        raise ValueError('Ambiguous source material state record')
    for name in names:
        if name not in originals[0] or name not in originals[1]:
            raise ValueError('Policy names a surface absent from one reviewed state')
        if originals[0][name][0] != originals[1][name][0]:
            raise ValueError('Shared surface geometry/transform differs')
        identity = identities[0][name]
        if identity != identities[1][name] or identity['asset_group'] != asset_id:
            raise ValueError('Shared surface source identity differs')
        record = records.get(name)
        if (not record or record.get('source_node') != identity['source_node']
                or record.get('projection_component') != identity['projection_component']
                or not record.get('covered_face_materials')
                or not record.get('revealed_face_materials')):
            raise ValueError('Shared surface lacks both recorded source material states')
    return set(names)
