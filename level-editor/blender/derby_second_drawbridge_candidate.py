"""Isolated source-grounded second drawbridge endpoint review; never publishes."""
import sys
import json
import math
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'level-editor/work/derby-refinement/drawbridge-state-final'
OUT = ROOT / 'level-editor/work/derby-refinement/round-2/assets/derby-second-drawbridge'
if '--output' in sys.argv:
    OUT = Path(sys.argv[sys.argv.index('--output')+1]).resolve()
ASSET = 'derby-second-drawbridge'

def prepare():
    from PIL import Image
    layers = json.loads((SOURCE / 'layers.json').read_text())
    patch = next(p for p in layers['mission_patches'] if p['mission'] == 'H03_Der_MK' and p['name'] == 'Derby - Pont_levis02')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'source-patch.json').write_text(json.dumps(patch, indent=2))
    for state in ('initial', 'applied'):
        directory = OUT / state
        directory.mkdir(exist_ok=True)
        graphic = patch[state + '_graphic']
        sprite = Image.open(SOURCE / graphic['image']).convert('RGBA')
        image = Image.open(SOURCE / 'covered.png').convert('RGBA')
        image.alpha_composite(sprite, tuple(graphic['bbox'][:2]))
        image.save(directory / 'source.png')
        sprite.getchannel('A').save(directory / 'mask.png')
        (directory / 'masks.json').write_text(json.dumps({'masks': [{'index': 0, 'box_top_left': graphic['bbox'][:2], 'box_size': graphic['bbox'][2:], 'png': 'mask.png'}]}, indent=2))
        (directory / 'ownership.json').write_text(json.dumps({'version': 1, 'mask_inventory': 'masks.json', 'projections': {'exterior': {'source_sha256': hashlib.sha256((directory/'source.png').read_bytes()).hexdigest(), 'state': state, 'assignments': [{'reviewed': True, 'asset_group': ASSET, 'mask_indices': [0]}]}}}, indent=2))

