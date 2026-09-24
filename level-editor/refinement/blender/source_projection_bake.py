"""Bake camera-owned source pixels, with explicitly unknown shaded surfaces.

Run once per reveal layer, passing that layer's source image and occluder nodes.
Geometry and existing UV layers are retained. No save or publication is implicit.
"""
import sys as _refinement_sys
from pathlib import Path as _RefinementPath
_refinement_legacy = str(_RefinementPath(__file__).resolve().parents[2] / 'blender')
if _refinement_legacy not in _refinement_sys.path:
    _refinement_sys.path.append(_refinement_legacy)

import hashlib
import json
import math
from pathlib import Path


def bind_uv_layer(mesh, node, requested_name):
    """Bind the shader to a stable Blender-sized layer name, including Unicode."""
    encoded = requested_name.encode('utf-8')
    name = requested_name
    if len(encoded) > 63:
        prefix = encoded[:48].decode('utf-8', errors='ignore')
        name = prefix + '-' + hashlib.sha256(encoded).hexdigest()[:14]
    layer = mesh.uv_layers.get(name) or mesh.uv_layers.new(name=name)
    node.uv_map = layer.name
    if mesh.uv_layers.get(node.uv_map) != layer:
        raise RuntimeError('Generated material UV map does not resolve to its atlas layer')
    return layer


