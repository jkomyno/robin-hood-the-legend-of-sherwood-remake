"""Guards and world-space lighting for an injective, possibly nonplanar UV atlas."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _cross2(a,b):return a[0]*b[1]-a[1]*b[0]

def _area(poly):
    if len(poly)<3:return 0.
    p=np.asarray(poly);return abs(float(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1))))/2

def _intersection(a,b):
    poly=[np.array(v) for v in a]
    orientation=np.sign(_cross2(b[1]-b[0],b[2]-b[0]))
    for c,d in zip(b,np.roll(b,-1,axis=0)):
        out=[]
        for p,q in zip(poly,poly[1:]+poly[:1]):
            dp=orientation*_cross2(d-c,p-c);dq=orientation*_cross2(d-c,q-c)
            if dp>=-1e-12:out.append(p)
            if (dp>1e-12 and dq< -1e-12) or (dp< -1e-12 and dq>1e-12):out.append(p+(q-p)*dp/(dp-dq))
        poly=out
        if not poly:break
    return _area(poly)

def validate_evidence(evidence):
    if evidence.get('physical_opacity')!='OPAQUE' or evidence.get('direct_image_color') is not True:raise ValueError('Only opaque direct-image UV atlases are supported')
    geometry=evidence['geometry']
    digest=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=evidence['geometry_uv_matrix_sha256']:raise ValueError('Geometry/UV evidence digest changed')
    uv=np.asarray([t['uv_top_left'] for t in evidence['triangles']],float)
    world=np.asarray([t['world'] for t in evidence['triangles']],float)
    normals=np.asarray([t['normal'] for t in evidence['triangles']],float)
    if uv.shape!=(len(uv),3,2) or world.shape!=(len(uv),3,3) or not len(uv):raise ValueError('Expected actual triangular UV/world evidence')
    if not all(np.isfinite(a).all() for a in (uv,world,normals)):raise ValueError('Nonfinite atlas geometry')
    if np.any(uv< -1e-7) or np.any(uv>1+1e-7):raise ValueError('Atlas UV leaves unit square')
    for i,t in enumerate(uv):
        if _area(t)<1e-12:raise ValueError('Degenerate UV triangle')
        normal=np.cross(world[i,1]-world[i,0],world[i,2]-world[i,0]);length=np.linalg.norm(normal)
        if length<1e-10 or not np.allclose(normal/length,normals[i],atol=1e-6):raise ValueError('World triangle/normal evidence differs')
        for j in range(i):
            if _intersection(t,uv[j])>1e-10:raise ValueError('Overlapping UV triangles cannot receive a unique atlas')
    return uv,world,normals

def raster_lighting(evidence,settings,*,chunk_rows=64):
    """Rasterize exact UV pixel centers and cast sun rays against this asset only."""
    uv,world,normals=validate_evidence(evidence);width,height=evidence['atlas_dimensions']
    sun=np.asarray(settings['toward_sun'],float);length=np.linalg.norm(sun)
    if not np.isfinite(sun).all() or length<=0:raise ValueError('Invalid sun direction')
    sun/=length;ambient=float(settings['ambient']);diffuse=float(settings['diffuse']);epsilon=float(settings['shadow_epsilon'])
    if not np.isfinite([ambient,diffuse,epsilon]).all() or min(ambient,diffuse)<0 or epsilon<=0:raise ValueError('Invalid lighting coefficients')
    surface=np.zeros((height,width),bool);solid=np.zeros((height,width,4),np.uint8);shadow_count=0
    x=(np.arange(width)+.5)/width
    for i,t in enumerate(uv):
        a,b,c=t;det=_cross2(b-a,c-a)
        lo=max(0,int(np.floor(t[:,1].min()*height)));hi=min(height,int(np.ceil(t[:,1].max()*height)))
        for start in range(lo,hi,chunk_rows):
            stop=min(hi,start+chunk_rows);y=(np.arange(start,stop)+.5)/height;dx=x[None,:]-a[0];dy=y[:,None]-a[1]
            u=(dx*(c[1]-a[1])-dy*(c[0]-a[0]))/det;v=((b[0]-a[0])*dy-(b[1]-a[1])*dx)/det
            inside=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&~surface[start:stop]
            yy,xx=np.nonzero(inside)
            if not len(xx):continue
            bary=np.stack((1-u[inside]-v[inside],u[inside],v[inside]),axis=1)
            points=bary@world[i];origins=points+sun*epsilon;blocked=np.zeros(len(points),bool)
            for j,tri in enumerate(world):
                if j==i:continue
                edge1=tri[1]-tri[0];edge2=tri[2]-tri[0];p=np.cross(sun,edge2);den=edge1@p
                if abs(den)<1e-12:continue
                delta=origins-tri[0];bu=(delta@p)/den;q=np.cross(delta,edge1);bv=(q@sun)/den;distance=(q@edge2)/den
                blocked|=(bu>=-1e-8)&(bv>=-1e-8)&(bu+bv<=1+1e-8)&(distance>1e-8)
            intensity=ambient+np.where(blocked,0,diffuse*max(0,float(normals[i]@sun)))
            gray=np.clip(np.rint(intensity*255),0,255).astype(np.uint8)
            solid[start+yy,xx,:3]=gray[:,None];solid[start+yy,xx,3]=255;surface[start+yy,xx]=True;shadow_count+=int(blocked.sum())
    return surface,solid,dict(surface_pixels=int(surface.sum()),outside_pixels=int((~surface).sum()),self_shadow_pixels=shadow_count,lighting=settings,triangle_count=len(uv),method='Exact UV pixel centers, saved world normals and asset-only directional shadow rays')

def validate_uv_atlas_bake(record,experiment,bake_directory):
    """Revalidate bound geometry and protected pixels; never trust PASS flags alone."""
    experiment,bake_directory=Path(experiment),Path(bake_directory)
    if sha(experiment/'preparation.json')!=record['preparation_sha256']:raise ValueError('UV preparation manifest changed')
    prep=json.loads((experiment/'preparation.json').read_text());manifest=json.loads((experiment/'views.json').read_text())
    if sha(Path(manifest['reviewed_packet'])/'views.json')!=record['frame_manifest_sha256']:raise ValueError('Reviewed camera evidence changed')
    if record.get('projection_kind')!='uv-atlas' or manifest.get('projection_kind')!='uv-atlas':raise ValueError('Expected UV-atlas texture evidence')
    for name,digest in prep['files'].items():
        if sha(experiment/name)!=digest:raise ValueError('UV preparation evidence changed: '+name)
    if sha(bake_directory/'worker.blend')!=record['baked_model_sha256']:raise ValueError('Baked model changed')
    if sha(experiment/'approved-model.blend')!=record['approved_model_sha256']:raise ValueError('Approved model changed')
    original=json.loads((experiment/'uv-evidence.json').read_text());actual=json.loads((bake_directory/'uv-evidence.json').read_text())
    validate_evidence(original);validate_evidence(actual)
    if original['model_sha256']!=record['approved_model_sha256']:raise ValueError('UV evidence is not from approved model')
    if original['atlas_sha256']!=sha(experiment/'source-atlas.png'):raise ValueError('Approved source atlas changed')
    if original['geometry']!=actual['geometry'] or original['triangles']!=actual['triangles']:raise ValueError('UV atlas bake changed actual geometry, normals or UVs')
    if actual['model_sha256']!=record['baked_model_sha256'] or sha(bake_directory/'uv-evidence.json')!=record['baked_uv_evidence_sha256']:raise ValueError('Baked UV evidence is stale')
    image=np.asarray(Image.open(bake_directory/'atlas.png').convert('RGBA'));input_image=np.asarray(Image.open(experiment/'input.png').convert('RGBA'));mask=np.asarray(Image.open(experiment/'mask.png').convert('RGBA'));surface=np.asarray(Image.open(experiment/'surface.png').convert('L'))>0
    if image.shape!=input_image.shape or mask.shape!=image.shape or surface.shape!=image.shape[:2]:raise ValueError('UV atlas dimensions changed')
    editable=mask[:,:,3]<128
    if np.any(editable&~surface):raise ValueError('Editable mask exposes physical outside')
    if np.any(image[~editable]!=input_image[~editable]):raise ValueError('Protected UV atlas pixels changed')
    if sha(bake_directory/'atlas.png')!=record['generated_sha256'] or actual['atlas_sha256']!=record['generated_sha256']:raise ValueError('Saved material is not the validated generated atlas')
    return dict(geometry_verified=True,uv_verified=True,protected_changes=0,editable_pixels=int(editable.sum()))