def build():
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    sys.path.insert(0, str(ROOT / 'level-editor/refinement/blender'))
    from refinement_review import render_review
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'Second drawbridge candidate'
    collection = bpy.data.collections.new('Second drawbridge candidate')
    scene.collection.children.link(collection)
    group = bpy.data.objects.new('Second courtyard drawbridge', None)
    collection.objects.link(group)
    group['asset_group'] = ASSET
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    # Measured hinge and raised-deck corners in full source pixels. Depth is
    # constrained by a horizontal hinge and one rigid rectangular leaf.
    hinge = Vector((1240, -1173/sine, 0))
    axis = Vector((34, 17/sine, 0))
    width = axis.length
    axis.normalize()
    away = Vector((axis.y, -axis.x, 0))
    length = 48/cosine
    basis = Matrix((axis, -away, Vector((0,0,1)))).transposed().to_4x4()
    basis.translation = hinge
    def mesh(name, vertices, faces):
        data = bpy.data.meshes.new(name)
        data.from_pydata(vertices, [], faces)
        bm = bmesh.new(); bm.from_mesh(data)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(data); bm.free()
        obj = bpy.data.objects.new(name, data); collection.objects.link(obj)
        obj.parent = group
        obj['asset_group'] = ASSET
        obj['source_node'] = 'mission-second-drawbridge'
        obj['mission_patch_profile'] = 'Derby - Pont_levis02'
        obj['part_name'] = name
        return obj
    verts, faces = [], []
    for n in range(7):
        lo, hi = width*n/7, width*(n+1)/7-.12
        off = len(verts)
        verts.extend((x,y,z) for z in (0,length) for y in (-1.4,1.4) for x in (lo,hi))
        faces.extend(tuple(off+i for i in f) for f in ((0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5),(0,2,3,1),(4,5,7,6)))
    deck = mesh('Hinged leaf / seven timber planks', verts, faces)
    deck['drawbridge_hinge_matrix'] = json.dumps([list(r) for r in basis])
    deck['drawbridge_pose_angles_degrees'] = [0,90]
    deck['drawbridge_export_mode'] = 'single_hinged_mesh'
    ropes = []
    def rope(name, points, radius=.7):
        vertices, polygons = [], []
        for i,p in enumerate(points):
            direction=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
            u=direction.cross(Vector((1,0,0))).normalized(); v=direction.cross(u).normalized()
            vertices.extend(p+radius*(math.cos(k*math.tau/8)*u+math.sin(k*math.tau/8)*v) for k in range(8))
        for i in range(len(points)-1):
            polygons.extend((i*8+k,i*8+(k+1)%8,(i+1)*8+(k+1)%8,(i+1)*8+k) for k in range(8))
        polygons.extend((tuple(reversed(range(8))),tuple((len(points)-1)*8+k for k in range(8))))
        ropes.append(mesh(name, vertices, polygons))
    validation = {'status': 'geometry candidate; approval required', 'source_anchors': {}, 'sun_elevation_degrees':48, 'camera_elevation_degrees':35, 'base_elevation':134.25, 'base_evidence':'context-ray-heights.json: adjacent upper wall walk and stair landing', 'limitations': ['Seven planks are an approximate count at small sprite resolution.', 'Far-side thickness and suspension depth are inferred.', 'Suspension ropes use continuous strands, not individual links.', 'No editor playback or live integration is included.', 'Endpoint silhouettes fit separately: hinge directions differ in artwork; rigid animation is NOT validated.', 'Small gray boundary strips reflect conservative sprite-alpha ownership and approximate thickness.'], 'states': {}}
    for state, angle in (('initial',0),('applied',math.pi/2)):
        for obj in ropes: bpy.data.objects.remove(obj, do_unlink=True)
        ropes.clear()
        # Endpoint sprites are not perfectly rigid-projection consistent. Fit
        # each observed leaf instead of claiming this is a validated animation.
        corners = ([[1240,1174],[1271,1158],[1244,1130],[1276,1115]] if state=='initial'
                   else [[1240,1176],[1260,1157],[1285,1201],[1311,1182]])
        def world(pixel,z):
            z+=134.25
            return Vector((pixel[0],(-pixel[1]-z*cosine)/sine,z))
        corner_world=[world(p,54 if state=='initial' and i>=2 else 0) for i,p in enumerate(corners)]
        deck.matrix_world=Matrix.Identity(4)
        for vertex in deck.data.vertices:
            u=verts[vertex.index][0]/width; v=verts[vertex.index][2]/length
            surface=corner_world[0].lerp(corner_world[1],u).lerp(corner_world[2].lerp(corner_world[3],u),v)
            normal=(corner_world[1]-corner_world[0]).cross(corner_world[2]-corner_world[0]).normalized()
            vertex.co=surface+normal*verts[vertex.index][1]
        bm=bmesh.new();bm.from_mesh(deck.data)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(deck.data);bm.free()
        deck['drawbridge_export_mode']='endpoint_geometry_candidate'
        deck['rigid_animation_validated']=False
        deck['drawbridge_pose'] = angle/(math.pi/2)
        deck['drawbridge_state'] = state
        def unproject(x,y,z): return world([x,y],z)
        junction = unproject(1246,1047,145) if state=='initial' else unproject(1248,1159,6)
        rope('Suspension / upper cord', [unproject(1239,1011,191) if state=='initial' else unproject(1232,1150,4), junction])
        for side in range(2):
            tip=corner_world[side+2]
            middle=(unproject(1235,1080,105) if side==0 else unproject(1270,1060,125)) if state=='initial' else unproject(1242 if side==0 else 1282,1176 if side==0 else 1164,7)
            rope('Suspension / branch '+str(side+1),[junction,middle,tip])
        state_dir=OUT/state
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(state_dir/'model.blend'))
        actual_edges=[]
        for obj in collection.objects:
            if obj.type!='MESH': continue
            for edge in obj.data.edges:
                points=[]
                for vi in edge.vertices:
                    p=obj.matrix_world @ obj.data.vertices[vi].co
                    points.append([p.x,-p.y*sine-p.z*cosine])
                actual_edges.append(points)
        (state_dir/'mesh-source-edges.json').write_text(json.dumps({'corners':corners,'edges':actual_edges},indent=2))
        record=render_review(state_dir/'input-v4', scene_name=scene.name,collection_name=collection.name,asset_id=ASSET,source_path=state_dir/'source.png',source_mask_manifest=state_dir/'ownership.json',width=384,height=384,context_padding=25)
        render_review(state_dir/'modified-v4',scene_name=scene.name,collection_name=collection.name,asset_id=ASSET,source_path=state_dir/'source.png',source_mask_manifest=state_dir/'ownership.json',frame_manifest=state_dir/'input-v4/views.json')
        validation['source_anchors'][state]=corners
        validation['states'][state]={'meshes':len([o for o in collection.objects if o.type=='MESH']), 'source_known_pixels':[v['counts']['source'] for v in record['views']], 'geometry_sha256':hashlib.sha256((state_dir/'model.blend').read_bytes()).hexdigest()}
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2))