def bake(map_name, source_path, report_path, receiver_nodes=None,
         occluder_nodes=None, projection_label="source", texels_per_unit=1,
         elevation_deg=35.0, preserve_authored=True, source_mask_manifest=None,
         hidden_fill="neutral", synthesis_cache=None, reproject_authored_nodes=None,
         hidden_sampler=None, projection_region=None, exclude_occluder_components=None,
         receiver_components=None, receiver_asset_id=None, receiver_object_names=None,
         receiver_face_indices=None, material_suffix=None, hidden_sampler_receives_face=False,
         collection_name=None, provenance_directory=None):
    import bpy
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    if texels_per_unit <= 0:
        raise ValueError("Texture density must be positive")
    if receiver_face_indices is not None and not material_suffix:
        raise ValueError('Face-scoped baking requires a separate material and UV suffix')
    if hidden_fill not in ("neutral", "synthesized"):
        raise ValueError("hidden_fill must be neutral or synthesized")
    if hidden_sampler is not None and hidden_fill != "neutral":
        raise ValueError("An external hidden sampler cannot be combined with synthesis")
    from source_texture_fill import donor_patch, fill_island, choose_donor, synthesize_tiles, prune_donors
    donors_by_asset = {}
    pending_fill = []
    collection = bpy.data.collections[collection_name or map_name + " Working"]
    objects = [o for o in collection.all_objects
               if o.type == "MESH" and not o.hide_render]
    present = {o.get("source_node") for o in objects}
    for requested in (receiver_nodes, occluder_nodes):
        if requested is not None and set(requested) - present:
            raise ValueError("Unknown projection nodes: " + str(set(requested) - present))
    receivers = [o for o in objects if receiver_nodes is None or o.get("source_node") in receiver_nodes]
    from reveal_components import filter_receivers
    receivers=filter_receivers(receivers,receiver_components,
        available_objects=collection.all_objects)
    if receiver_asset_id is not None:
        receivers = [obj for obj in receivers if obj.get("asset_group") == receiver_asset_id]
    if receiver_object_names is not None:
        names = set(receiver_object_names)
        if names - {obj.name for obj in receivers}:
            raise ValueError('Explicit texture receivers are absent from projection layer')
        receivers = [obj for obj in receivers if obj.name in names]
    reproject_authored_nodes = set(reproject_authored_nodes or ())
    if reproject_authored_nodes - {o.get("source_node") for o in receivers}:
        raise ValueError("Authored texture reset must name receiver nodes")
    occluders = [o for o in objects if occluder_nodes is None or o.get("source_node") in occluder_nodes]
    from reveal_components import filter_occluders
    occluders = filter_occluders(occluders, exclude_occluder_components,
        projection_label=projection_label,
        available_objects=collection.all_objects)
    if not receivers or not occluders:
        raise ValueError("Projection requires receivers and occluders")
    if any(m.show_render or m.show_viewport for o in set(receivers + occluders) for m in o.modifiers):
        raise ValueError("Apply geometry modifiers before ownership projection")
    bpy.context.view_layer.update()
    vertices, triangles, triangle_owners = [], [], []
    from physical_opacity import OpacityRegistry
    opacity = OpacityRegistry()
    for obj in occluders:
        obj.data.calc_loop_triangles()
        offset = len(vertices)
        vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        for triangle in obj.data.loop_triangles:
            opacity.add(obj, obj.data, triangle)
            triangles.append(tuple(offset + i for i in triangle.vertices))
            triangle_owners.append(obj)
    tree = opacity.wrap(BVHTree.FromPolygons(vertices, triangles, all_triangles=True))
    if tree is None:
        raise ValueError("No occluder triangles")
    angle = math.radians(elevation_deg)
    toward = Vector((0, -math.cos(angle), math.sin(angle)))
    camera_depth = max(v.dot(toward) for v in vertices) + 10
    source_path = Path(source_path).resolve()
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source = bpy.data.images.load(str(source_path), check_existing=False)
    sw, sh = source.size
    pixels = np.empty(sw * sh * 4, dtype=np.float32)
    source.pixels.foreach_get(pixels)
    pixels = pixels.reshape(sh, sw, 4)
    bpy.data.images.remove(source)
    constraints = None
    if source_mask_manifest is not None:
        from occlusion_constraints import SourceMaskConstraints
        constraints = SourceMaskConstraints(source_mask_manifest, projection_label, source_hash, (sw, sh))
    ray_count = 0
    region = None
    if projection_region:
        from projection_regions import ProjectionRegion
        region = ProjectionRegion(projection_region, source_hash, (sw,sh), objects, source_mask_manifest,
            available_objects=collection.all_objects)
        camera_depth = max((o.matrix_world @ v.co).dot(toward) for o in objects for v in o.data.vertices) + 10

    def visible_at(position, receiver, source_pixel, fallback=False):
        nonlocal ray_count
        ray_count += 1
        point = Vector(position)
        origin = point + toward * (camera_depth - point.dot(toward))
        from source_visibility import first_source_hit
        hit, normal, index, distance = first_source_hit(
            region.tree if fallback else tree, region.owners if fallback else triangle_owners,
            origin, -toward, constraints=region.constraints if fallback else constraints,
            receiver=receiver, source_pixel=source_pixel)
        # Compare depth at the continuous projected sample, not polygon identity
        # at a rounded pixel center: finely subdivided coplanar faces share pixels.
        return hit is not None and (hit - point).length <= .01

    storage_label = projection_label + (' / ' + material_suffix if material_suffix else '')
    uv_name = "Owned source / " + storage_label
    report = {"source": str(source_path), "source_sha256": source_hash,
              "projection_label": projection_label, "receiver_nodes": receiver_nodes,
              "occluder_nodes": occluder_nodes, "objects": [], "geometry_changed": False,
              "ownership": "First hit depth at continuous projected texel center; tolerance 0.01 world units",
              "unknown": hidden_fill,
              "synthesis_method": "Example-based synthesis of fully observed donor patches, same asset and projection layer" if hidden_fill == "synthesized" else None,
              "source_mask_manifest": str(Path(source_mask_manifest).resolve()) if source_mask_manifest else None,
              "source_mask_state": constraints.state if constraints else None,
              "source_mask_evidence": __import__("occlusion_constraints").evidence_record(source_mask_manifest) if source_mask_manifest else None,
              "projection_region": projection_region,
              "exclude_occluder_components": exclude_occluder_components or [],
              "receiver_components": receiver_components or [],
              "reproject_authored_nodes": sorted(reproject_authored_nodes),
              "limitations": ["Geometry outside the artwork silhouette must still be corrected geometrically.",
                              "Reveal layers require explicit retained occluders matching their source artwork.",
                              "Ground cleanup and explicit projection_preserve materials are retained."]}
    if receiver_asset_id is not None:
        report["receiver_asset_id"] = receiver_asset_id
        report["projected_object_selectors"] = [
            {"object": obj.name, "source_node": obj.get("source_node"),
             "asset_group": obj.get("asset_group"),
             "projection_component": obj.get("projection_component")} for obj in receivers]
    light = Vector((-.35, -.45, .82)).normalized()
    for object_index, obj in enumerate(receivers):
        if object_index % 25 == 0:
            print(f"Ownership {projection_label}: object {object_index+1}/{len(receivers)}", flush=True)
        if obj.get("source_node") == "ground" or obj.get("source_obstacle") == "ground":
            continue
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        mesh = obj.data
        if receiver_face_indices is not None:
            selected_faces = receiver_face_indices.get(obj.name)
            if not selected_faces or any(type(i) is not int or i < 0 or i >= len(mesh.polygons)
                                         for i in selected_faces):
                raise ValueError('Face scope must identify existing receiver polygons: ' + obj.name)
        mesh.calc_loop_triangles()
        world = [obj.matrix_world @ v.co for v in mesh.vertices]
        by_face = {}
        for triangle in mesh.loop_triangles:
            by_face.setdefault(triangle.polygon_index, []).append(triangle)
        islands = []
        preserved = 0
        physical_opacity_preserved = 0
        degenerate = 0
        for face in mesh.polygons:
            if receiver_face_indices is not None and face.index not in receiver_face_indices.get(obj.name, []):
                preserved += 1
                continue
            mat = mesh.materials[face.material_index] if mesh.materials else None
            if mat and mat.get('foliage_physical_opacity'):
                contract = {'opacity_semantics': 'physical-coverage',
                            'source_ownership_semantics': 'separate-mask',
                            'source_ownership_channel': 'vertex-color-r'}
                if any(mat.get(key) != value for key, value in contract.items()):
                    raise ValueError('Physical foliage opacity requires separate ownership metadata: ' + mat.name)
                # Source-only rebaking cannot reconstruct authored leaf coverage;
                # alpha here is physical opacity, never an ownership channel.
                preserved += 1
                physical_opacity_preserved += 1
                continue
            if (preserve_authored and obj.get("source_node") not in reproject_authored_nodes
                    and mat and mat.get("projection_preserve")
                    and (not mat.get("source_ownership_bake") or mat.get("generated_source_sha256"))):
                preserved += 1
                continue
            points = [world[i] for i in face.vertices]
            normal = (obj.matrix_world.to_3x3().inverted().transposed() @ face.normal).normalized()
            origin = points[0]
            axis = max((p - origin for p in points), key=lambda v: v.length).normalized()
            vertical = normal.cross(axis).normalized()
            coords = [Vector(((p-origin).dot(axis), (p-origin).dot(vertical))) for p in points]
            low = Vector((min(p.x for p in coords), min(p.y for p in coords)))
            size = Vector((max(p.x for p in coords), max(p.y for p in coords))) - low
            if min(size) < 1e-7:
                degenerate += 1
                continue
            w, h = [min(1024, max(2, math.ceil(v * texels_per_unit))) for v in size]
            islands.append((face.index, origin, axis, vertical, normal, low, size, w, h))
        if not islands:
            report["objects"].append({"object": obj.name, "authored_faces_preserved": preserved,
                                      "physical_opacity_faces_preserved": physical_opacity_preserved,
                                      "degenerate_faces_unchanged": degenerate})
            continue
        area = sum((island[7]+4)*(island[8]+4) for island in islands)
        desired = max(64, max(island[7]+4 for island in islands), math.sqrt(area))
        width = min(2048, 2**math.ceil(math.log2(desired)))
        x = y = 2
        row = 0
        packed = []
        for island in islands:
            w, h = island[7:9]
            if x + w + 2 > width:
                x = 2
                y += row + 4
                row = 0
            packed.append((*island, x, y))
            x += w + 4
            row = max(row, h)
        islands = packed
        height = y + row + 2
        if height > 16384:
            raise ValueError(f"Ownership atlas for {obj.name} exceeds 16384 pixels; lower texels_per_unit or split the mesh")
        atlas = np.zeros((height, width, 4), dtype=np.float32)
        provenance = np.zeros((height, width), dtype=np.uint8) if provenance_directory else None
        atlas[:, :, 3] = 0 if hidden_fill == "synthesized" else 1
        known = unknown = mask_rejected = fallback_known = 0
        masks = constraints.for_object(obj) if constraints else None
        for fid, origin, axis, vertical, normal, low, size, w, h, left, bottom in islands:
            yy, xx = np.mgrid[-2:h+2, -2:w+2]
            qx = low.x + (xx.ravel()+.5)*size.x/w
            qy = low.y + (yy.ravel()+.5)*size.y/h
            positions = np.zeros((len(qx), 3))
            best = np.full(len(qx), -np.inf)
            sample_triangles = np.full(len(qx), -1, dtype=int)
            triangle_normals = {}
            for triangle in by_face[fid]:
                ps = [world[i] for i in triangle.vertices]
                triangle_normal = (ps[1]-ps[0]).cross(ps[2]-ps[0]).normalized()
                # Keep planar faces byte-stable. A warped polygon can contain
                # front- and back-facing triangles despite one averaged normal.
                triangle_normals[triangle.index] = (normal if triangle_normal.dot(normal) > 1-1e-5
                                                    else triangle_normal)
                a, b, c = [Vector(((p-origin).dot(axis), (p-origin).dot(vertical))) for p in ps]
                det = (b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y)
                if abs(det) < 1e-12:
                    continue
                wa = ((b.y-c.y)*(qx-c.x)+(c.x-b.x)*(qy-c.y))/det
                wb = ((c.y-a.y)*(qx-c.x)+(a.x-c.x)*(qy-c.y))/det
                weights = np.stack((wa, wb, 1-wa-wb), axis=1)
                margin = weights.min(axis=1)
                take = margin > best
                selected = weights[take].copy()
                # Atlas gutters extend beyond the polygon, not beyond its real
                # surface. Extrapolated 3D positions fail depth ownership on
                # curved adjacent facets and produce gray seams under filtering.
                # Clamp only outside samples onto the triangle boundary;
                # interior source samples retain their exact positions.
                outside = margin[take] < 0
                selected[outside] = np.maximum(selected[outside], 0)
                selected[outside] /= selected[outside].sum(axis=1, keepdims=True)
                positions[take] = selected @ np.asarray(ps)
                sample_triangles[take] = triangle.index
                best[take] = margin[take]
            colors = np.ones((len(qx), 4), dtype=np.float32)
            normal_groups = [(triangle_normals[index], sample_triangles == index)
                             for index in np.unique(sample_triangles) if index >= 0]
            colors[:, :3] = .16 + .16*max(0, normal.dot(light))
            for sample_normal, selected in normal_groups:
                colors[selected, :3] = .16 + .16*max(0, sample_normal.dot(light))
            sx = np.floor(positions[:, 0]).astype(int)
            sy = np.floor(sh + positions[:, 1]*math.sin(angle) + positions[:, 2]*math.cos(angle)).astype(int)
            # Match the source-review visibility floor. Near-grazing surfaces
            # magnify a source pixel into long bands across otherwise unknown roofs.
            front = np.zeros(len(qx), dtype=bool)
            for sample_normal, selected in normal_groups:
                if sample_normal.dot(toward) > max(.05, float(obj.get("projection_min_cosine", .05))):
                    front[selected] = True
            accepted = np.zeros(len(qx), dtype=bool)
            in_source = (sx >= 0) & (sx < sw) & (sy >= 0) & (sy < sh)
            mask_allowed = constraints.allowed(masks, sx, sy) if masks is not None else np.ones(len(sx), dtype=bool)
            primary = region.membership(sx,sy,sh) if region else np.ones(len(sx),dtype=bool)
            if region:
                fallback_masks = region.constraints.for_object(obj) if region.constraints else None
                fallback_allowed = region.constraints.allowed(fallback_masks,sx,sy) if region.constraints else np.ones(len(sx),dtype=bool)
                mask_allowed = np.where(primary,mask_allowed,fallback_allowed)
            mask_rejected += int(np.count_nonzero(front & in_source & ~mask_allowed & (best >= 0)))
            for i in np.flatnonzero(front & in_source & mask_allowed):
                accepted[i] = visible_at(positions[i], obj, (int(sx[i]), int(sh-1-sy[i])), bool(region and not primary[i]))
            colors[accepted] = pixels[sy[accepted], sx[accepted]]
            if region:
                fallback_samples=accepted & ~primary
                colors[fallback_samples]=region.pixels[sy[fallback_samples],sx[fallback_samples]]
                fallback_known += int(np.count_nonzero(fallback_samples & (best>=0)))
            if hidden_sampler is not None:
                protected_colors = colors[accepted].copy()
                generated_samples = np.zeros(len(accepted), dtype=bool)
                for sample_normal, selected in normal_groups:
                    sampled_colors = colors[selected].copy()
                    if hidden_sampler_receives_face:
                        filled = hidden_sampler(obj, sample_normal, positions[selected], accepted[selected], sampled_colors, face_index=fid)
                    else:
                        filled = hidden_sampler(obj, sample_normal, positions[selected], accepted[selected], sampled_colors)
                    if provenance is not None:
                        filled = np.asarray(filled)
                        if filled.dtype != bool or filled.shape != (int(selected.sum()),) or np.any(filled & accepted[selected]):
                            raise ValueError('Provenance requires an explicit unknown-only sampler fill mask')
                        generated_samples[selected] = filled
                    colors[selected] = sampled_colors
                if not np.array_equal(colors[accepted], protected_colors):
                    raise ValueError("Hidden sampler modified protected source pixels")
            if hidden_fill == "synthesized":
                colors[:, 3] = accepted.astype(np.float32)
            inside = best >= 0
            known += int(np.count_nonzero(accepted & inside))
            unknown += int(np.count_nonzero(~accepted & inside))
            atlas[bottom-2:bottom+h+2, left-2:left+w+2] = colors.reshape(h+4, w+4, 4)
            if provenance is not None:
                flags = accepted.astype(np.uint8)
                if hidden_sampler is not None:
                    flags[generated_samples] = 2
                provenance[bottom-2:bottom+h+2, left-2:left+w+2] = flags.reshape(h+4, w+4)
            if hidden_fill == "synthesized":
                tile = colors.reshape(h+4, w+4, 4)
                donor = donor_patch(tile, (accepted & inside).reshape(h+4, w+4))
                if donor is not None:
                    asset = obj.get("asset_group") or obj.name
                    donors_by_asset.setdefault(asset, []).append((donor, abs(normal.z), obj.name))
        name = obj.name + " / owned " + storage_label
        existing = next(((i, m) for i, m in enumerate(mesh.materials)
                         if m and m.get("source_ownership_label") == storage_label), None)
        # Split meshes can inherit one atlas material. Each receiver has its own
        # island layout, so detach shared material and image data before writing.
        if existing and existing[1].users > 1:
            material = existing[1].copy()
            material.name = name
            mesh.materials[existing[0]] = material
            existing = (existing[0], material)
        old_image = next((n.image for n in existing[1].node_tree.nodes
                          if n.type == "TEX_IMAGE" and n.image), None) if existing else None
        if old_image and old_image.users > 1:
            old_image = old_image.copy()
            old_image.name = name
        image = old_image or bpy.data.images.new(name, width=width, height=height, alpha=True)
        image.alpha_mode = "CHANNEL_PACKED" if hidden_fill == "synthesized" else "STRAIGHT"
        if tuple(image.size) != (width, height):
            image.scale(width, height)
        image.pixels.foreach_set(atlas.ravel())
        image.update()
        image.pack()
        mat = existing[1] if existing else bpy.data.materials.new(name)
        # Reaching this point explicitly replaces the atlas. A subsequent
        # generated fill can attach fresh approval metadata after baking.
        for key in ("generated_source_sha256", "generated_camera_manifest", "generated_approved_input_sha256"):
            if key in mat:
                del mat[key]
        mat.use_nodes = True
        mat["source_ownership_bake"] = True
        mat["source_ownership_label"] = storage_label
        mat["source_ownership_fill"] = hidden_fill
        mat["source_ownership_alpha"] = "one=observed,zero=inferred;material remains opaque"
        mat["projection_preserve"] = True
        mat["reprojection_source_sha256"] = source_hash
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nodes.clear()
        uv = nodes.new("ShaderNodeUVMap")
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = image
        texture.interpolation = "Linear"
        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(uv.outputs["UV"], texture.inputs["Vector"])
        # A direct color surface is Blender's implicit emission and exports as
        # KHR_materials_unlit, with RGBA in baseColorTexture and opaque coverage.
        links.new(texture.outputs["Color"], output.inputs["Surface"])
        slot = existing[0] if existing else len(mesh.materials)
        if not existing:
            mesh.materials.append(mat)
        layer = bind_uv_layer(mesh, uv, uv_name)
        fallback = mesh.attributes.get("reprojection_fallback_material")
        for fid, origin, axis, vertical, normal, low, size, w, h, left, bottom in islands:
            face = mesh.polygons[fid]
            face.material_index = slot
            if fallback:
                fallback.data[fid].value = slot
            for lid in face.loop_indices:
                p = world[mesh.loops[lid].vertex_index] - origin
                q = Vector((p.dot(axis), p.dot(vertical))) - low
                layer.data[lid].uv = ((left+q.x/size.x*w)/width, (bottom+q.y/size.y*h)/height)
        report["objects"].append({"object": obj.name, "faces": len(islands),
                                  "known_texels": known, "unknown_texels": unknown,
                                  "exterior_fallback_known_texels": fallback_known,
                                  "mask_rejected_texels": mask_rejected, "source_mask_constrained": masks is not None,
                                  "atlas_size": [width, height], "authored_faces_preserved": preserved,
                                  "physical_opacity_faces_preserved": physical_opacity_preserved})
        obj['reprojection_ownership_label'] = projection_label
        obj['reprojection_ownership_source_sha256'] = source_hash
        obj['reprojection_known_texels'] = known
        obj['reprojection_unknown_texels'] = unknown
        report["objects"][-1]["degenerate_faces_unchanged"] = degenerate
        if provenance is not None:
            directory = Path(provenance_directory)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (hashlib.sha256(obj.name.encode()).hexdigest()[:20] + '.npz')
            np.savez_compressed(path, ownership=provenance)
            report['objects'][-1]['texel_provenance'] = {
                'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'semantics': {'0': 'unfilled-or-padding', '1': 'protected-source', '2': 'generated'},
                'rgba8_sha256': hashlib.sha256(np.rint(np.clip(atlas,0,1)*255).astype(np.uint8).tobytes()).hexdigest(),
                'uv_sha256': hashlib.sha256(json.dumps([list(entry.uv) for entry in layer.data]).encode()).hexdigest()}
        if hidden_fill == "synthesized":
            pending_fill.append((obj, image, islands, report["objects"][-1]))
    tiles = {}
    if pending_fill:
        print(f"Ownership {projection_label}: synthesizing hidden fill for {len(pending_fill)} meshes", flush=True)
        donors_by_asset = {key: prune_donors(value) for key, value in donors_by_asset.items()}
        selected = []
        for obj, image, islands, entry in pending_fill:
            donors = donors_by_asset.get(obj.get("asset_group") or obj.name, [])
            selected.extend(choose_donor(donors, abs(island[4].z), obj.name) for island in islands)
        tiles, report["synthesis"] = synthesize_tiles(selected, synthesis_cache or Path(report_path).parent / "synthesis-cache")
    for obj, image, islands, entry in pending_fill:
        width, height = image.size
        atlas = np.empty(width*height*4, dtype=np.float32)
        image.pixels.foreach_get(atlas)
        atlas = atlas.reshape(height, width, 4)
        donors = donors_by_asset.get(obj.get("asset_group") or obj.name, [])
        filled = 0
        for fid, origin, axis, vertical, normal, low, size, w, h, left, bottom in islands:
            tile = atlas[bottom-2:bottom+h+2, left-2:left+w+2]
            filled += fill_island(tile, donors, abs(normal.z), obj.name,
                                  (int(origin.dot(axis)*texels_per_unit), int(origin.dot(vertical)*texels_per_unit)), tiles)
        image.pixels.foreach_set(atlas.ravel())
        image.update()
        image.pack()
        entry["synthesized_texels_including_padding"] = filled
        entry["donor_patches"] = len(donors)
        entry["missing_donor"] = not donors
    report["visibility_rays"] = ray_count
    report["known_texels"] = sum(o.get("known_texels", 0) for o in report["objects"])
    report["unknown_texels"] = sum(o.get("unknown_texels", 0) for o in report["objects"])
    report["mask_rejected_texels"] = sum(o.get("mask_rejected_texels", 0) for o in report["objects"])
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2)+"\n")
    return report