def report():
    from PIL import Image, ImageDraw
    for state in ('initial','applied'):
        directory=OUT/state
        data=json.loads((directory/'mesh-source-edges.json').read_text())
        box=(1215,995,1330,1215) if state=='initial' else (1215,1135,1330,1220)
        source=Image.open(directory/'source.png').convert('RGB').crop(box).resize(((box[2]-box[0])*4,(box[3]-box[1])*4),Image.Resampling.NEAREST)
        original=source.copy(); draw=ImageDraw.Draw(source)
        def xy(p): return ((p[0]-box[0])*4,(p[1]-box[1])*4)
        for a,b in data['edges']: draw.line((xy(a),xy(b)), fill=(0,220,255),width=1)
        for i,p in enumerate(data['corners']):
            x,y=xy(p);draw.ellipse((x-4,y-4,x+4,y+4),fill='red');draw.text((x+5,y+5),str(i+1),fill='yellow')
        sheet=Image.new('RGB',(source.width*2,source.height));sheet.paste(original,(0,0));sheet.paste(source,(source.width,0));sheet.save(directory/'mesh-on-source.png')
    (OUT/'review.md').write_text('''# Second courtyard drawbridge — endpoint geometry candidate

Approval required. Not integrated; no generated textures. Source sprite alpha is the ownership authority for each state. Gray pixels remain unknown. Sun elevation is 48°, source camera elevation is 35°.

## Raised initial state

![Original artwork beside actual mesh edges and four numbered leaf corners](initial/mesh-on-source.png)
![Solid eight views](initial/modified-v4/solid.png)
![Source-only eight views](initial/modified-v4/textured.png)

## Lowered applied state

![Original artwork beside actual mesh edges and four numbered leaf corners](applied/mesh-on-source.png)
![Solid eight views](applied/modified-v4/solid.png)
![Source-only eight views](applied/modified-v4/textured.png)

The suspension falls onto the deck in the final sprite. The two endpoint silhouettes were fit independently because their hinge directions differ in the artwork. These are static endpoint candidates, not a validated rigid animation; only one endpoint should display at once. Thickness, seven-plank count, back surfaces and rope depth remain inferred. Native old/new masks are empty for this profile, so its sprite alpha is retained as a lossless mask. The prepared source image is the original covered map with the exact endpoint sprite composited at its native bounding box.

The first bridge and all published models were untouched. The mechanism initial graphic is a transparent 1×1 sprite; its final sprite is a small 23×34 fragment. A complete initial winch cannot be reconstructed from those frames alone, and no mechanism candidate is claimed here.
''')

if __name__ == '__main__':
    if '--prepare' in sys.argv: prepare()
    elif '--report' in sys.argv: report()
    else: build()
